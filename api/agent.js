/**
 * Agent KAM -- orchestrateur de l'assistant multi-agent "Hermes". Recoit
 * une question (+ perimetre optionnel, + pieces jointes optionnelles),
 * interroge les agents specialises (api/_lib/tools.js) via le mecanisme de
 * tool-use de Claude, et synthetise une reponse unique -- avec, quand
 * pertinent, des graphiques (show_chart) bases sur des donnees exactes
 * (get_series).
 *
 * Protege par middleware.js en amont (cookie de session valide requis) ;
 * la verification ci-dessous est une defense en profondeur.
 */

const { callClaudeStream } = require("./_lib/anthropic");
const { TOOLS, runTool } = require("./_lib/tools");
const { verifySessionFromRequest } = require("./_lib/auth");

// Sonnet 5 + effort medium : qualite proche d'Opus sur ce type de travail
// agentique (orchestration + synthese), pour une fraction du cout -- le
// "vrai" raisonnement analytique est fait par les agents specialistes
// (api/_lib/tools.js), le KAM orchestre et synthetise.
const KAM_MODEL = "claude-sonnet-5";
const KAM_EFFORT = "medium";
const MAX_ITERATIONS = 6;
const MAX_ATTACHMENTS = 3;
const MAX_ATTACHMENT_BYTES = 4 * 1024 * 1024; // 4 Mo par fichier (base64 decode)

const SYSTEM = `Tu es Agent KAM, le cerveau de l'assistant "Hermes" du dashboard PSA Site Factory. Les personnes qui te parlent sont des Key Account Managers qui suivent la performance de sites de reprise automobile (trafic, leads, conversion).

Regles :
- Reponds en interrogeant les agents specialises a ta disposition (list_sites, ask_agent_analytics, ask_agent_business, ask_agent_ux, get_series, compare_to_peers, show_chart, ask_agent_dashboard) plutot qu'a partir de connaissances generales -- ce sont eux qui ont acces aux vraies donnees.
- Utilise list_sites si tu n'es pas sur du nom exact d'un site. Si un "Perimetre selectionne" est indique dans le message de l'utilisateur, priorise ces sites sauf si la question en nomme explicitement d'autres. Si rien n'est selectionne et que la question est ambigue ("ce site", "ici", "on"), utilise en repli le site/onglet indique par "Actuellement affiche dans le dashboard" quand ce contexte est present.
- Pour une question d'analyse ("pourquoi X a baisse", "quel impact business", "quelles actions proposer"), appelle plusieurs agents pertinents (analytics + business + ux selon le cas) puis synthetise UNE reponse argumentee et chiffree qui croise leurs constats -- jamais une simple liste de chiffres juxtaposes sans interpretation.
- Pour une question de positionnement ("comment se situe ce site", "est-ce dans la moyenne", "est-ce un bon chiffre"), appelle compare_to_peers plutot que de qualifier un chiffre a l'instinct -- un chiffre n'est "bon" ou "mauvais" que compare au reste du parc.
- Visualisation : quand une evolution chiffree (trafic, leads, funnel...) est au coeur de la reponse, appelle get_series pour obtenir les vraies valeurs puis show_chart pour les afficher -- ne recopie JAMAIS des valeurs approximees depuis le texte d'un autre agent dans un graphique, elles doivent venir de get_series.
- N'appelle ask_agent_dashboard que si la demande porte explicitement sur une modification du dashboard lui-meme (nouveau graphique, nouveau module...).
- Si des pieces jointes sont fournies, elles apparaissent directement dans ce message -- appuie-toi dessus si la question les concerne.
- Si les donnees ne permettent pas de repondre avec certitude, dis-le clairement plutot que d'inventer.
- Format : reponds en Markdown simple (**gras** pour les points cles, listes a puces pour les actions, pas de titres ##). Reste concis, va droit a l'analyse et aux actions concretes, sans meta-commentaire sur ton propre raisonnement.`;

