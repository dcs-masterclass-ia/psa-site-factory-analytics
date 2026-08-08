/**
 * Declenche le workflow "Rafraichissement automatique des donnees" sur
 * GitHub Actions, sans jamais exposer de jeton au navigateur.
 *
 * Le jeton GITHUB_TOKEN vit UNIQUEMENT dans les variables d'environnement
 * Vercel (Project Settings -> Environment Variables). Il n'apparait jamais
 * dans le code livre au client -- c'est cette fonction, executee sur les
 * serveurs de Vercel, qui l'utilise pour appeler l'API GitHub.
 *
 * Portee minimale requise pour le jeton :
 *   - un jeton fin (fine-grained) limite a CE depot
 *   - permission "Actions" en Lecture et ecriture
 *   - aucune autre permission (surtout pas "Contents" en ecriture)
 *
 * Variables d'environnement Vercel a creer :
 *   GITHUB_TOKEN   le jeton fin decrit ci-dessus
 *   GITHUB_REPO    dcs-masterclass-ia/psa-site-factory-analytics (optionnel,
 *                  valeur par defaut ci-dessous)
 */

const REPO = process.env.GITHUB_REPO || "dcs-masterclass-ia/psa-site-factory-analytics";
const WORKFLOW = "refresh.yml";
// VERCEL_GIT_COMMIT_REF (fournie automatiquement par Vercel a chaque
// deploiement) vaut "main" en Production et le nom de la branche sur une
// Preview -- le bouton "Actualiser" clique depuis la Preview "staging"
// declenche donc deja refresh.yml --ref staging, qui (voir build.py et les
// autres workflows) n'ecrit alors que sur staging, jamais sur main.
const REF = process.env.VERCEL_GIT_COMMIT_REF || "main";

// garde-fou anti-abus : pas de nouveau declenchement si le precedent date de
// moins de 2 minutes, ou est encore en cours. Aucun stockage necessaire : on
// interroge simplement le dernier run connu de GitHub.
const DELAI_MIN_MS = 2 * 60 * 1000;

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Methode non autorisee." });
    return;
  }

  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    res.status(500).json({ error: "GITHUB_TOKEN n'est pas configure sur le serveur." });
    return;
  }

  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };

  try {
    const runsResp = await fetch(
      `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/runs?per_page=1`,
      { headers }
    );
    const runsJson = await runsResp.json();
    const dernier = runsJson.workflow_runs && runsJson.workflow_runs[0];

    if (dernier) {
      const age = Date.now() - new Date(dernier.created_at).getTime();
      if (dernier.status === "in_progress" || dernier.status === "queued") {
        res.status(429).json({
          error: "Un rafraichissement est deja en cours.",
          run_url: dernier.html_url,
        });
        return;
      }
      if (age < DELAI_MIN_MS) {
        res.status(429).json({
          error: "Un rafraichissement vient d'etre lance, merci de patienter quelques minutes.",
          run_url: dernier.html_url,
        });
        return;
      }
    }

    const dispatch = await fetch(
      `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({ ref: REF, inputs: { simulation: "non", sites: "" } }),
      }
    );

    if (dispatch.status !== 204) {
      const detail = await dispatch.text();
      res.status(502).json({ error: "GitHub a refuse le declenchement.", detail });
      return;
    }

    res.status(200).json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: String(e && e.message ? e.message : e) });
  }
};
