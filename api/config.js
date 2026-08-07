/**
 * Expose au client les valeurs de configuration necessaires au flux Google
 * Sign-In. Le client ID OAuth n'est pas un secret (il est de toute facon
 * visible dans toute app cote client) mais reste pilote par variable
 * d'environnement plutot que code en dur, pour ne pas re-editer index.html
 * a chaque changement de projet Google Cloud.
 */

module.exports = async function handler(req, res) {
  res.status(200).json({ googleClientId: process.env.GOOGLE_CLIENT_ID || null });
};
