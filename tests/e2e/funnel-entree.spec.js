// @ts-check
// GA4 > tunnel de conversion : pastilles Tous / Immatriculation / Marque-modèle (funnelEntree ajouté à la volée sur la réponse réelle de data/peugeot-fr.json).
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });
});

const TOUS = [1000, 400, 380, 370, 200, 160], MM = [50, 40, 38, 36, 14, 8];       // Version -> estimation : tous 40 %, marque/modèle 20 %, immatriculation (160-8)/(400-40) = 42,2 %

test("tunnel : pastilles par mode de saisie, barres à partir de « Version », comparaison des trois", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.route("**/data/peugeot-fr.json", async (route) => {
    const d = await (await route.fetch()).json();
    d.funnelEntree = {};
    for (const m of d.months || []) d.funnelEntree[m] = { tous: TOUS, marque_modele: MM };
    await route.fulfill({ json: d });
  });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate(() => sessionStorage.setItem("psf_ui_state", JSON.stringify({ source: "ga", tab: "dash", sites: ["PEUGEOT FR"], from: null, to: null, cmpMode: "none" })));
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("Tous les parcours", { exact: true })).toBeVisible();
  await expect(page.getByText(/De « Version » à l'estimation : Tous [\d,]+ % · Immatriculation [\d,]+ % · Marque \/ modèle [\d,]+ %/)).toBeVisible();
  await expect(page.getByText("Accueil → Leads GA · 6 étapes")).toBeVisible();
  await page.getByText("Marque / modèle", { exact: true }).first().click();
  await expect(page.getByText("Version → Leads GA · 5 étapes")).toBeVisible();
  await expect(page.getByText("Page d'accueil", { exact: true })).toHaveCount(0);                    // le mode ne se lit pas à l'accueil
  await page.getByText("Immatriculation", { exact: true }).first().click();
  await expect(page.getByText("visiteurs du parcours immatriculation")).toBeVisible();
  await page.getByText("Tous les parcours", { exact: true }).click();
  await expect(page.getByText("Page d'accueil", { exact: true }).first()).toBeVisible();
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});
