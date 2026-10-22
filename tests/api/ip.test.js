// Filtre par adresse IP de middleware.js (ALLOWED_IPS) : le fichier est du JavaScript « module » sans package type=module,
// on l'évalue donc dans un contexte isolé (sans réseau). Lancer : node --test tests/api/
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

function charge(env) {
  let src = fs.readFileSync(path.resolve(__dirname, "../../middleware.js"), "utf8");
  src = src.replace("export const config", "const config").replace("export default async function middleware", "async function middleware");
  const ctx = { Response, URL, TextEncoder, crypto: globalThis.crypto, Intl, fetch: async () => ({ ok: false, status: 404 }), atob, Date, JSON, Number, String, Promise,
    process: { env }, console };
  return vm.runInNewContext(src + "\n({ middleware, config, ipAutorisee, ipClient, estProtege });", ctx);
}
const req = (url, ip, cookie) => new Request("https://converge.test" + url, { headers: Object.assign(ip ? { "x-forwarded-for": ip } : {}, cookie ? { cookie } : {}) });
const IPS = "203.0.113.5, 198.51.100.0/24 ,2001:db8::1";

test("sans ALLOWED_IPS, le filtre est inactif (page et données comme avant)", async () => {
  const m = charge({});
  assert.equal(await m.middleware(req("/", "8.8.8.8")), undefined);
  assert.equal((await m.middleware(req("/api/data?f=x", "8.8.8.8"))).status, 401);       // session exigée comme avant
});

test("adresse autorisée : exacte, dans un /24, IPv4 présentée en IPv6, IPv6 exacte", () => {
  const m = charge({});
  const liste = IPS.split(",").map(x => x.trim());
  for (const ip of ["203.0.113.5", "198.51.100.77", "::ffff:203.0.113.5", "2001:DB8::1"]) assert.equal(m.ipAutorisee(m.ipClient(req("/", ip)), liste), true, ip);
  for (const ip of ["203.0.113.6", "198.51.101.1", "8.8.8.8", "", "999.1.1.1"]) assert.equal(m.ipAutorisee(m.ipClient(req("/", ip)), liste), false, ip);
});

test("avec ALLOWED_IPS : la page, les scripts, l'API et les données sont fermés aux autres adresses", async () => {
  const m = charge({ ALLOWED_IPS: IPS });
  for (const u of ["/", "/index.html", "/support.js", "/api/auth", "/api/config", "/api/data?f=x", "/data/pipeline.json"]) {
    const r = await m.middleware(req(u, "8.8.8.8"));
    assert.equal(r.status, 403, u);
    assert.match(r.headers.get("content-type"), u.startsWith("/api") || u.startsWith("/data") ? /json/ : /html/);
  }
  assert.equal((await m.middleware(req("/", null))).status, 403);                           // adresse introuvable : refusé
});

test("avec ALLOWED_IPS : une adresse autorisée voit la page ; les routes protégées exigent toujours la session", async () => {
  const m = charge({ ALLOWED_IPS: IPS });
  assert.equal(await m.middleware(req("/", "203.0.113.5")), undefined);
  assert.equal(await m.middleware(req("/support.js", "198.51.100.9")), undefined);
  assert.equal(await m.middleware(req("/api/auth", "203.0.113.5")), undefined);              // route publique de connexion
  assert.equal((await m.middleware(req("/api/data?f=x", "203.0.113.5"))).status, 401);
});

test("seule la première valeur de x-forwarded-for compte (Vercel l'écrase côté serveur)", async () => {
  const m = charge({ ALLOWED_IPS: "203.0.113.5" });
  assert.equal((await m.middleware(req("/", "8.8.8.8, 203.0.113.5"))).status, 403);
  assert.equal(await m.middleware(req("/", "203.0.113.5, 8.8.8.8")), undefined);
});

test("la page de refus n'affiche que l'adresse du visiteur, nettoyée", async () => {
  const m = charge({ ALLOWED_IPS: "203.0.113.5" });
  const html = await (await m.middleware(req("/", "8.8.8.8<script>"))).text();
  assert.match(html, /Adresse detectee : 8\.8\.8\.8/);
  assert.doesNotMatch(html, /<script>/);
});
