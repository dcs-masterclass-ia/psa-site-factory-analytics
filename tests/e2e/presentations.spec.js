// @ts-check
// Onglet « Présentations » : questionnaire, plan calculé, enregistrement et liste de briefs.
// L'API (fonction Vercel) n'existe pas en local : /api/presentations est simulée.
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
});

test("créer un brief : plan calculé, validation, enregistrement", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  const posts = [];
  await page.route("**/api/presentations", async (route) => {
    const req = route.request();
    if (req.method() === "GET") return route.fulfill({ json: { briefs: [], moi: "e2e@autobiz.com" } });
    const body = req.postDataJSON();
    posts.push(body);
    return route.fulfill({ json: { ok: true, brief: { ...body.brief, id: "B-test1", statut: "brouillon", auteur: "e2e@autobiz.com", createdAt: Date.now(), updatedAt: Date.now() } } });
  });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('div[title="Présentations"]').click();

  await expect(page.getByText("Plan de la présentation")).toBeVisible();
  await expect(page.getByText(/BELUX \(Belgique \+ Luxembourg\) · T\d-\d{4}/)).toBeVisible();
  await expect(page.getByText(/^\d+ diapositives$/)).toBeVisible();
  // le module « Contenu » est replié par défaut (résumé visible), on le déplie
  await expect(page.getByText(/\d+ modules? sélectionnés? · \d+ diapositives/)).toBeVisible();
  await expect(page.getByText("Données CRM non disponibles dans Converge")).toBeHidden();
  await page.getByText("Contenu", { exact: true }).click();
  // module indisponible : non cochable, absent du plan
  await expect(page.getByText("Données CRM non disponibles dans Converge")).toBeVisible();

  const total = async () => parseInt((await page.getByText(/^\d+ diapositives$/).innerText()), 10);
  const avant = await total();
  await page.getByText("Trafic et leads par marque", { exact: true }).first().click();   // décoche
  expect(await total()).toBeLessThan(avant);

  await page.getByText("+ Ajouter un point ouvert").click();
  await page.getByPlaceholder("Titre du point").fill("Pop-in");
  await page.getByText("+ Ajouter une action").click();
  await page.getByPlaceholder("Action").fill("Brancher Promo Master");
  await page.getByText("À faire", { exact: true }).click();                              // statut suivant

  await page.getByText("Enregistrer le brief").click();
  await expect(page.getByText(/Brief enregistré/)).toBeVisible();
  expect(posts.length).toBe(1);
  expect(posts[0]).toMatchObject({ action: "save", brief: { client: "Stellantis", perimetre: { pays: ["BE", "LU"] }, comparaisons: { precedente: true, n1: true } } });
  expect(posts[0].brief.modules).not.toContain("trafic_marque");
  expect(posts[0].brief.modules).not.toContain("crm");
  expect(posts[0].brief.pointsOuverts[0].titre).toBe("Pop-in");
  expect(posts[0].brief.prochainesEtapes[0]).toMatchObject({ item: "Brancher Promo Master", statut: "en_cours" });
  await expect(page.getByText("Mettre à jour le brief")).toBeVisible();
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("briefs enregistrés : liste, ouverture dans le formulaire, duplication", async ({ page }) => {
  const brief = { id: "B-x1", titre: "Stellantis BELUX T3-2026", client: "Stellantis", langue: "en", perimetre: { pays: ["BE", "LU"], marques: [] }, periode: { type: "trimestre", annee: 2026, indice: 3 },
    comparaisons: { precedente: true, n1: false }, modules: ["global", "projets"], contact: { nom: "B. Moumni" }, pointsOuverts: [], prochainesEtapes: [], statut: "brouillon",
    auteur: "e2e@autobiz.com", createdAt: Date.now(), updatedAt: Date.now() };
  await page.route("**/api/presentations", (r) => r.fulfill({ json: { briefs: [brief], moi: "e2e@autobiz.com" } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('div[title="Présentations"]').click();
  await page.getByText(/^Briefs enregistrés/).click();
  await expect(page.getByText("Stellantis BELUX T3-2026")).toBeVisible();
  await page.getByText("Dupliquer").click();
  await expect(page.getByText(/Copie du brief/)).toBeVisible();
  await expect(page.getByPlaceholder("Prénom Nom")).toHaveValue("B. Moumni");
});

test("périodicité : mensuel, semestre, annuel adaptent la période et les comparaisons", async ({ page }) => {
  await page.route("**/api/presentations", (r) => r.fulfill({ json: { briefs: [], templates: [], moi: "x" } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('div[title="Présentations"]').click();
  await page.getByText("Mensuelle", { exact: true }).click();
  await expect(page.getByText("vs mois précédent")).toBeVisible();
  await expect(page.getByText(/^Période : (Janvier|Février|Mars|Avril|Mai|Juin|Juillet|Août|Septembre|Octobre|Novembre|Décembre) \d{4}$/)).toBeVisible();
  await page.getByText("Semestrielle", { exact: true }).click();
  await expect(page.getByText("vs semestre précédent")).toBeVisible();
  await page.getByText("Annuelle", { exact: true }).click();
  await expect(page.getByText("vs année précédente")).toBeVisible();
  await expect(page.getByText(/vs (mois|trimestre|semestre) précédent/)).toHaveCount(0);   // pas de « précédente » pour une année
  await page.getByText("Trimestrielle", { exact: true }).click();
  await expect(page.getByText("vs même trimestre N-1")).toBeVisible();
});

test("modèles : modèle de base appliqué, enregistrement d'un modèle, onglet Modèles", async ({ page }) => {
  const posts = [];
  const tpls = [];
  await page.route("**/api/presentations", async (route) => {
    const req = route.request();
    if (req.method() === "GET") return route.fulfill({ json: { briefs: [], templates: tpls, moi: "e2e@autobiz.com" } });
    const body = req.postDataJSON(); posts.push(body);
    const t = { ...body.template, id: "M-t1", auteur: "e2e@autobiz.com", createdAt: Date.now(), updatedAt: Date.now() };
    tpls.push(t);
    return route.fulfill({ json: { ok: true, template: t } });
  });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('div[title="Présentations"]').click();
  await page.getByText("Reporting mensuel — pays", { exact: true }).first().click();       // modèle de base
  await expect(page.getByText(/Modèle « Reporting mensuel — pays » appliqué/)).toBeVisible();
  await expect(page.getByText("vs mois précédent")).toBeVisible();                  // périodicité du modèle
  await page.getByPlaceholder("Nom du modèle").fill("Mon mensuel BELUX");
  await page.getByText("Enregistrer", { exact: true }).click();
  await expect(page.getByText(/Modèle « Mon mensuel BELUX » enregistré/)).toBeVisible();
  expect(posts[0]).toMatchObject({ action: "save_template", template: { nom: "Mon mensuel BELUX", config: { periodicite: "mois", client: "Stellantis" } } });
  expect(posts[0].template.config.perimetre.pays).toEqual(["BE", "LU"]);
  await page.getByText("Modèles", { exact: true }).click();
  await expect(page.getByText("Mon mensuel BELUX").first()).toBeVisible();
  await expect(page.getByText("Modèle de base").first()).toBeVisible();
});

test("génération : le bouton se remplit avec le temps, puis propose le téléchargement", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  let etat = "demandee";
  const brief = () => ({ id: "B-gen1", titre: "Brief test", client: "Stellantis", langue: "fr", perimetre: { pays: ["BE", "LU"], marques: [] }, periode: { type: "trimestre", annee: 2026, indice: 3 },
    comparaisons: { precedente: true, n1: true }, modules: ["global"], contact: {}, pointsOuverts: [], prochainesEtapes: [], statut: etat, demandeeLe: Date.now() - 20000,
    ...(etat === "generee" ? { fichier: "presentations/out/B-gen1.pptx", diapositives: 54 } : {}), auteur: "e2e@autobiz.com", updatedAt: Date.now() });
  await page.route("**/api/presentations", (route) => route.fulfill({ json: { briefs: [brief()], templates: [], moi: "e2e@autobiz.com" } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('div[title="Présentations"]').click();
  await page.getByText("Briefs enregistrés", { exact: false }).click();
  await page.getByText("Ouvrir", { exact: true }).click();
  const bouton = page.getByText(/^Génération en cours… \d+ %$/);
  await expect(bouton).toBeVisible();
  const pct = async () => parseInt(((await bouton.innerText()).match(/(\d+) %/) || [])[1], 10);
  const p1 = await pct();
  expect(p1).toBeGreaterThan(5);
  await expect.poll(pct, { timeout: 8000 }).toBeGreaterThan(p1);          // progresse sans rechargement
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("périmètre : un clic sélectionne une seule entrée, Cmd/Maj + clic en ajoute", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.route("**/api/presentations", (route) => route.fulfill({ json: { briefs: [], templates: [], moi: "e2e@autobiz.com" } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('div[title="Présentations"]').click();
  const nbMarques = async () => parseInt(((await page.getByText(/\d+ marques? ×/).first().innerText().catch(() => "0")).match(/(\d+) marque/) || [])[1] || "0", 10);
  const toutes = await page.getByText(/^Toutes \(\d+\)$/).innerText();
  const n = parseInt(toutes.match(/\d+/)[0], 10);
  expect(n).toBeGreaterThan(3);
  await page.getByText("Peugeot", { exact: true }).first().click();               // une seule marque, pas toutes les autres
  await expect(page.getByText(/^1 marque ×/).first()).toBeVisible();
  await page.getByText("Opel", { exact: true }).first().click({ modifiers: ["Shift"] });   // ajout
  await expect(page.getByText(/^2 marques ×/).first()).toBeVisible();
  await page.getByText("Peugeot", { exact: true }).first().click();               // clic simple : seulement Peugeot
  await expect(page.getByText(/^1 marque ×/).first()).toBeVisible();
  await page.getByText("Peugeot", { exact: true }).first().click();               // re-clic sur la seule marque : retour à « Toutes »
  await expect(page.getByText(new RegExp(`^${n} marques ×`)).first()).toBeVisible();
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});
