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
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40exemple.test", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
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
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40exemple.test", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });   // pas de fenêtre « Du nouveau » devant les clics
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate((s) => sessionStorage.setItem("psf_ui_state", JSON.stringify(s)), { source: "c1st", sites: ["PEUGEOT FR", "SPOTICAR FR", "LEAPMOTOR BE"], from: DEBUT, to: FIN, cmpMode: "none" });
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("n.d.").first()).toBeVisible();
  await expect(page.getByText("marques non suivies").first()).toBeVisible();      // Leapmotor : pas de suivi C1ST (les marchés DE / PL / AT / GB, eux, sont suivis)
});

test("C1ST : sans l'accès des Présentations (même liste d'adresses), pas d'onglet C1ST", async ({ context, page }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40exemple.test", url: "http://localhost:8199" }]);
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await expect(page.locator('div[title="C1ST"]')).toHaveCount(0);
  await expect(page.locator('div[title="AAA Data"]')).toHaveCount(1);
});

test("C1ST : Allemagne, Pologne, Autriche et Royaume-Uni sont suivis (mise en garde sur le suivi des concessionnaires)", async ({ context, page }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40exemple.test", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });   // pas de fenêtre « Du nouveau » devant les clics
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate((s) => sessionStorage.setItem("psf_ui_state", JSON.stringify(s)), { source: "c1st", sites: ["PEUGEOT DE", "CITROEN PL", "PEUGEOT AT"], from: DEBUT, to: FIN, cmpMode: "none" });
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText(/Suivi des concessionnaires quasi inexistant dans C1ST/)).toBeVisible();
  await expect(page.getByText(/site\(s\) sélectionné\(s\) non inclus/)).toHaveCount(0);       // plus de marché « hors C1ST » pour ces pays
});

