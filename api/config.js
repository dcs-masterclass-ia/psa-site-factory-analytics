/**
 * Expose au client les valeurs de configuration necessaires au flux Google
 * Sign-In. Le client ID OAuth n'est pas un secret (il est de toute facon
 * visible dans toute app cote client) mais reste pilote par variable
 * d'environnement plutot que code en dur, pour ne pas re-editer index.html
 * a chaque changement de projet Google Cloud.
 */

module.exports = async function handler(req, res) {
  // maintenance : MAINTENANCE=1 (variable Vercel). Lu par la page (voile + blocage)
  // et appliqué côté serveur par middleware.js (503 sur les données et les API).
  res.setHeader("Cache-Control", "no-store");
  res.status(200).json({
    googleClientId: process.env.GOOGLE_CLIENT_ID || null,
    maintenance: /^(1|true|oui)$/i.test(process.env.MAINTENANCE || ""),
  });
};
