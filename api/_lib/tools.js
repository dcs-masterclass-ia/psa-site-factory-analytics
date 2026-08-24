/**
 * Les 4 agents specialises, exposes comme des OUTILS que l'Agent KAM
 * (api/agent.js) peut appeler. Chaque outil "ask_agent_*" fait lui-meme un
 * appel Claude dedie (prompt systeme specialise) sur les donnees du site --
 * c'est ce qui rend la reponse reellement multi-agent plutot qu'un seul
 * prompt deguise. ask_agent_dashboard est different : c'est un mini-agent
 * d'edition de code qui ouvre une pull request GitHub (jamais de push
 * direct sur main).
 */

const { callClaude } = require("./anthropic");
const { loadSite, loadSiteRaw, listSites } = require("./data");
const { getFile, createBranch, updateFile, createPullRequest } = require("./github");

// Haiku 4.5, pas Sonnet : les agents specialistes resument/interpretent des
// donnees deja fournies (JSON du site) sur une tache ciblee et courte,
// jamais une orchestration -- Sonnet etait surdimensionne pour ce role.
// Concerne ask_agent_analytics/business/ux (chat reactif) ET la veille
// quotidienne (scripts/hermes_watch.js), qui reutilise askSpecialist.
// KAM_MODEL (api/agent.js, orchestration+synthese) et DASHBOARD_MODEL
// (edition de code) restent inchanges, role different.
// PAS de parametre "effort" ici : contrairement a Sonnet/Opus, Haiku 4.5 le
// rejette ("This model does not support the effort parameter") -- bug reel
// introduit par ce meme changement Sonnet->Haiku, jamais declenche avant
// (le premier appel Haiku reellement passe en prod, cote api/perf-ticket.js,
// l'a fait echouer immediatement). Decouvert et corrige le 08/08/2026.
const SPECIALIST_MODEL = "claude-haiku-4-5";
const DASHBOARD_MODEL = "claude-opus-5";
const MAX_DASHBOARD_ITERATIONS = 6;

function siteContext(sites) {
  const out = {};
  for (const nom of sites || []) {
    const data = loadSite(nom);
    if (data) out[nom] = data;
  }
  return out;
}

const SERIES_KEY = { sessions_parent: "u", sessions_reprise: "rep", gsc_clics: "sc", gsc_impressions: "si" };

// Serie numerique quotidienne EXACTE (jamais interpretee/arrondie par un
// modele) -- sert de source de verite a show_chart, pour que les
// graphiques affiches a l'utilisateur reprennent les vrais chiffres.
function getSeries(site, metric, months) {
  const raw = loadSite(site);
  if (!raw) return null;

  if (metric === "leads") {
    const dispo = Object.keys(raw.leads || {}).filter(m => m !== "total");
    const mois = (months && months.length ? months : dispo).filter(m => raw.leads[m]).sort();
    const labels = [], values = [];
    for (const m of mois) {
      (raw.leads[m].daily || []).forEach((v, i) => {
        labels.push(m + "-" + String(i + 1).padStart(2, "0"));
        values.push(v || 0);
      });
    }
    return { labels, values };
  }

  const key = SERIES_KEY[metric];
  if (!key) return null;
  const d = raw.daily || {};
  const allLabels = d.d || [];
  const allValues = d[key] || [];
  if (!months || !months.length) return { labels: allLabels, values: allValues.map(v => v || 0) };
  // dates completes "YYYY-MM-DD" (voir pipeline/build.py, migre le 08/08/2026) :
  // comparer sur les 7 premiers caracteres ("YYYY-MM"), jamais sur le seul
  // numero de mois -- deux annees differentes partagent le meme "MM" des que
  // la fenetre depasse 12 mois.
  const wanted = new Set(months);
  const labels = [], values = [];
  allLabels.forEach((lab, i) => {
    if (wanted.has(String(lab).slice(0, 7))) { labels.push(lab); values.push(allValues[i] || 0); }
  });
  return { labels, values };
}

