// @ts-check
// Search Console > Analyses détaillées : navigation par questions, toutes les vues s'affichent (données présentes ou état vide), même hauteur.
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
});

const VUES = [
  ["Visibilité", "Positions", "Distribution des positions"],
  ["Visibilité", "Appareils", "Appareils"],
  ["Visibilité", "Marque / hors marque", "Marque / hors marque"],
  ["Requêtes", "Top requêtes", "Requêtes"],
  ["Requêtes", "Gagnantes & perdantes", "Requêtes gagnantes et perdantes"],
  ["Requêtes", "Opportunités", "Opportunités SEO"],
  ["Requêtes", "Cannibalisation", "Cannibalisation"],
  ["Pages", "Top pages", "Pages"],
  ["Pages", "Pages en déclin", "Pages en déclin"],
  ["Pages", "Du clic à l'estimation", "Du clic à l'estimation"],
  ["Technique", "Indexation", "Indexation des pages principales"],
  ["Comparer", "Deux périodes", "Comparer deux périodes"],
];

test("analyses détaillées Search Console : 12 vues, une carte de même hauteur, aucune erreur JS", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.route("**/api/indexation", (r) => r.fulfill({ json: { genere: "2026-10-05", sites: {} } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('div[title="Search Console"]').first().click();
  await expect(page.getByText("Où apparaît-on ?")).toBeVisible();
  const hauteur = async () => page.evaluate(() => { const t = [...document.querySelectorAll("span")].find((s) => s.textContent.trim() === "Analyses détaillées"); return Math.round(t.parentElement.nextElementSibling.nextElementSibling.getBoundingClientRect().height); });
  const h0 = await hauteur();
  for (const [theme, vue, titre] of VUES) {
    await page.getByText(theme, { exact: true }).first().click();
    await page.getByText(vue, { exact: true }).first().click();
    await expect(page.getByText(titre).first()).toBeVisible();
    await page.waitForTimeout(250);
    expect(await hauteur(), `hauteur de la vue « ${vue} »`).toBeGreaterThanOrEqual(h0);
  }
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});
