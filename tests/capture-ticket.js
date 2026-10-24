// Capture ciblée de la section modifiée par un ticket (livraison autonome).
// Lit ticket-capture.json {nav:[textes à cliquer], texte:"titre de la section"} à la racine du repo, sert le dashboard en
// local (python http.server déjà lancé sur le port 8199) et écrit ticket-capture.png : la CARTE de la section, jamais l'écran entier.
const { chromium } = require("@playwright/test");
const fs = require("fs");
const path = require("path");

(async () => {
  const racine = path.resolve(__dirname, "..");
  const cfg = JSON.parse(fs.readFileSync(path.join(racine, "ticket-capture.json"), "utf8"));
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1700 } });
  await ctx.addCookies([{ name: "psf_user_email", value: "e2e%40exemple.test", url: "http://localhost:8199" }]);
  const page = await ctx.newPage();
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.goto("http://localhost:8199/", { waitUntil: "networkidle" });
  for (const t of cfg.nav || []) await page.getByText(t, { exact: true }).first().click({ timeout: 5000 });
  await page.evaluate(() => {
    document.querySelectorAll("*").forEach((e) => {
      const cs = getComputedStyle(e);
      if (cs.position === "fixed") { const r = e.getBoundingClientRect(); if (r.width < 320 && r.height < 90 && /KamIA/.test(e.textContent)) e.style.visibility = "hidden"; }
    });
  });
  const h = await page.getByText(cfg.texte).first().elementHandle();
  const carte = await page.evaluateHandle((el) => {
    let e = el;
    while (e.parentElement) {
      e = e.parentElement;
      const cs = getComputedStyle(e);
      if (e.getBoundingClientRect().width > 700 && parseFloat(cs.borderTopLeftRadius) >= 16 && cs.backgroundColor === "rgb(255, 255, 255)") return e;
    }
    return el;
  }, h);
  await carte.asElement().scrollIntoViewIfNeeded();
  await page.waitForTimeout(600);
  await carte.asElement().screenshot({ path: path.join(racine, "ticket-capture.png") });
  await browser.close();
})().catch((e) => { console.error("capture impossible :", e.message); process.exit(1); });