function labelForTool(name) {
  return {
    list_sites: "Sites",
    ask_agent_analytics: "Analytics",
    ask_agent_business: "Business",
    ask_agent_ux: "UX",
    get_series: "Données",
    compare_to_peers: "Comparaison",
    show_chart: "Visualisation",
    ask_agent_dashboard: "Dashboard",
  }[name] || name;
}

// libelle humain pour l'onglet actuellement affiche -- doit rester en phase
// avec les cles internes (st.tab) de index.html, cf. TAB_LABELS_VIEW plus
// bas dans ce fichier si de nouveaux onglets sont ajoutes.
const TAB_LABELS_VIEW = {
  ga4: "Vue d'ensemble (GA4)", gsc: "Search Console", v2: "Comparaison V2",
  performance: "PageSpeed", tableau: "Tableau (leads back-office)",
  assistant: "KamIA", compare: "Comparatif",
};

function buildInitialContent(question, scope, attachments, view) {
  const blocks = [];
  for (const att of (attachments || []).slice(0, MAX_ATTACHMENTS)) {
    if (!att || !att.dataBase64 || !att.mediaType) continue;
    const approxBytes = att.dataBase64.length * 0.75;
    if (approxBytes > MAX_ATTACHMENT_BYTES) continue;
    if (att.mediaType.startsWith("image/")) {
      blocks.push({ type: "image", source: { type: "base64", media_type: att.mediaType, data: att.dataBase64 } });
    } else if (att.mediaType === "application/pdf") {
      blocks.push({ type: "document", source: { type: "base64", media_type: att.mediaType, data: att.dataBase64 } });
    }
  }
  let text = question;
  // "Actuellement affiche" (site+onglet a l'ecran, automatique) reste une
  // ligne DISTINCTE du "Perimetre selectionne" (choix manuel de
  // l'utilisateur, chatScope) -- jamais fusionnes : chatScope doit pouvoir
  // rester independant du site consulte (cf. plan "intelligence dashboard").
  if (view && typeof view.site === "string" && view.site) {
    const tabLabel = TAB_LABELS_VIEW[view.tab] || view.tab || "";
    text += `\n\n(Actuellement affiché dans le dashboard : ${view.site}${tabLabel ? ", onglet " + tabLabel : ""} -- a utiliser seulement si aucun perimetre n'est selectionne et que la question est ambigue)`;
  }
  if (Array.isArray(scope) && scope.length > 0) {
    text += `\n\n(Perimetre selectionne par l'utilisateur : ${scope.join(", ")})`;
  }
  blocks.push({ type: "text", text });
  return blocks;
}

/**
 * Boucle tool-use partagee par les deux modes de reponse (JSON bufferise et
 * SSE). Yield des evenements incrementaux au fil des tours ; le dernier
 * evenement est toujours "done" avec la meme forme que l'ancienne reponse
 * JSON (answer/agentsConsultes/charts/history), pour rester compatible avec
 * le front actuel qui ne consomme que ca.
 */
