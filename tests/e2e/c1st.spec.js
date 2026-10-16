// @ts-check
// Onglet C1ST : suivi des leads par les concessionnaires, depuis data/c1st/kpi.json (vrai fichier, pas de fixture).
const fs = require("fs");
const path = require("path");
const { test, expect } = require("@playwright/test");

const KPI = JSON.parse(fs.readFileSync(path.join(__dirname, "../../data/c1st/kpi.json"), "utf8"));
const nf = (n) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");

// période = le dernier mois ENTIER du fichier (le mois de la date de collecte est partiel), choisie dans le calendrier général
const PARTIEL = String((KPI.collecte || {}).date || "").slice(0, 7);
const MOIS = Object.keys(KPI.donnees.FR).sort().filter((m) => m !== PARTIEL).pop();
const DEBUT = MOIS + "-01";
const FIN = new Date(Date.UTC(+MOIS.slice(0, 4), +MOIS.slice(5, 7), 0)).toISOString().slice(0, 10);

test("C1ST : onglet, cartes, entonnoirs, évolution et chiffres du fichier", async ({ context, page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });   // pas de fenêtre « Du nouveau » devant les clics
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  // périmètre : un seul site (PEUGEOT FR), source C1ST
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate((s) => sessionStorage.setItem("psf_ui_state", JSON.stringify(s)), { source: "c1st", sites: ["PEUGEOT FR"], from: DEBUT, to: FIN, cmpMode: "none" });
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("Ce que deviennent les leads de reprise")).toBeVisible();
  await expect(page.getByText("Suivi par les concessionnaires")).toBeVisible();
  await expect(page.getByText("Du lead à la commande")).toBeVisible();
  await expect(page.getByText("Évolution mensuelle")).toBeVisible();
  await expect(page.getByText("Période, comparaison et sites")).toBeVisible();      // plus de sélecteurs propres : calendrier général
  await expect(page.getByText("Détail du périmètre")).toBeVisible();

  // chiffres : le mois affiché (dernier mois entier du fichier) doit redonner le total du fichier pour Peugeot France
  const ap = KPI.donnees.FR[MOIS].leads.find((r) => r.marque === "AP");
  await expect(page.getByText(nf(ap.leads), { exact: true }).first()).toBeVisible();
  expect(erreurs).toEqual([]);
});

test("C1ST : Spoticar affiché n.d. et exclu du total ; marques non suivies signalées", async ({ context, page }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });   // pas de fenêtre « Du nouveau » devant les clics
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate((s) => sessionStorage.setItem("psf_ui_state", JSON.stringify(s)), { source: "c1st", sites: ["PEUGEOT FR", "SPOTICAR FR", "LEAPMOTOR BE"], from: DEBUT, to: FIN, cmpMode: "none" });
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("n.d.").first()).toBeVisible();
  await expect(page.getByText("marques non suivies").first()).toBeVisible();      // Leapmotor : pas de suivi C1ST (les marchés DE / PL / AT / GB, eux, sont suivis)
});

test("C1ST : sans l'accès des Présentations (même liste d'adresses), pas d'onglet C1ST", async ({ context, page }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await expect(page.locator('div[title="C1ST"]')).toHaveCount(0);
  await expect(page.locator('div[title="AAA Data"]')).toHaveCount(1);
});

test("C1ST : Allemagne, Pologne, Autriche et Royaume-Uni sont suivis (mise en garde sur le suivi des concessionnaires)", async ({ context, page }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });   // pas de fenêtre « Du nouveau » devant les clics
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate((s) => sessionStorage.setItem("psf_ui_state", JSON.stringify(s)), { source: "c1st", sites: ["PEUGEOT DE", "CITROEN PL", "PEUGEOT AT"], from: DEBUT, to: FIN, cmpMode: "none" });
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText(/Suivi des concessionnaires quasi inexistant dans C1ST/)).toBeVisible();
  await expect(page.getByText(/site\(s\) sélectionné\(s\) non inclus/)).toHaveCount(0);       // plus de marché « hors C1ST » pour ces pays
});