// seuils repris de pipeline/insights.py (PLANCHER_ENTREES, seuil "mois
// incomplet" sur tdays) -- un mois sans assez de recul ou d'entrees dans le
// parcours fausserait le classement (petit echantillon = pourcentage
// instable), meme logique de garde-fou que les insights generes au build.
const PEERS_PLANCHER_ENTREES = 30;
const PEERS_PLANCHER_JOURS = 20;

// dernier mois "fiable" du funnel pour un site : le plus recent avec assez
// de jours releves ET assez d'entrees dans le parcours pour que son taux de
// conversion ne soit pas du bruit statistique.
function derniereMoisFunnelFiable(raw) {
  const fm = raw.funnelMonth || {};
  const tm = raw.trafficMonth || {};
  const mois = Object.keys(fm).filter(m => m !== "total").sort();
  for (let i = mois.length - 1; i >= 0; i--) {
    const m = mois[i];
    const bloc = fm[m];
    const steps = bloc && bloc.steps;
    const entrees = steps && steps.length ? steps[0].users : 0;
    const tdays = (tm[m] || {}).tdays;
    if (bloc && bloc.conversion_pct != null && entrees >= PEERS_PLANCHER_ENTREES
        && (tdays == null || tdays >= PEERS_PLANCHER_JOURS)) {
      return { mois: m, valeur: bloc.conversion_pct };
    }
  }
  return null;
}

// rang/mediane/meilleur d'un site parmi tout le parc -- meme perimetre
// (tous les sites, pas de filtre marque/marche) et meme metrique (taux de
// conversion du funnel) que le rang deja affiche cote client sur l'onglet
// GA4 (index.html, ~ligne 4412), pour ne jamais dire au KAM un chiffre
// different de ce qu'il voit deja a l'ecran. Une seule metrique pour
// l'instant, extensible plus tard si l'usage le justifie.
function compareToPeers(site, metric) {
  if (metric !== "conversion_funnel") {
    return { error: "Metrique non supportee. Seule 'conversion_funnel' est disponible pour l'instant." };
  }
  const points = [];
  for (const nom of listSites()) {
    const raw = loadSiteRaw(nom);
    if (!raw) continue;
    const r = derniereMoisFunnelFiable(raw);
    if (r) points.push({ site: nom, valeur: r.valeur, mois: r.mois });
  }
  const moi = points.find(p => p.site === site);
  if (!moi) {
    return { error: "Pas assez de donnees fiables (funnel) pour ce site sur cette metrique -- verifie le nom exact avec list_sites." };
  }
  points.sort((a, b) => b.valeur - a.valeur);
  const rang = points.findIndex(p => p.site === site) + 1;
  const valeursTriees = points.map(p => p.valeur).sort((a, b) => a - b);
  const mid = Math.floor(valeursTriees.length / 2);
  const mediane = valeursTriees.length % 2
    ? valeursTriees[mid] : (valeursTriees[mid - 1] + valeursTriees[mid]) / 2;
  const meilleur = points[0];
  return {
    site, metrique: "conversion_funnel", mois_utilise: moi.mois,
    valeur: moi.valeur, rang, total_sites: points.length,
    mediane_parc: Math.round(mediane * 100) / 100,
    meilleur_site: meilleur.site, meilleur_valeur: meilleur.valeur,
  };
}

async function askSpecialist(systemPrompt, question, sites) {
  const ctx = siteContext(sites);
  if (Object.keys(ctx).length === 0) {
    return "Aucune donnee disponible pour ce(s) site(s) -- verifie le nom exact du site (utilise list_sites).";
  }
  const resp = await callClaude({
    model: SPECIALIST_MODEL,
    system: systemPrompt,
    messages: [{
      role: "user",
      content: `Question : ${question}\n\nDonnees disponibles (JSON) pour ${Object.keys(ctx).join(", ")} :\n${JSON.stringify(ctx)}`,
    }],
    maxTokens: 1200,
  });
  const text = (resp.content || []).filter(b => b.type === "text").map(b => b.text).join("\n");
  return text || "Pas de reponse exploitable.";
}

