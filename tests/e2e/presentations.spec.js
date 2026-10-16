// @ts-check
// Onglet « Présentations » : questionnaire, plan calculé, enregistrement et liste de briefs.
// L'API (fonction Vercel) n'existe pas en local : /api/presentations est simulée.
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
});

test("verrouillé : sans l'autorisation, l'onglet Présentations n'apparaît pas", async ({ browser }) => {
  const ctx = await browser.newContext({ baseURL: "http://localhost:8199" });
  await ctx.addCookies([{ name: "psf_user_email", value: "autre%40autobiz.com", url: "http://localhost:8199" }]);
  const page = await ctx.newPage();
  await page.goto("/", { waitUntil: "networkidle" });
  await expect(page.locator('div[title="Google Analytics 4"]').first()).toBeVisible();
  await expect(page.locator('div[title="Présentations"]')).toHaveCount(0);
  await ctx.close();
});

const ouvre = async (page) => {
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('div[title="Présentations"]').click();
};
const continuer = (page) => page.locator("span.pr-btn:visible", { hasText: /^Continuer$/ }).last().click();   // le dernier = celui de l'étape qui vient de s'ouvrir
const choisitModele = async (page, nom = "Personnalisée") => {
  await page.getByText(nom, { exact: true }).first().click();
  await expect(page.getByText("Titre de la présentation").first()).toBeVisible();      // l'étape 2 s'ouvre toute seule
};

