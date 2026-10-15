// @ts-check
// Onglet C1ST : suivi des leads par les concessionnaires, depuis data/c1st/kpi.json (vrai fichier, pas de fixture).
const fs = require("fs");
const path = require("path");
const { test, expect } = require("@playwright/test");

const KPI = JSON.parse(fs.readFileSync(path.join(__dirname, "../../data/c1st/kpi.json"), "utf8"));
const nf = (n) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");

test("C1ST : onglet, cartes, entonnoirs, évolution et chiffres du fichier", async ({ context, page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  // périmètre : un seul site (PEUGEOT FR), source C1ST
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate(() => sessionStorage.setItem("psf_ui_state", JSON.stringify({ source: "c1st", sites: ["PEUGEOT FR"] })));
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("Ce que deviennent les leads de reprise")).toBeVisible();
  await expect(page.getByText("Suivi par les concessionnaires")).toBeVisible();
  await expect(page.getByText("Du lead à la commande")).toBeVisible();
  await expect(page.getByText("Évolution mensuelle")).toBeVisible();
  await expect(page.getByText("Détail du périmètre")).toBeVisible();

  // chiffres : le mois affiché (dernier mois entier du fichier) doit redonner le total du fichier pour Peugeot France
  const partiel = String((KPI.collecte || {}).date || "").slice(0, 7);
  const mois = Object.keys(KPI.donnees.FR).sort().filter((m) => m !== partiel).pop();
  const ap = KPI.donnees.FR[mois].leads.find((r) => r.marque === "AP");
  await expect(page.getByText(nf(ap.leads), { exact: true }).first()).toBeVisible();
  expect(erreurs).toEqual([]);
});

test("C1ST : Spoticar affiché n.d. et exclu du total ; sites hors C1ST signalés", async ({ context, page }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate(() => sessionStorage.setItem("psf_ui_state", JSON.stringify({ source: "c1st", sites: ["PEUGEOT FR", "SPOTICAR FR", "PEUGEOT DE"] })));
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("n.d.").first()).toBeVisible();
  await expect(page.getByText("marchés hors C1ST").first()).toBeVisible();
});
