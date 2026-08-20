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
- Reponds en interrogeant les agents specialises a ta disposition (list_sites, ask_agent_analytics, ask_agent_business, ask_agent_ux, get_series, show_chart, ask_agent_dashboard) plutot qu'a partir de connaissances generales -- ce sont eux qui ont acces aux vraies donnees.
- Utilise list_sites si tu n'es pas sur du nom exact d'un site. Si un "Perimetre selectionne" est indique dans le message de l'utilisateur, priorise ces sites sauf si la question en nomme explicitement d'autres.
- Pour une question d'analyse ("pourquoi X a baisse", "quel impact business", "quelles actions proposer"), appelle plusieurs agents pertinents (analytics + business + ux selon le cas) puis synthetise UNE reponse argumentee et chiffree qui croise leurs constats -- jamais une simple liste de chiffres juxtaposes sans interpretation.
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
    show_chart: "Visualisation",
    ask_agent_dashboard: "Dashboard",
  }[name] || name;
}

function buildInitialContent(question, scope, attachments) {
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

  const { question, history, scope, attachments } = req.body || {};
  if (!question || typeof question !== "string") {
    res.status(400).json({ error: "question requise." });
    return;
  }

  const messages = Array.isArray(history) ? history.slice(-20) : [];
  messages.push({ role: "user", content: buildInitialContent(question, scope, attachments) });

  const wantsStream = (req.query && req.query.stream === "1") || req.headers.accept === "text/event-stream";

  if (!wantsStream) {
    // Mode JSON bufferise -- comportement inchange pour le front actuel.
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
    return;
  }

  // Mode SSE -- destine au futur panneau React/AG-UI (phase 2).
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no",
  });
  const send = (ev) => res.write(`data: ${JSON.stringify(ev)}\n\n`);
  try {
    for await (const ev of runAgentLoop(messages)) {
      send(ev);
      if (ev.type === "done") break;
    }
  } catch (e) {
    send({ type: "error", message: String(e && e.message ? e.message : e) });
  } finally {
    res.end();
  }
};