async function* runAgentLoop(messages) {
  const agentsConsultes = new Set();
  const charts = [];

  for (let i = 0; i < MAX_ITERATIONS; i++) {
    let finalContent = null;
    let stopReason = null;

    for await (const ev of callClaudeStream({
      model: KAM_MODEL,
      system: SYSTEM,
      messages,
      tools: TOOLS,
      thinking: { type: "adaptive" },
      effort: KAM_EFFORT,
      maxTokens: 4096,
    })) {
      if (ev.type === "text-delta") {
        yield { type: "text-delta", text: ev.text };
      } else if (ev.type === "tool-call") {
        yield { type: "tool-call-start", toolName: ev.name, label: labelForTool(ev.name) };
      } else if (ev.type === "message-complete") {
        finalContent = ev.content;
        stopReason = ev.stop_reason;
      }
    }

    messages.push({ role: "assistant", content: finalContent });

    if (stopReason !== "tool_use") {
      const answer = (finalContent || []).filter(b => b.type === "text").map(b => b.text).join("\n");
      yield { type: "done", answer, agentsConsultes: [...agentsConsultes], charts, history: messages };
      return;
    }

    const toolUses = finalContent.filter(b => b.type === "tool_use");
    const toolResults = [];
    for (const block of toolUses) {
      agentsConsultes.add(labelForTool(block.name));
      if (block.name === "show_chart") {
        charts.push(block.input);
        yield { type: "chart", spec: block.input };
        toolResults.push({ type: "tool_result", tool_use_id: block.id, content: "Graphique pris en compte, il sera affiche a l'utilisateur." });
        continue;
      }
      try {
        const result = await runTool(block.name, block.input);
        yield { type: "tool-call-end", toolName: block.name };
        toolResults.push({
          type: "tool_result",
          tool_use_id: block.id,
          content: typeof result === "string" ? result : JSON.stringify(result),
        });
      } catch (e) {
        yield { type: "tool-call-error", toolName: block.name, message: e && e.message ? e.message : String(e) };
        toolResults.push({
          type: "tool_result",
          tool_use_id: block.id,
          content: "Erreur : " + (e && e.message ? e.message : e),
          is_error: true,
        });
      }
    }
    messages.push({ role: "user", content: toolResults });
  }

  yield {
    type: "done",
    answer: "Desole, je n'ai pas reussi a conclure sur cette question (trop d'etapes necessaires).",
    agentsConsultes: [...agentsConsultes],
    charts,
    history: messages,
  };
}

// ---------------------------------------------------------------------------
// Mode AG-UI (?stream=1) : consomme par le panneau React Hermes (panel/).
// Recoit un RunAgentInput standard (threadId, runId, messages, resume?) et
// emet le protocole d'evenements AG-UI (TEXT_MESSAGE_*, TOOL_CALL_*,
// RUN_STARTED/FINISHED/ERROR) au fil de la meme boucle tool-use que le mode
// JSON. Contrairement au mode JSON, l'appel a ask_agent_dashboard (qui edite
// index.html et ouvre une PR) declenche un interrupt AG-UI -- l'execution
// est suspendue et RUN_FINISHED renvoie outcome:{type:"interrupt", ...} ;
// l'utilisateur doit confirmer avant que le tour ne reprenne via `resume`.
// ---------------------------------------------------------------------------

const CONFIRM_BEFORE_EXEC = new Set(["ask_agent_dashboard"]);

function aguiUserContentToBlocks(content) {
  if (typeof content === "string") return [{ type: "text", text: content }];
  if (!Array.isArray(content)) return [{ type: "text", text: "" }];
  return content
    .map((part) => {
      if (part.type === "text") return { type: "text", text: part.text };
      if (part.type === "image" && part.source) {
        return part.source.type === "data"
          ? { type: "image", source: { type: "base64", media_type: part.source.mimeType, data: part.source.value } }
          : { type: "image", source: { type: "url", url: part.source.value } };
      }
      return { type: "text", text: "" };
    })
    .filter((b) => !(b.type === "text" && b.text === ""));
}

/** Convertit les Message[] du protocole AG-UI en messages Claude (blocks). */
function aguiMessagesToClaude(aguiMessages) {
  const claudeMessages = [];
  const systemExtra = [];
  for (const m of aguiMessages || []) {
    if (m.role === "system" || m.role === "developer") {
      if (m.content) systemExtra.push(m.content);
    } else if (m.role === "user") {
      claudeMessages.push({ role: "user", content: aguiUserContentToBlocks(m.content) });
    } else if (m.role === "assistant") {
      const blocks = [];
      if (m.content) blocks.push({ type: "text", text: m.content });
      for (const tc of m.toolCalls || []) {
        let input = {};
        try {
          input = JSON.parse(tc.function.arguments || "{}");
        } catch (_) {}
        blocks.push({ type: "tool_use", id: tc.id, name: tc.function.name, input });
      }
      claudeMessages.push({ role: "assistant", content: blocks });
    } else if (m.role === "tool") {
      const block = { type: "tool_result", tool_use_id: m.toolCallId, content: m.content };
      const last = claudeMessages[claudeMessages.length - 1];
      if (last && last.role === "user" && Array.isArray(last.content) && last.content.every((b) => b.type === "tool_result")) {
        last.content.push(block);
      } else {
        claudeMessages.push({ role: "user", content: [block] });
      }
    }
  }
  return { claudeMessages, system: systemExtra.join("\n\n") };
}

