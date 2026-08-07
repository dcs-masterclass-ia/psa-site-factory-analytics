/**
 * Agent KAM -- orchestrateur de l'assistant multi-agent. Recoit une
 * question, interroge les agents specialises (api/_lib/tools.js) via le
 * mecanisme de tool-use de Claude, et synthetise une reponse unique.
 *
 * Protege par middleware.js en amont (cookie de session valide requis) ;
 * la verification ci-dessous est une defense en profondeur.
 */

const { callClaude } = require("./_lib/anthropic");
const { TOOLS, runTool } = require("./_lib/tools");
const { verifySessionFromRequest } = require("./_lib/auth");

const KAM_MODEL = "claude-opus-5";
const MAX_ITERATIONS = 6;

const SYSTEM = `Tu es Agent KAM, l'orchestrateur de l'assistant du dashboard PSA Site Factory. Les personnes qui te parlent sont des Key Account Managers qui suivent la performance de sites de reprise automobile (trafic, leads, conversion).

Regles :
- Reponds en interrogeant les agents specialises a ta disposition (list_sites, ask_agent_analytics, ask_agent_business, ask_agent_ux, ask_agent_dashboard) plutot qu'a partir de connaissances generales -- ce sont eux qui ont acces aux vraies donnees.
- Utilise list_sites si tu n'es pas sur du nom exact d'un site.
- Pour une question d'analyse ("pourquoi X a baisse", "quel impact business", "quelles actions proposer"), appelle plusieurs agents pertinents (analytics + business + ux selon le cas) puis synthetise UNE reponse argumentee et chiffree, en francais, qui croise leurs constats -- jamais une simple liste de chiffres juxtaposes sans interpretation.
- N'appelle ask_agent_dashboard que si la demande porte explicitement sur une modification du dashboard lui-meme (nouveau graphique, nouveau module...).
- Si les donnees ne permettent pas de repondre avec certitude, dis-le clairement plutot que d'inventer.
- Reste concis : pas de meta-commentaire sur ton propre raisonnement, va droit a l'analyse et aux actions concretes.`;

function labelForTool(name) {
  return {
    list_sites: "Sites",
    ask_agent_analytics: "Analytics",
    ask_agent_business: "Business",
    ask_agent_ux: "UX",
    ask_agent_dashboard: "Dashboard",
  }[name] || name;
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

  const { question, history } = req.body || {};
  if (!question || typeof question !== "string") {
    res.status(400).json({ error: "question requise." });
    return;
  }

  const messages = Array.isArray(history) ? history.slice(-20) : [];
  messages.push({ role: "user", content: question });

  const agentsConsultes = new Set();

  try {
    for (let i = 0; i < MAX_ITERATIONS; i++) {
      const resp = await callClaude({
        model: KAM_MODEL,
        system: SYSTEM,
        messages,
        tools: TOOLS,
        thinking: { type: "adaptive" },
        effort: "high",
        maxTokens: 4096,
      });
      messages.push({ role: "assistant", content: resp.content });

      if (resp.stop_reason !== "tool_use") {
        const answer = (resp.content || []).filter(b => b.type === "text").map(b => b.text).join("\n");
        res.status(200).json({ answer, agentsConsultes: [...agentsConsultes], history: messages });
        return;
      }

      const toolUses = resp.content.filter(b => b.type === "tool_use");
      const toolResults = [];
      for (const block of toolUses) {
        agentsConsultes.add(labelForTool(block.name));
        try {
          const result = await runTool(block.name, block.input);
          toolResults.push({
            type: "tool_result",
            tool_use_id: block.id,
            content: typeof result === "string" ? result : JSON.stringify(result),
          });
        } catch (e) {
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

    res.status(200).json({
      answer: "Desole, je n'ai pas reussi a conclure sur cette question (trop d'etapes necessaires).",
      agentsConsultes: [...agentsConsultes],
      history: messages,
    });
  } catch (e) {
    res.status(500).json({ error: String(e && e.message ? e.message : e) });
  }
};
