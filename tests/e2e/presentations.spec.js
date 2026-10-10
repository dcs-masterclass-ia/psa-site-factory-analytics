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
  expect(posts[0]).toMatchObject({ action: "save", brief: { client: "Stellantis", perimetre: { pays: ["BE", "LU"] }, comparaisons: { qoq: true, yoy: true } } });
  expect(posts[0].brief.modules).not.toContain("trafic_marque");
  expect(posts[0].brief.modules).not.toContain("crm");
  expect(posts[0].brief.pointsOuverts[0].titre).toBe("Pop-in");
  expect(posts[0].brief.prochainesEtapes[0]).toMatchObject({ item: "Brancher Promo Master", statut: "en_cours" });
  await expect(page.getByText("Mettre à jour le brief")).toBeVisible();
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("briefs enregistrés : liste, ouverture dans le formulaire, duplication", async ({ page }) => {
  const brief = { id: "B-x1", titre: "Stellantis BELUX T3-2026", client: "Stellantis", langue: "en", perimetre: { pays: ["BE", "LU"], marques: [] }, periode: { annee: 2026, trimestre: 3 },
    comparaisons: { qoq: true, yoy: false }, modules: ["global", "projets"], contact: { nom: "B. Moumni" }, pointsOuverts: [], prochainesEtapes: [], statut: "brouillon",
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
