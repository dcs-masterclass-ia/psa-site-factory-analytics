#!/usr/bin/env node
/**
 * Analyse narrative des sites retenus par pipeline/watch.py (pre-tri
 * statistique gratuit). Appele par .github/workflows/hermes-watch.yml,
 * jamais par une requete HTTP -- reutilise directement les memes modules
 * que l'assistant Hermes reactif (api/_lib/*), sans passer par /api/agent
 * (protege par cookie de session, inadapte a un job planifie sans navigateur).
 *
 * Usage
 * -----
 *     node scripts/hermes_watch.js <chemin_candidats.json>
 */
const fs = require("fs");
const path = require("path");
const { askSpecialist } = require("../api/_lib/tools");

const WATCH_SYSTEM = `Tu es l'analyste de veille automatique du dashboard PSA Site Factory. On te donne un site dont le trafic ou les leads ont significativement bouge sur les 7 derniers jours par rapport aux 7 precedents, avec les chiffres bruts en contexte.

Reponds en deux parties, separees par une ligne contenant UNIQUEMENT "---" :
1. Une synthese d'UNE phrase (20 mots maximum) : le fait principal et sa cause probable, sans detail chiffre.
2. L'analyse complete en 3 a 5 phrases : cause la plus probable en te basant sur les donnees fournies (funnel, canaux, leads par marque/appareil si disponibles), impact business, action concrete si pertinente.

Sois direct et factuel, ne cite que des donnees presentes dans le JSON fourni -- si tu ne peux pas conclure avec certitude, dis-le clairement plutot que de deviner. Ne mets rien avant la synthese ni en dehors de ces deux parties.`;

function gravite(c) {
  const pire = Math.max(Math.abs(c.sessionsDelta || 0), Math.abs(c.leadsDelta || 0));
  if (c.anomalieDetectee || pire >= 50) return "important";
  return "a_surveiller";
}

// separe la reponse en {synthese, analyse} ; jamais bloquant si Claude
// s'ecarte du format demande -- retombe sur un simple tronquage plutot que
// de perdre l'analyse.
function decoupe(texte) {
  const parts = String(texte || "").split(/\n\s*---\s*\n/);
  if (parts.length >= 2 && parts[0].trim()) {
    return { synthese: parts[0].trim(), analyse: parts.slice(1).join("\n---\n").trim() };
  }
  const brut = String(texte || "").trim();
  const court = brut.slice(0, 140);
  return { synthese: court + (brut.length > 140 ? "…" : ""), analyse: brut };
}

function question(c) {
  const parts = [];
  if (c.sessionsDelta != null) {
    parts.push(`sessions reprise : ${c.sessionsRecent} sur les 7 derniers jours contre ${c.sessionsPrecedent} les 7 precedents (${c.sessionsDelta > 0 ? "+" : ""}${c.sessionsDelta} %)`);
  }
  if (c.leadsDelta != null) {
    parts.push(`leads : ${c.leadsRecent} contre ${c.leadsPrecedent} (${c.leadsDelta > 0 ? "+" : ""}${c.leadsDelta} %)`);
  }
  if (c.anomalieDetectee) parts.push("un trafic automatise a ete detecte recemment sur ce site");
  return `Periode recente analysee : ${c.periodeRecente}. Constat : ${parts.join(" ; ")}. Explique et evalue l'impact.`;
}

async function main() {
  const chemin = process.argv[2];
  if (!chemin) {
    console.error("Usage: node hermes_watch.js <chemin_candidats.json>");
    process.exit(1);
  }
  const { candidats } = JSON.parse(fs.readFileSync(chemin, "utf8"));
  console.log(`${candidats.length} site(s) retenu(s) par le pre-tri statistique.`);

  const constats = [];
  for (const c of candidats) {
    try {
      const brut = await askSpecialist(WATCH_SYSTEM, question(c), [c.site]);
      const { synthese, analyse } = decoupe(brut);
      constats.push({
        site: c.site,
        gravite: gravite(c),
        synthese, analyse,
        periodeRecente: c.periodeRecente,
        chiffres: {
          sessionsDelta: c.sessionsDelta, leadsDelta: c.leadsDelta, anomalieDetectee: c.anomalieDetectee,
          sessionsRecent: c.sessionsRecent, sessionsPrecedent: c.sessionsPrecedent,
          leadsRecent: c.leadsRecent, leadsPrecedent: c.leadsPrecedent,
        },
        genere_le: new Date().toISOString().slice(0, 10),
      });
      console.log(`  ${c.site} -- analyse generee (${gravite(c)}).`);
    } catch (e) {
      console.error(`  ${c.site} -- erreur d'analyse : ${e.message}`);
    }
  }

  const sortie = { derniere_execution: new Date().toISOString(), constats };
  const cheminSortie = path.join(process.cwd(), "data", "hermes_watch.json");
  fs.writeFileSync(cheminSortie, JSON.stringify(sortie));
  console.log(`ecrit ${cheminSortie} (${constats.length} constat(s))`);
}

main().catch(e => {
  console.error(e);
  process.exit(1);
});