const TOOLS = [
  {
    name: "list_sites",
    description: "Liste les sites PSA Site Factory disponibles (noms exacts a utiliser dans les autres outils).",
    input_schema: { type: "object", properties: {}, additionalProperties: false },
  },
  {
    name: "ask_agent_analytics",
    description: "Interroge l'Agent Analytics : trafic GA4 (site parent vs site de reprise), funnel de conversion, sources d'acquisition, Search Console. A utiliser pour comprendre POURQUOI le trafic ou la conversion a evolue.",
    input_schema: {
      type: "object",
      properties: {
        question: { type: "string", description: "Question precise posee a l'agent analytics." },
        sites: { type: "array", items: { type: "string" }, description: "Noms exacts des sites concernes (voir list_sites)." },
      },
      required: ["question", "sites"],
      additionalProperties: false,
    },
  },
  {
    name: "ask_agent_business",
    description: "Interroge l'Agent Business : volume de leads, repartition par marque/carburant/source/code marketing/appareil. A utiliser pour l'impact business (volume et qualite des leads).",
    input_schema: {
      type: "object",
      properties: {
        question: { type: "string" },
        sites: { type: "array", items: { type: "string" } },
      },
      required: ["question", "sites"],
      additionalProperties: false,
    },
  },
  {
    name: "ask_agent_ux",
    description: "Interroge l'Agent UX : points de friction dans le parcours de reprise (chute etape par etape du funnel), ecarts mobile/desktop. A utiliser pour proposer des actions concretes d'amelioration du parcours.",
    input_schema: {
      type: "object",
      properties: {
        question: { type: "string" },
        sites: { type: "array", items: { type: "string" } },
      },
      required: ["question", "sites"],
      additionalProperties: false,
    },
  },
  {
    name: "compare_to_peers",
    description: "Compare un site a l'ensemble du parc sur une metrique (rang, mediane du parc, meilleur site) -- utilise pour repondre a 'comment se situe ce site', 'est-ce dans la moyenne', 'est-ce un bon ou mauvais chiffre'. Seule la metrique 'conversion_funnel' (taux de conversion du parcours de reprise) est disponible pour l'instant.",
    input_schema: {
      type: "object",
      properties: {
        site: { type: "string", description: "Nom exact du site (voir list_sites)." },
        metric: { type: "string", enum: ["conversion_funnel"] },
      },
      required: ["site", "metric"],
      additionalProperties: false,
    },
  },
  {
    name: "get_series",
    description: "Renvoie une serie numerique quotidienne EXACTE pour un site et une metrique -- toujours passer par cet outil avant show_chart, jamais recopier des chiffres approximes depuis la reponse d'un autre agent.",
    input_schema: {
      type: "object",
      properties: {
        site: { type: "string", description: "Nom exact du site (voir list_sites)." },
        metric: { type: "string", enum: ["sessions_parent", "sessions_reprise", "leads", "gsc_clics", "gsc_impressions"] },
        months: { type: "array", items: { type: "string" }, description: "Mois au format AAAA-MM (ex. 2026-07). Omis = tous les mois disponibles." },
      },
      required: ["site", "metric"],
      additionalProperties: false,
    },
  },
  {
    name: "show_chart",
    description: "Affiche un graphique dans la reponse a l'utilisateur. N'utilise QUE des valeurs obtenues via get_series (jamais de valeurs inventees, arrondies ou estimees) -- recopie-les exactement. Utile quand une evolution se comprend mieux visuellement qu'en texte.",
    input_schema: {
      type: "object",
      properties: {
        title: { type: "string" },
        type: { type: "string", enum: ["line", "bar"] },
        labels: { type: "array", items: { type: "string" }, description: "Etiquettes de l'axe (ex. dates), meme longueur que chaque serie." },
        series: {
          type: "array",
          items: {
            type: "object",
            properties: { name: { type: "string" }, values: { type: "array", items: { type: "number" } } },
            required: ["name", "values"],
            additionalProperties: false,
          },
        },
      },
      required: ["title", "type", "labels", "series"],
      additionalProperties: false,
    },
  },
  {
    name: "ask_agent_dashboard",
    description: "Demande a l'Agent Dashboard de modifier ou d'ajouter un module d'analyse sur le dashboard. N'appelle cet outil QUE si la demande porte explicitement sur un changement du dashboard lui-meme (nouveau graphique, nouvelle carte...) -- jamais pour une simple question d'analyse. Ouvre une vraie pull request GitHub (jamais de modification directe sur main) ; le resultat est un lien vers la PR, pas une reponse d'analyse.",
    input_schema: {
      type: "object",
      properties: {
        spec: { type: "string", description: "Description precise du module/changement demande : titre, metrique, type de graphique, emplacement." },
      },
      required: ["spec"],
      additionalProperties: false,
    },
  },
];

