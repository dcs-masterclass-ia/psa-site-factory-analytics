/**
 * Petit magasin cle/JSON adosse au repo de donnees prive
 * (dcs-masterclass-ia/psa-site-factory-data), via l'API Contents de GitHub.
 * Sert aujourd'hui a persister l'historique des conversations KamIA par
 * profil connecte (api/kamia-conversations.js).
 *
 * Reutilise sciemment DATA_REPO_TOKEN (deja configure pour scripts/fetch-data.sh,
 * en lecture) : il doit desormais porter "Contents: Read and write" sur ce
 * seul repo. Aucun melange avec GITHUB_TOKEN (pipeline, scope Actions) ni
 * GITHUB_PR_TOKEN (repo de code, PR de l'Agent Dashboard).
 *
 * Variables d'environnement Vercel :
 *   DATA_REPO_TOKEN     PAT fine-grained, Contents RW sur psa-site-factory-data
 *   KAMIA_STORE_REPO    optionnel, defaut "dcs-masterclass-ia/psa-site-factory-data"
 *   KAMIA_STORE_BRANCH  optionnel, defaut "main" (politique prod-direct du repo)
 */

const REPO = process.env.KAMIA_STORE_REPO || "dcs-masterclass-ia/psa-site-factory-data";
const BRANCH = process.env.KAMIA_STORE_BRANCH || "main";

function authHeaders() {
  const token = process.env.DATA_REPO_TOKEN;
  if (!token) throw new Error("DATA_REPO_TOKEN non configure sur le serveur.");
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

async function ghFetch(pathSuffix, opts = {}) {
  const r = await fetch(`https://api.github.com/repos/${REPO}${pathSuffix}`, {
    ...opts,
    headers: { ...authHeaders(), "content-type": "application/json", ...(opts.headers || {}) },
  });
  const text = await r.text();
  let json = null;
  try { json = text ? JSON.parse(text) : null; } catch (e) { /* non-JSON */ }
  return { ok: r.ok, status: r.status, json, text };
}

/**
 * Lit un fichier JSON du magasin. Renvoie { data, sha }. Un fichier absent
 * n'est pas une erreur : { data: null, sha: null }.
 */
async function readJson(filePath) {
  const res = await ghFetch(`/contents/${encodeURIComponent(filePath).replace(/%2F/g, "/")}?ref=${encodeURIComponent(BRANCH)}`);
  if (res.status === 404) return { data: null, sha: null };
  if (!res.ok) {
    const detail = (res.json && res.json.message) || res.text || res.status;
    throw new Error(`store.readJson(${filePath}) : ${res.status} ${detail}`);
  }
  let data = null;
  try {
    data = JSON.parse(Buffer.from(res.json.content, "base64").toString("utf8"));
  } catch (e) {
    // fichier corrompu : on le traite comme vide plutot que de bloquer
    // l'utilisateur -- le prochain writeJson l'ecrasera proprement.
    data = null;
  }
  return { data, sha: res.json.sha };
}

/**
 * Ecrit (cree ou remplace) un fichier JSON. Gere les collisions de sha
 * (deux onglets qui poussent en meme temps) : sur 409, relit le sha et
 * reessaie, jusqu'a 3 fois -- last-write-wins par profil, ce qui est le
 * bon compromis ici (un meme utilisateur ecrit rarement depuis 2 onglets
 * a la milliseconde).
 */
async function writeJson(filePath, dataObj, message, knownSha) {
  const body = JSON.stringify(dataObj, null, 0);
  const contentB64 = Buffer.from(body, "utf8").toString("base64");
  let sha = knownSha;

  for (let attempt = 0; attempt < 3; attempt++) {
    if (sha === undefined) {
      const cur = await readJson(filePath);
      sha = cur.sha || null;
    }
    const res = await ghFetch(`/contents/${encodeURIComponent(filePath).replace(/%2F/g, "/")}`, {
      method: "PUT",
      body: JSON.stringify({
        message,
        content: contentB64,
        branch: BRANCH,
        ...(sha ? { sha } : {}),
      }),
    });
    if (res.ok) return { sha: res.json && res.json.content && res.json.content.sha };
    if (res.status === 409 || res.status === 422) {
      // sha perime : on force une relecture au tour suivant
      sha = undefined;
      continue;
    }
    const detail = (res.json && res.json.message) || res.text || res.status;
    throw new Error(`store.writeJson(${filePath}) : ${res.status} ${detail}`);
  }
  throw new Error(`store.writeJson(${filePath}) : conflit de version persistant apres 3 tentatives.`);
}

module.exports = { readJson, writeJson, REPO, BRANCH };
