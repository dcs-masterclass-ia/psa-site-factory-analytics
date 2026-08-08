/**
 * Wrappers fetch bruts vers l'API GitHub, pour l'Agent Dashboard uniquement
 * (creation de branche + PR). Utilise sciemment un jeton SEPARE
 * (GITHUB_PR_TOKEN) de celui d'api/refresh.js (GITHUB_TOKEN, volontairement
 * limite au scope "Actions" -- cf. commentaire en tete de ce fichier) : ce
 * nouvel usage a besoin de "Contents" et "Pull requests" en ecriture, un
 * scope plus large qu'on ne veut pas melanger avec le declenchement du
 * pipeline de donnees.
 */

const REPO = process.env.GITHUB_REPO || "dcs-masterclass-ia/psa-site-factory-analytics";
// meme principe que api/refresh.js : "main" en Production, la branche de la
// Preview (ex. "staging") ailleurs -- l'Agent Dashboard invoque depuis une
// Preview cree sa branche et sa PR contre CETTE branche, jamais contre main.
const BASE_REF = process.env.VERCEL_GIT_COMMIT_REF || "main";

function authHeaders() {
  const token = process.env.GITHUB_PR_TOKEN;
  if (!token) throw new Error("GITHUB_PR_TOKEN non configure sur le serveur.");
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

async function api(pathSuffix, opts = {}) {
  const r = await fetch(`https://api.github.com/repos/${REPO}${pathSuffix}`, {
    ...opts,
    headers: { ...authHeaders(), "content-type": "application/json", ...(opts.headers || {}) },
  });
  const text = await r.text();
  let json = null;
  try { json = text ? JSON.parse(text) : null; } catch (e) { /* reponse non-JSON */ }
  if (!r.ok) {
    const detail = (json && json.message) || text || r.statusText;
    throw new Error(`GitHub API ${pathSuffix} : ${r.status} ${detail}`);
  }
  return json;
}

async function getDefaultBranchSha() {
  const ref = await api(`/git/ref/heads/${BASE_REF}`);
  return ref.object.sha;
}

async function getFile(filePath, ref = BASE_REF) {
  const data = await api(`/contents/${filePath}?ref=${encodeURIComponent(ref)}`);
  const content = Buffer.from(data.content, "base64").toString("utf8");
  return { content, sha: data.sha };
}

async function createBranch(branchName) {
  const sha = await getDefaultBranchSha();
  await api("/git/refs", {
    method: "POST",
    body: JSON.stringify({ ref: `refs/heads/${branchName}`, sha }),
  });
  return sha;
}

async function updateFile(filePath, branchName, content, sha, message) {
  await api(`/contents/${filePath}`, {
    method: "PUT",
    body: JSON.stringify({
      message,
      content: Buffer.from(content, "utf8").toString("base64"),
      sha,
      branch: branchName,
    }),
  });
}

async function createPullRequest(branchName, title, body) {
  const pr = await api("/pulls", {
    method: "POST",
    body: JSON.stringify({ title, head: branchName, base: BASE_REF, body }),
  });
  return { url: pr.html_url, number: pr.number };
}

module.exports = { getFile, createBranch, updateFile, createPullRequest };