async function runDashboardAgent(spec) {
  let fileContent, fileSha;
  try {
    const f = await getFile("index.html"); // branche par defaut de getFile (voir api/_lib/github.js) : dynamique, plus "main" en dur
    fileContent = f.content;
    fileSha = f.sha;
  } catch (e) {
    return "Impossible de recuperer index.html depuis GitHub : " + e.message;
  }
  const originalContent = fileContent;

  const editTools = [
    {
      name: "str_replace",
      description: "Remplace une occurrence unique de old_str par new_str dans index.html. old_str doit apparaitre EXACTEMENT une fois dans le fichier, sinon l'outil renvoie une erreur.",
      input_schema: {
        type: "object",
        properties: {
          old_str: { type: "string" },
          new_str: { type: "string" },
        },
        required: ["old_str", "new_str"],
        additionalProperties: false,
      },
    },
    {
      name: "done",
      description: "Signale que l'edition est terminee et prete a etre soumise en pull request.",
      input_schema: {
        type: "object",
        properties: { summary: { type: "string" } },
        required: ["summary"],
        additionalProperties: false,
      },
    },
  ];

  const system = `Tu es l'Agent Dashboard du dashboard PSA Site Factory (fichier unique index.html, gabarit de templating "x-dc" avec {{ }}, sc-for, sc-if -- repere le style existant et imite-le exactement : variables CSS var(--text) etc., animations riseIn deja presentes, memes conventions de nommage et d'indentation).

Voici le contenu actuel complet du fichier :
<index_html>
${fileContent}
</index_html>

Demande : ${spec}

Fais UNE ou plusieurs editions ciblees avec str_replace (jamais de reecriture complete du fichier). Chaque old_str doit etre copie EXACTEMENT depuis le fichier ci-dessus et etre unique dans le fichier -- si l'outil te signale plusieurs occurrences, elargis le contexte de old_str pour le rendre unique. Quand tu as termine, appelle done avec un resume en francais de ce que tu as ajoute.`;

  let messages = [{ role: "user", content: "Effectue la demande." }];
  let summary = "";
  let sawDone = false;

  for (let i = 0; i < MAX_DASHBOARD_ITERATIONS; i++) {
    const resp = await callClaude({
      model: DASHBOARD_MODEL,
      system,
      messages,
      tools: editTools,
      thinking: { type: "adaptive" },
      effort: "high",
      maxTokens: 8000,
    });
    messages.push({ role: "assistant", content: resp.content });
    if (resp.stop_reason !== "tool_use") break;

    const toolResults = [];
    for (const block of resp.content) {
      if (block.type !== "tool_use") continue;
      if (block.name === "done") {
        summary = (block.input && block.input.summary) || "";
        sawDone = true;
        toolResults.push({ type: "tool_result", tool_use_id: block.id, content: "OK" });
        continue;
      }
      if (block.name === "str_replace") {
        const oldStr = block.input && block.input.old_str;
        const newStr = block.input && block.input.new_str;
        const count = oldStr ? fileContent.split(oldStr).length - 1 : 0;
        if (!oldStr || count !== 1) {
          toolResults.push({
            type: "tool_result", tool_use_id: block.id,
            content: `Erreur : old_str trouve ${count} fois (doit etre exactement 1). Affine ta recherche.`,
            is_error: true,
          });
          continue;
        }
        fileContent = fileContent.replace(oldStr, newStr);
        toolResults.push({ type: "tool_result", tool_use_id: block.id, content: "Remplacement effectue." });
      }
    }
    messages.push({ role: "user", content: toolResults });
    if (sawDone) break;
  }

  if (fileContent === originalContent) {
    return "L'Agent Dashboard n'a pas reussi a produire d'edition valide pour cette demande -- aucune pull request ouverte.";
  }
  if (fileContent.length < originalContent.length * 0.9) {
    return "L'Agent Dashboard a produit un resultat suspect (fichier anormalement raccourci) -- aucune PR n'a ete ouverte par securite.";
  }

  const branch = "agent-dashboard/" + Date.now();
  try {
    await createBranch(branch);
    await updateFile("index.html", branch, fileContent, fileSha, "Agent Dashboard : " + spec.slice(0, 60));
    const pr = await createPullRequest(
      branch,
      "Agent Dashboard : " + spec.slice(0, 72),
      `Demande d'origine : ${spec}\n\nResume de l'agent : ${summary}\n\n_Genere automatiquement par Agent Dashboard -- a relire avant merge._`
    );
    return `Pull request ouverte : ${pr.url}`;
  } catch (e) {
    return "Edition generee mais echec a l'ouverture de la pull request : " + e.message;
  }
}

