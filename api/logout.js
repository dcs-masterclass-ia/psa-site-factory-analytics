module.exports = async function handler(req, res) {
  res.setHeader("Set-Cookie", [
    "psf_session=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0",
    "psf_user_email=; Path=/; Secure; SameSite=Lax; Max-Age=0",
  ]);
  res.status(200).json({ ok: true });
};
