/**
 * Lance un workflow GitHub Actions du repo de code (workflow_dispatch) pour qu'un ticket soit traité tout de suite, sans attendre
 * le passage planifié (non fiable). Nécessite GH_DISPATCH_TOKEN (jeton limité à ce repo, droit « Actions : lecture/écriture »).
 * Sans jeton ou en cas d'erreur : renvoie false, le passage planifié prend le relais. Jamais bloquant.
 */
const REPO = "dcs-masterclass-ia/psa-site-factory-analytics";

async function lance(workflow) {
  const token = process.env.GH_DISPATCH_TOKEN;
  if (!token) return false;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 4000);
    const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/dispatches`, {
      method: "POST", signal: ctrl.signal,
      headers: { authorization: `Bearer ${token}`, accept: "application/vnd.github+json", "x-github-api-version": "2022-11-28", "content-type": "application/json" },
      body: JSON.stringify({ ref: "main" }),
    });
    clearTimeout(t);
    return r.status === 204;
  } catch (e) {
    console.error("[dispatch]", workflow, e && e.message);
    return false;
  }
}

module.exports = { lance };