async function runTool(name, input) {
  input = input || {};
  if (name === "list_sites") {
    return { sites: listSites() };
  }
  if (name === "ask_agent_analytics") {
    return await askSpecialist(
      "Tu es l'Agent Analytics du dashboard PSA Site Factory. Analyse le trafic GA4 (site parent vs site de reprise), le funnel de conversion et Search Console a partir des donnees JSON fournies. Reponds en francais, de facon factuelle et chiffree (cite les vrais chiffres du JSON), en 4 a 8 phrases, sans jamais inventer de donnee absente du JSON.",
      input.question, input.sites
    );
  }
  if (name === "ask_agent_business") {
    return await askSpecialist(
      "Tu es l'Agent Business du dashboard PSA Site Factory. Analyse les leads (volume, repartition marque/carburant/source/code marketing/appareil) a partir des donnees JSON fournies. Reponds en francais, factuel et chiffre, en 4 a 8 phrases, sans jamais inventer de donnee absente du JSON.",
      input.question, input.sites
    );
  }
  if (name === "ask_agent_ux") {
    return await askSpecialist(
      "Tu es l'Agent UX du dashboard PSA Site Factory. Identifie les points de friction du parcours (chute entre etapes du funnel, ecarts mobile/desktop) a partir des donnees JSON fournies, et propose 1 a 3 actions concretes. Reponds en francais, factuel et chiffre, sans jamais inventer de donnee absente du JSON.",
      input.question, input.sites
    );
  }
  if (name === "get_series") {
    const result = getSeries(input.site, input.metric, input.months);
    return result || { error: "Site ou metrique inconnu -- verifie avec list_sites." };
  }
  if (name === "compare_to_peers") {
    return compareToPeers(input.site, input.metric);
  }
  if (name === "ask_agent_dashboard") {
    return await runDashboardAgent(input.spec || "");
  }
  throw new Error("Outil inconnu : " + name);
}

module.exports = { TOOLS, runTool, askSpecialist };