test("C1ST : onglet « Leads Funnel » avec les six graphiques de C1ST et les taux clés face à la comparaison", async ({ context, page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40exemple.test", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate((s) => sessionStorage.setItem("psf_ui_state", JSON.stringify(s)), { source: "c1st", sites: ["PEUGEOT FR"], from: DEBUT, to: FIN, cmpMode: "previous" });
  await page.reload({ waitUntil: "networkidle" });
  for (const titre of ["Leads générés par mois", "Leads par statut", "1er appel dans les délais", "Contactés", "Avec devis", "Commandes NSC"]) {
    await expect(page.locator("div", { hasText: new RegExp("^" + titre + "i") }).first()).toBeVisible();      // le titre porte une pastille « i » (+ son infobulle)
  }
  await expect(page.getByText("Taux clés face à la comparaison")).toBeVisible();
  // survol : chaque graphique donne le détail du mois sous la souris (barres des leads, 4 courbes de taux)
  for (const [id, texte] of [["c1h_b", "Clients envoyés"], ["c1h_p", "Clients envoyés"], ["c1h_c", "Clients contactés"], ["c1h_d", "Clients avec devis"], ["c1h_o", "Commandes NSC"]]) {
    const boite = page.locator("#" + id);
    await boite.scrollIntoViewIfNeeded();
    const b = await boite.boundingBox();
    await page.mouse.move(b.x + b.width * 0.86, b.y + b.height * 0.55);
    await expect(page.locator("#chartHovTip")).toContainText(texte);
  }
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("C1ST : sans données par contrat, pas d'onglet « Leads Network Vision »", async ({ context, page }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40exemple.test", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.route("**/data/c1st/reseau.json", (r) => r.fulfill({ status: 404, body: "" }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate((s) => sessionStorage.setItem("psf_ui_state", JSON.stringify(s)), { source: "c1st", sites: ["PEUGEOT FR"], from: DEBUT, to: FIN, cmpMode: "none" });
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("Leads générés par mois").first()).toBeVisible();
  await expect(page.getByText("Leads Network Vision", { exact: true })).toHaveCount(0);
});

test("C1ST : onglet « Leads Network Vision » (bandeau, entonnoir, contrats à traiter, tableau par contrat)", async ({ context, page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40exemple.test", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  const contrats = [
    { pays: "FR", marque: "AP", code: "0000013", nom: "MSCAR TEST", leads: 120, clients: 100, fca: 80, tot: 70, tov: 5, tr: 75, cot: 60, cov: 5, c: 65, eso: 0, es: 0, q: 30, o: 7, rel: 3 },
    { pays: "FR", marque: "AP", code: "0000022", nom: "SILENCE TEST", leads: 70, clients: 60, fca: 2, tot: 1, tov: 0, tr: 1, cot: 1, cov: 0, c: 2, eso: 0, es: 0, q: 5, o: 0, rel: 1 },
  ];
  await page.route("**/data/c1st/reseau.json", (r) => r.fulfill({ json: { collecte: { date: "2026-10-18" }, contrats, commandes: [{ lead: "LEAD-A1", commande: "CMD-B2", code: "0000013", pays: "FR", marque: "AP", cree: "2026-10-02", jours: 12 }] } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate((s) => sessionStorage.setItem("psf_ui_state", JSON.stringify(s)), { source: "c1st", c1Onglet: "reseau", sites: ["PEUGEOT FR"], from: DEBUT, to: FIN, cmpMode: "none" });
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("UNIQUE LEADS")).toBeVisible();
  await expect(page.getByText("160", { exact: true }).first()).toBeVisible();                 // 100 + 60 clients uniques envoyés
  await expect(page.getByText("Summary Table")).toBeVisible();
  await expect(page.getByText("MSCAR TEST", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("À traiter en priorité").first()).toBeVisible();                // SILENCE TEST : 60 clients, 3 % contactés
  await expect(page.getByText("SILENCE TEST").first()).toBeVisible();
  await expect(page.getByText("À traiter", { exact: true }).first()).toBeVisible();           // verdict de suivi du contrat SILENCE TEST (traités à l'heure < 70 %)
  await page.getByText("MSCAR TEST", { exact: true }).last().click();                        // clic sur la ligne : détail complet
  await expect(page.getByText("Traités hors délais").first()).toBeVisible();
  await expect(page.getByText("LEAD-A1", { exact: false }).first()).toBeVisible();           // lien lead -> commande (identifiants seulement)
  // retour sur Leads Funnel
  await page.getByText("Leads Funnel", { exact: true }).click();
  await expect(page.getByText("Leads générés par mois").first()).toBeVisible();
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("C1ST : code d'accès mensuel requis, l'onglet se déverrouille avec le bon code", async ({ context, page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40exemple.test", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });
  let ouvert = false, essais = 0;
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.route("**/api/c1st-acces", async (r) => {
    if (r.request().method() !== "POST") return r.fulfill({ json: { ouvert, admin: false } });
    essais++;
    const bon = JSON.parse(r.request().postData() || "{}").code === "BON-CODE";
    if (bon) ouvert = true;
    await r.fulfill({ status: bon ? 200 : 403, json: bon ? { ouvert: true } : { error: "Code incorrect." } });
  });
  await page.route("**/data/c1st/kpi.json", (r) => (ouvert ? r.fallback() : r.fulfill({ status: 403, json: { error: "Code d'acces C1ST requis.", code: "c1st_code" } })));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate((s) => sessionStorage.setItem("psf_ui_state", JSON.stringify(s)), { source: "c1st", sites: ["PEUGEOT FR"], from: DEBUT, to: FIN, cmpMode: "none" });
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("Code d'accès C1ST")).toBeVisible();
  await expect(page.getByText("Du lead envoyé à la commande")).toHaveCount(0);                 // aucune donnée tant que le code n'est pas bon
  await page.getByPlaceholder("XXXXX-XXXXX").fill("FAUX");
  await page.getByText("Déverrouiller", { exact: true }).click();
  await expect(page.getByText("Code incorrect.")).toBeVisible();
  await page.getByPlaceholder("XXXXX-XXXXX").fill("BON-CODE");
  await page.getByText("Déverrouiller", { exact: true }).click();
  await expect(page.getByText("Code d'accès C1ST")).toHaveCount(0);
  await expect(page.getByText("Évolution mensuelle").first()).toBeVisible();
  expect(essais).toBe(2);
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("C1ST : l'administrateur voit le code du mois et peut révoquer les accès (avec confirmation)", async ({ context, page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40exemple.test", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });
  const appels = [];
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.route("**/api/c1st-acces**", async (r) => {
    const req = r.request(); appels.push(req.method() + " " + (req.postData() || req.url().split("?")[1] || ""));
    if (req.method() === "POST") return r.fulfill({ json: { ouvert: true, code: "NEUF1-NEUF2" } });
    return r.fulfill({ json: req.url().includes("code=1") ? { code: "ABCDE-FGHJK" } : { ouvert: true, admin: true } });
  });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate((s) => sessionStorage.setItem("psf_ui_state", JSON.stringify(s)), { source: "c1st", sites: ["PEUGEOT FR"], from: DEBUT, to: FIN, cmpMode: "none" });
  await page.reload({ waitUntil: "networkidle" });
  await page.getByText("Voir le code du mois").click();
  await expect(page.getByText("ABCDE-FGHJK")).toBeVisible();
  await page.getByText("Révoquer tous les accès").click();
  expect(appels.some((a) => a.startsWith("POST"))).toBe(false);                                 // premier clic = demande de confirmation seulement
  await page.getByText(/Confirmer : tout le monde/).click();
  await expect(page.getByText("NEUF1-NEUF2")).toBeVisible();
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("C1ST : verrouillage automatique après 5 minutes sans activité, et bouton « Verrouiller »", async ({ context, page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40exemple.test", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });
  const appels = [];
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.route("**/api/c1st-acces", async (r) => { appels.push(r.request().method()); await r.fulfill({ json: { ouvert: true, admin: false } }); });
  await page.clock.install();
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate((s) => sessionStorage.setItem("psf_ui_state", JSON.stringify(s)), { source: "c1st", sites: ["PEUGEOT FR"], from: DEBUT, to: FIN, cmpMode: "none" });
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("Évolution mensuelle").first()).toBeVisible();
  await page.clock.fastForward(4 * 60 * 1000);                                                   // 4 min sans bouger : toujours ouvert
  await expect(page.getByText("Évolution mensuelle").first()).toBeVisible();
  await page.clock.fastForward(2 * 60 * 1000);                                                   // 6 min : verrouillé
  await expect(page.getByText("Code d'accès C1ST")).toBeVisible();
  await expect(page.getByText("Évolution mensuelle")).toHaveCount(0);
  expect(appels).toContain("DELETE");
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("C1ST : le bouton « Verrouiller » ferme tout de suite, sans mention de durée", async ({ context, page }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40exemple.test", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.route("**/api/c1st-acces", async (r) => { await new Promise((x) => setTimeout(x, 1500)); await r.fulfill({ json: { ouvert: true, admin: false } }); });   // réseau lent : l'écran ne doit pas attendre
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate((s) => sessionStorage.setItem("psf_ui_state", JSON.stringify(s)), { source: "c1st", sites: ["PEUGEOT FR"], from: DEBUT, to: FIN, cmpMode: "none" });
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText(/5 minutes/)).toHaveCount(0);
  await page.getByText("Verrouiller", { exact: true }).click();
  await expect(page.getByText("Code d'accès C1ST")).toBeVisible({ timeout: 700 });
});

test("C1ST : F12 ou clic droit verrouille aussitôt l'onglet et trace la tentative", async ({ context, page }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40exemple.test", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });
  const alertes = [];
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.route("**/api/c1st-acces", async (r) => {
    const req = r.request();
    if (req.method() === "POST" && (req.postData() || "").includes("alerte")) alertes.push(req.postData());
    await r.fulfill({ json: { ouvert: true, admin: false } });
  });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate((s) => sessionStorage.setItem("psf_ui_state", JSON.stringify(s)), { source: "c1st", sites: ["PEUGEOT FR"], from: DEBUT, to: FIN, cmpMode: "none" });
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("Évolution mensuelle").first()).toBeVisible();
  await page.keyboard.press("F12");
  await expect(page.getByText("Code d'accès C1ST")).toBeVisible({ timeout: 700 });
  await expect(page.getByText("Évolution mensuelle")).toHaveCount(0);
  await expect.poll(() => alertes.length).toBe(1);
  expect(alertes[0]).toContain("f12");
});