function findToolUseById(claudeMessages, id) {
  for (let i = claudeMessages.length - 1; i >= 0; i--) {
    const m = claudeMessages[i];
    if (m.role !== "assistant" || !Array.isArray(m.content)) continue;
    const block = m.content.find((b) => b.type === "tool_use" && b.id === id);
    if (block) return block;
  }
  return null;
}

function interruptMessageFor(block) {
  if (block.name === "ask_agent_dashboard") {
    const req = (block.input && block.input.request) || "";
    return `Hermes propose de modifier le dashboard (ouverture d'une Pull Request GitHub) : "${req}". Confirmer ?`;
  }
  return `Action groupee avec une modification du dashboard, en attente de confirmation (${labelForTool(block.name)}).`;
}

/** Applique les reponses `resume` d'un interrupt precedent : execute (ou annule) les tool_use en attente et pousse le message tool_result correspondant. */
async function applyResume(claudeMessages, resume) {
  const toolResults = [];
  for (const entry of resume) {
    const block = findToolUseById(claudeMessages, entry.interruptId);
    if (!block) continue;
    if (entry.status === "resolved") {
      try {
        const result = await runTool(block.name, block.input);
        toolResults.push({ type: "tool_result", tool_use_id: block.id, content: typeof result === "string" ? result : JSON.stringify(result) });
      } catch (e) {
        toolResults.push({ type: "tool_result", tool_use_id: block.id, content: "Erreur : " + (e && e.message ? e.message : e), is_error: true });
      }
    } else {
      toolResults.push({ type: "tool_result", tool_use_id: block.id, content: "Action annulee par l'utilisateur.", is_error: true });
    }
  }
  if (toolResults.length > 0) claudeMessages.push({ role: "user", content: toolResults });
}

