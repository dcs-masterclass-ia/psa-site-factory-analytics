// @ts-check
// Profil "limited" (GA4 / Search Console / PageSpeed uniquement) : l'interface
// masque les onglets leads et charge ses donnees via /api/data (simule ici
// avec le vrai nettoyeur api/_lib/limited.js, comme le fait le serveur).
const { test, expect } = require("@playwright/test");
const fs = require("fs");
const path = require("path");
const { stripLeads } = require("../../api/_lib/limited");

const DATA = path.join(__dirname, "..", "..", "data");

test.beforeEach(async ({ context, page }) => {
  await context.addCookies([
    { name: "psf_user_email", value: "limite%40autobiz.com", url: "http://localhost:8199" },
    { name: "psf_role", value: "limited", url: "http://localhost:8199" },
  ]);
  await page.route("**/api/data?f=*", async (route) => {
    const nom = new URL(route.request().url()).searchParams.get("f");
    const brut = JSON.parse(fs.readFileSync(path.join(DATA, nom + ".json"), "utf8"));
    await route.fulfill({ json: stripLeads(brut) });
  });
});

test.describe("profil limite", () => {
  test("charge via /api/data (jamais /data/ en direct) sans erreur JS", async ({ page }) => {
    const erreurs = [];
    const directs = [];
    page.on("pageerror", (e) => erreurs.push(e.message));
    page.on("request", (r) => { if (/\/data\/[^/]+\.json/.test(new URL(r.url()).pathname)) directs.push(r.url()); });
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.locator('div[title="Google Analytics 4"]').first()).toBeVisible();
    expect(directs, "le profil limite ne doit pas lire /data/ en direct").toEqual([]);
    expect(erreurs, erreurs.join(" | ")).toEqual([]);
  });

  test("masque Tableau, GCP, KamIA et le sous-onglet V2", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    for (const t of ["Google Analytics 4", "Search Console", "PageSpeed Insights"]) {
      await expect(page.locator(`div[title="${t}"]`).first()).toBeVisible();
    }
    for (const t of ["Tableau", "Google Cloud Platform"]) {
      await expect(page.locator(`div[title="${t}"]`)).toHaveCount(0);
    }
    await expect(page.locator('[data-chrome="chat"]')).toHaveCount(0);
    await expect(page.getByText("Acquisition", { exact: true }).first()).toBeVisible();
    await page.getByText("Conversion", { exact: true }).first().click();
    await expect(page.getByText("Fuites du tunnel", { exact: true })).toBeVisible();           // les vues GA4 restent accessibles
    await expect(page.getByText("Avant / après V2")).toHaveCount(0);                            // sauf la comparaison V2
    await page.getByText("Pilotage", { exact: true }).first().click();                            // alertes GA4 : oui ; objectifs (leads back-office) : non
    await expect(page.getByText("Alertes", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Objectifs", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Indisponible sur ce profil.")).toBeVisible();
  });

  test("les trois onglets autorises s'affichent sans erreur JS", async ({ page }) => {
    const erreurs = [];
    page.on("pageerror", (e) => erreurs.push(e.message));
    await page.goto("/", { waitUntil: "networkidle" });
    for (const t of ["Search Console", "PageSpeed Insights", "Google Analytics 4"]) {
      await page.locator(`div[title="${t}"]`).first().click();
      await page.waitForTimeout(400);
    }
    expect(erreurs, erreurs.join(" | ")).toEqual([]);
  });

  test("?source=tb est ignore : on reste sur GA4", async ({ page }) => {
    await page.goto("/?source=tb", { waitUntil: "networkidle" });
    await expect(page.getByText("Leads back-office")).toHaveCount(0);
    await expect(page.getByText("Taux de conversion").first()).toBeVisible();
  });
});