test("parcours : les étapes se débloquent une à une, erreurs près des champs", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.route("**/api/presentations", (r) => r.fulfill({ json: { briefs: [], templates: [], moi: "e2e@autobiz.com" } }));
  await ouvre(page);
  await expect(page.getByText("Termine l'étape précédente pour la débloquer").first()).toBeVisible();   // Cadrage, Contenu… verrouillés
  await expect(page.getByText("0 / 3 étapes obligatoires")).toBeVisible();
  await expect(page.getByText("BELUX (Belgique + Luxembourg)")).toHaveCount(0);                    // rien de pré-sélectionné avant d'avoir choisi un modèle
  await expect(page.getByText(/^\d+ diapositives$/)).toHaveCount(0);
  await expect(page.getByText("Il reste à : choisir un modèle.")).toBeVisible();                   // le CTA principal dit pourquoi il est inactif
  await choisitModele(page);
  await expect(page.getByText("1 / 3 étapes obligatoires")).toBeVisible();
  await expect(page.getByText(/^Il reste à : donner un titre/)).toBeVisible();
  await continuer(page);                                       // titre vide : l'erreur apparaît sous le champ
  await expect(page.getByText(/Donne un titre d'au moins 3 caractères/)).toBeVisible();
  await page.getByPlaceholder("Titre de la présentation").fill("Stellantis BELUX — Reporting T3-2026");
  await continuer(page);
  await expect(page.getByText("Contenu recommandé").first()).toBeVisible();                          // étape 3 ouverte, contenu verrouillé
  await expect(page.getByText("3 / 3 étapes obligatoires")).toBeVisible();                   // modèle + cadrage + contenu recommandé : prêt à générer
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("contenu : verrouillé par défaut, déverrouillage confirmé, retour au contenu recommandé", async ({ page }) => {
  await page.route("**/api/presentations", (r) => r.fulfill({ json: { briefs: [], templates: [], moi: "e2e@autobiz.com" } }));
  await ouvre(page);
  await choisitModele(page);
  await page.getByPlaceholder("Titre de la présentation").fill("Test contenu");
  await continuer(page);
  await expect(page.locator(".pr-box")).toHaveCount(0);                                              // pas de cases à cocher tant que c'est verrouillé
  await page.getByText("Personnaliser le contenu", { exact: true }).click();
  await expect(page.getByText(/En le personnalisant, vous pourriez modifier l'équilibre/)).toBeVisible();
  await page.getByText("Garder le contenu recommandé", { exact: true }).click();                     // annuler ne change rien
  await expect(page.locator(".pr-box")).toHaveCount(0);
  await page.getByText("Personnaliser le contenu", { exact: true }).click();
  await page.getByText("Déverrouiller et personnaliser", { exact: true }).click();
  await expect(page.locator(".pr-box").first()).toBeVisible();
  await page.getByText("Trafic et leads par marque", { exact: true }).first().click();               // décoche un module
  await expect(page.getByText("Contenu personnalisé").first()).toBeVisible();
  await page.getByText("Revenir au contenu recommandé", { exact: true }).click();
  await expect(page.getByText("Contenu recommandé").first()).toBeVisible();
  await expect(page.locator(".pr-box")).toHaveCount(0);
});

test("brouillon et modèle : libellés explicites, enregistrement du brouillon, langue italienne", async ({ page }) => {
  const posts = [];
  await page.route("**/api/presentations", async (route) => {
    const req = route.request();
    if (req.method() === "GET") return route.fulfill({ json: { briefs: [], templates: [], moi: "e2e@autobiz.com" } });
    const body = req.postDataJSON();
    posts.push(body);
    return route.fulfill({ json: { ok: true, brief: { ...body.brief, id: "B-test1", statut: "brouillon", auteur: "e2e@autobiz.com", createdAt: Date.now(), updatedAt: Date.now() } } });
  });
  await ouvre(page);
  await expect(page.getByText("Enregistrer le brouillon")).toBeVisible();
  await expect(page.getByText(/sans la générer/)).toBeVisible();
  await expect(page.getByText(/Crée un modèle pour tes prochaines présentations/)).toBeVisible();
  await choisitModele(page);
  await page.getByPlaceholder("Titre de la présentation").fill("Stellantis BELUX — Reporting T3-2026");
  await page.getByText("Italiano", { exact: true }).click();
  await page.getByText("Enregistrer le brouillon").click();
  await expect(page.getByText(/Brief enregistré/)).toBeVisible();
  expect(posts.length).toBe(1);
  expect(posts[0]).toMatchObject({ action: "save", brief: { client: "Stellantis", langue: "it", titre: "Stellantis BELUX — Reporting T3-2026", perimetre: { pays: ["BE", "LU"] }, comparaisons: { precedente: true, n1: true } } });
  expect(posts[0].brief.modules).toContain("analyse");
  expect(posts[0].brief.modules).toContain("crm");   // module C1ST disponible
  await expect(page.getByText("Mettre à jour le brouillon")).toBeVisible();
});

test("points ouverts et prochaines étapes : explications, exemples cliquables, contact compact", async ({ page }) => {
  const posts = [];
  await page.route("**/api/presentations", async (route) => {
    const req = route.request();
    if (req.method() === "GET") return route.fulfill({ json: { briefs: [], templates: [], moi: "e2e@autobiz.com" } });
    const body = req.postDataJSON(); posts.push(body);
    return route.fulfill({ json: { ok: true, brief: { ...body.brief, id: "B-t2", statut: "brouillon", auteur: "e2e@autobiz.com", createdAt: Date.now(), updatedAt: Date.now() } } });
  });
  await ouvre(page);
  await choisitModele(page);
  await page.getByPlaceholder("Titre de la présentation").fill("Test étapes");
  await continuer(page);   // -> étape 3
  await continuer(page);   // -> étape 4
  await expect(page.getByText(/Identifiez les sujets qui nécessitent encore une clarification/)).toBeVisible();
  await page.getByText("+ Validation d'un planning de déploiement").click();
  await expect(page.getByPlaceholder("Titre du point")).toHaveValue("Validation d'un planning de déploiement");
  await continuer(page);   // -> étape 5
  await expect(page.getByText(/Présentez les actions à engager après la réunion/)).toBeVisible();
  await page.getByText("+ Confirmer la date de mise en production").click();
  await expect(page.getByPlaceholder("Action")).toHaveValue("Confirmer la date de mise en production");
  await page.getByText("À faire", { exact: true }).click();     // statut suivant
  await continuer(page);   // -> étape 6
  await page.getByPlaceholder("Prénom Nom").fill("B. Moumni");
  await page.getByText("Enregistrer le brouillon").click();
  await expect.poll(() => posts.length).toBe(1);
  expect(posts[0].brief.pointsOuverts[0].titre).toBe("Validation d'un planning de déploiement");
  expect(posts[0].brief.prochainesEtapes[0]).toMatchObject({ item: "Confirmer la date de mise en production", statut: "en_cours" });
  expect(posts[0].brief.contact.nom).toBe("B. Moumni");
});

test("mes présentations : liste, ouverture dans le parcours, duplication", async ({ page }) => {
  const brief = { id: "B-x1", titre: "Stellantis BELUX T3-2026", client: "Stellantis", langue: "en", perimetre: { pays: ["BE", "LU"], marques: [] }, periode: { type: "trimestre", annee: 2026, indice: 3 },
    comparaisons: { precedente: true, n1: false }, modules: ["global", "projets"], contact: { nom: "B. Moumni" }, pointsOuverts: [], prochainesEtapes: [], statut: "brouillon",
    auteur: "e2e@autobiz.com", createdAt: Date.now(), updatedAt: Date.now() };
  await page.route("**/api/presentations", (r) => r.fulfill({ json: { briefs: [brief], moi: "e2e@autobiz.com" } }));
  await ouvre(page);
  await page.getByText(/^Mes présentations/).click();
  await expect(page.getByText("Stellantis BELUX T3-2026")).toBeVisible();
  await page.getByText("Dupliquer").click();
  await expect(page.getByText(/Copie de « Stellantis BELUX T3-2026 »/).first()).toBeVisible();
  await expect(page.getByText("3 / 3 étapes obligatoires")).toBeVisible();                           // un brief existant a déjà toutes ses étapes obligatoires
  await page.getByText("Contact", { exact: true }).first().click();
  await expect(page.getByPlaceholder("Prénom Nom")).toHaveValue("B. Moumni");
});

test("périodicité : mensuel, semestre, annuel adaptent la période et les comparaisons", async ({ page }) => {
  await page.route("**/api/presentations", (r) => r.fulfill({ json: { briefs: [], templates: [], moi: "x" } }));
  await ouvre(page);
  await choisitModele(page);
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

test("modèles : choix d'un modèle de base, création d'un modèle, onglet Modèles", async ({ page }) => {
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
  await ouvre(page);
  await choisitModele(page, "Revue mensuelle");
  await expect(page.getByText("vs mois précédent")).toBeVisible();                  // périodicité du modèle
  await page.getByText("Enregistrer comme modèle", { exact: true }).click();
  await page.getByPlaceholder("Nom du modèle").fill("Mon mensuel BELUX");
  await page.getByText("Créer le modèle", { exact: true }).click();
  await expect(page.getByText(/Modèle « Mon mensuel BELUX » créé/)).toBeVisible();
  expect(posts[0]).toMatchObject({ action: "save_template", template: { nom: "Mon mensuel BELUX", config: { periodicite: "mois", client: "Stellantis" } } });
  expect(posts[0].template.config.perimetre.pays).toEqual(["FR"]);
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
  await page.getByText(/^Mes présentations/).click();
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
  await choisitModele(page);
  await page.getByText("Voir le détail des diapositives").click();
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

test("commentaires et actions : étape dédiée, saisie envoyée dans le brief", async ({ page }) => {
  const posts = [];
  await page.route("**/api/presentations", async (route) => {
    const req = route.request();
    if (req.method() === "GET") return route.fulfill({ json: { briefs: [], templates: [], moi: "e2e@autobiz.com" } });
    const body = req.postDataJSON(); posts.push(body);
    return route.fulfill({ json: { ok: true, brief: { ...body.brief, id: "B-t3", statut: "brouillon", auteur: "e2e@autobiz.com", createdAt: Date.now(), updatedAt: Date.now() } } });
  });
  await ouvre(page);
  await choisitModele(page);
  await page.getByPlaceholder("Titre de la présentation").fill("Test commentaires");
  await continuer(page);   // -> étape 3
  await page.getByText("Commentaires et actions recommandées").first().click();   // étape 7 (facultative)
  await page.getByPlaceholder("Commentaire (facultatif)").first().fill("Bon trimestre malgré l'été");
  await page.getByPlaceholder("Suggestions automatiques conservées").first().fill("Renforcer le display\nCompléter l'UTM");
  await page.getByText("Enregistrer le brouillon").click();
  await expect.poll(() => posts.length).toBe(1);
  expect(Object.values(posts[0].brief.commentaires)).toContain("Bon trimestre malgré l'été");
  expect(Object.values(posts[0].brief.actionsMarques)[0]).toContain("Renforcer le display");
});

test("modèle « Revue mensuelle » : contenu fixe (carte d'information), éditeur d'actions en cours", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.route("**/api/presentations", (r) => r.fulfill({ json: { briefs: [], templates: [], moi: "e2e@autobiz.com" } }));
  await ouvre(page);
  await choisitModele(page, "Revue mensuelle");
  await page.getByPlaceholder("Titre de la présentation").fill("Revue mensuelle France — Septembre 2026");
  await continuer(page);
  await expect(page.getByText("Ce modèle reproduit le deck « Trade in review »")).toBeVisible();
  await expect(page.locator(".pr-box:visible")).toHaveCount(0);                                  // pas de cases à cocher
  await expect(page.getByText("Estimation : 63 diapositives")).toBeVisible();                    // 1+1+5+3+2+1+1+48+1 = 63 (actions en cours conservées vides, sans annexe CTA)
  await continuer(page);                                                                         // étape 4 (points ouverts)
  await page.locator("span.pr-btn:visible", { hasText: /^Passer cette étape$/ }).last().click();   // étape 4 (points ouverts) : on passe
  await expect(page.getByText("+ Ajouter une action en cours")).toBeVisible();
  await page.getByText("+ Ajouter une action en cours").click();
  await page.getByPlaceholder("Sujet").fill("Migration V2");
  await page.getByPlaceholder("Statut (une ligne par puce)").fill("Lancé\nEn recette");
  await expect(page.getByText("63 diapositives").first()).toBeVisible();                       // la diapositive « actions en cours » existe déjà (vide), le total ne bouge pas
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});