async function runAguiLoop(send, claudeMessages, system, threadId, runId) {
  const agentsConsultes = new Set();
  const charts = [];
  const sendState = () => send({ type: "STATE_SNAPSHOT", snapshot: { agentsConsultes: [...agentsConsultes], charts } });

  for (let i = 0; i < MAX_ITERATIONS; i++) {
    let finalContent = null;
    let stopReason = null;
    const messageId = require("crypto").randomUUID();
    let textStarted = false;

    for await (const ev of callClaudeStream({
      model: KAM_MODEL,
      system: system ? `${SYSTEM}\n\n${system}` : SYSTEM,
      messages: claudeMessages,
      tools: TOOLS,
      thinking: { type: "adaptive" },
      effort: KAM_EFFORT,
      maxTokens: 4096,
    })) {
      if (ev.type === "text-delta") {
        if (!textStarted) {
          send({ type: "TEXT_MESSAGE_START", messageId, role: "assistant" });
          textStarted = true;
        }
        send({ type: "TEXT_MESSAGE_CONTENT", messageId, delta: ev.text });
      } else if (ev.type === "tool-call") {
        agentsConsultes.add(labelForTool(ev.name));
        send({ type: "TOOL_CALL_START", toolCallId: ev.id, toolCallName: ev.name, parentMessageId: messageId });
        send({ type: "TOOL_CALL_ARGS", toolCallId: ev.id, delta: JSON.stringify(ev.input) });
        send({ type: "TOOL_CALL_END", toolCallId: ev.id });
      } else if (ev.type === "message-complete") {
        finalContent = ev.content;
        stopReason = ev.stop_reason;
      }
    }
    if (textStarted) send({ type: "TEXT_MESSAGE_END", messageId });

    claudeMessages.push({ role: "assistant", content: finalContent });

    if (stopReason !== "tool_use") {
      sendState();
      send({ type: "RUN_FINISHED", threadId, runId, outcome: { type: "success" } });
      return;
    }

    const toolUses = finalContent.filter((b) => b.type === "tool_use");

    if (toolUses.some((b) => CONFIRM_BEFORE_EXEC.has(b.name))) {
      const interrupts = toolUses.map((b) => ({
        id: b.id,
        reason: CONFIRM_BEFORE_EXEC.has(b.name) ? "confirm_dashboard_edit" : "batched_with_dashboard_edit",
        toolCallId: b.id,
        message: interruptMessageFor(b),
        metadata: { toolName: b.name, input: b.input },
      }));
      sendState();
      send({ type: "RUN_FINISHED", threadId, runId, outcome: { type: "interrupt", interrupts } });
      return;
    }

    const toolResults = [];
    for (const block of toolUses) {
      agentsConsultes.add(labelForTool(block.name));
      if (block.name === "show_chart") {
        charts.push(block.input);
        toolResults.push({ type: "tool_result", tool_use_id: block.id, content: "Graphique pris en compte, il sera affiche a l'utilisateur." });
        sendState();
        continue;
      }
      try {
        const result = await runTool(block.name, block.input);
        const content = typeof result === "string" ? result : JSON.stringify(result);
        toolResults.push({ type: "tool_result", tool_use_id: block.id, content });
        send({ type: "TOOL_CALL_RESULT", messageId: require("crypto").randomUUID(), toolCallId: block.id, content, role: "tool" });
      } catch (e) {
        toolResults.push({ type: "tool_result", tool_use_id: block.id, content: "Erreur : " + (e && e.message ? e.message : e), is_error: true });
      }
    }
    claudeMessages.push({ role: "user", content: toolResults });
  }

  send({ type: "RUN_ERROR", message: "Trop d'etapes necessaires pour conclure." });
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Methode non autorisee." });
    return;
  }

  const session = verifySessionFromRequest(req);
  if (!session) {
    res.status(401).json({ error: "Non authentifie." });
    return;
  }

  const wantsAgui = req.query && req.query.stream === "1";

  if (wantsAgui) {
    const input = req.body || {};
    const { threadId, runId, messages: aguiMessages, resume } = input;
    if (!threadId || !runId || !Array.isArray(aguiMessages)) {
      res.status(400).json({ error: "RunAgentInput invalide (threadId/runId/messages requis)." });
      return;
    }

    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    });
    const send = (ev) => res.write(`data: ${JSON.stringify(ev)}\n\n`);
    send({ type: "RUN_STARTED", threadId, runId });

    try {
      const { claudeMessages, system } = aguiMessagesToClaude(aguiMessages);
      if (Array.isArray(resume) && resume.length > 0) {
        await applyResume(claudeMessages, resume);
      }
      await runAguiLoop(send, claudeMessages, system, threadId, runId);
    } catch (e) {
      send({ type: "RUN_ERROR", message: String(e && e.message ? e.message : e) });
    } finally {
      res.end();
    }
    return;
  }

  // Mode JSON bufferise -- comportement inchange pour le front actuel.
  const { question, history, scope, attachments, view } = req.body || {};
  if (!question || typeof question !== "string") {
    res.status(400).json({ error: "question requise." });
    return;
  }

  const messages = Array.isArray(history) ? history.slice(-20) : [];
  messages.push({ role: "user", content: buildInitialContent(question, scope, attachments, view) });

  try {
    for await (const ev of runAgentLoop(messages)) {
      if (ev.type === "done") {
        res.status(200).json({ answer: ev.answer, agentsConsultes: ev.agentsConsultes, charts: ev.charts, history: ev.history });
        return;
      }
    }
  } catch (e) {
    res.status(500).json({ error: String(e && e.message ? e.message : e) });
  }
};
