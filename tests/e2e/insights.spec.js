// @ts-check
// Carte « Insights » du tableau de bord GA4 : constats calculés (insights.js), « Creuser avec KamIA » envoie la question à l'agent.
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context, page }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
});
const ouvre = async (page, sites) => {
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate((s) => sessionStorage.setItem("psf_ui_state", JSON.stringify({ source: "ga", sites: s, from: null, to: null, cmpMode: "previous" })), sites);
  await page.reload({ waitUntil: "networkidle" });
};

test("insights : constats chiffrés avec impact en leads, plus de faux « Analyse IA · il y a 4 min »", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await ouvre(page, ["OPEL FR"]);
  await expect(page.getByText("Insights", { exact: true })).toBeVisible();
  await expect(page.getByText(/Calculés sur les données affichées · vs période précédente · \d\d\/\d\d/)).toBeVisible();
  await expect(page.getByText(/il y a 4 min/)).toHaveCount(0);
  await expect(page.getByText(/^(ALERTE|CAUSE|OPPORTUNITÉ)$/).first()).toBeVisible();
  await expect(page.getByText(/^(≈ )?[+−][\d  ,]+ leads( potentiels)?$/).first()).toBeVisible();      // l'impact chiffré de chaque insight
  await expect(page.getByText(/Leads GA [+−]/).first()).toBeVisible();                                      // décomposition trafic / conversion
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("« Creuser avec KamIA » ouvre le panneau et envoie le constat à l'agent avec le contexte", async ({ page }) => {
  const appels = [];
  await page.route("**/api/kamia-conversations", (r) => r.fulfill({ json: { conversations: [] } }));
  await page.route("**/api/agent", async (r) => { appels.push(JSON.parse(r.request().postData() || "{}")); await r.fulfill({ json: { answer: "Voici les causes probables.", verifie: true, agentsConsultes: ["Données"], charts: [], history: [] } }); });
  await ouvre(page, ["OPEL FR"]);
  await page.getByText("Creuser avec KamIA").first().click();
  await expect(page.getByText("Voici les causes probables.")).toBeVisible();
  expect(appels.length).toBe(1);
  expect(appels[0].question).toMatch(/Explique les causes probables/);
  expect(appels[0].question).toMatch(/Leads GA|conversion|sessions/);
  expect(appels[0].scope).toEqual(["OPEL FR"]);
});

test("insights en anglais : textes calculés en anglais, aucun accent français résiduel", async ({ page }) => {
  await ouvre(page, ["OPEL FR"]);
  await page.getByRole("group", { name: "Langue" }).getByText("EN", { exact: true }).click();
  await expect(page.getByText("Dig deeper with KamIA").first()).toBeVisible();
  const carte = await page.evaluate(() => { const c = [...document.querySelectorAll(".psf-card")].find((e) => e.textContent.includes("Insights")); return c ? c.innerText : ""; });
  expect(carte).toMatch(/GA leads [+−]/);
  expect(/[éèêàù]/.test(carte)).toBe(false);
});

test("« Voir le détail » change de vue d'analyse et amène l'écran dessus (la vue est sous la carte)", async ({ page }) => {
  await ouvre(page, ["OPEL FR"]);
  await page.evaluate(() => { const z = document.getElementById("gaAnalyses").closest("div[style*='overflow-y']"); window.__zone = z; z.scrollTop = 0; });
  const avant = await page.evaluate(() => document.getElementById("gaAnalyses").getBoundingClientRect().top);
  expect(avant).toBeGreaterThan(400);                                                          // sous la ligne de flottaison
  await page.getByText("Voir le détail →").first().click();
  await expect.poll(() => page.evaluate(() => document.getElementById("gaAnalyses").getBoundingClientRect().top), { timeout: 5000 }).toBeLessThan(300);   // l'écran a défilé
});

test("« Voir le détail » d'un insight de canal ouvre la vue « Évolution du trafic reprise par canal »", async ({ page }) => {
  await ouvre(page, ["PEUGEOT FR"]);
  const titre = page.getByText(/trafic (en hausse|en recul)$/).first();
  test.skip((await titre.count()) === 0, "pas d'insight de canal sur ce jeu de données");
  await titre.locator("xpath=following::span[contains(.,'Voir le détail')][1]").click();
  await expect(page.getByText("Évolution du trafic reprise par canal").first()).toBeVisible();
});

test("« Voir le détail » d'un insight de segment ouvre la vue canal × appareil (marché entier)", async ({ page }) => {
  await page.goto("/", { waitUntil: "networkidle" });
  const titre = page.getByText(/à développer$/).first();
  test.skip((await titre.count()) === 0, "pas d'insight de segment sur ce jeu de données");
  await titre.locator("xpath=following::span[contains(.,'Voir le détail')][1]").click();
  await expect(page.getByText(/^Conversion par canal et appareil/).first()).toBeVisible();
});
