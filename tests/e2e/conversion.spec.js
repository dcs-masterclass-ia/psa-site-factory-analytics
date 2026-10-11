// @ts-check
// Sous-onglet GA4 "Conversion" : courbe quotidienne accueil -> estimation
// (funnelDaily, donnee GA4). Ne depend que des donnees du jour de test.
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
});

test("la courbe de conversion par jour s'affiche pour un site avec funnelDaily", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('[data-testid="scope-picker-toggle"]').click();
  await page.getByText("Aucun", { exact: true }).click();
  await page.locator('[data-testid="scope-search-input"]').fill("CITROEN FR");
  await page.locator('[data-testid="scope-item"]').filter({ hasText: "CITROEN FR" }).first().click();
  await page.keyboard.press("Escape");
  await page.mouse.click(5, 5);

  await page.getByText("Conversion", { exact: true }).first().click();
  await expect(page.getByText("Conversion par jour")).toBeVisible();
  await expect(page.getByText("Moyenne glissante 7 jours")).toBeVisible();
  // courbe de la moyenne glissante : un <path> violet epais
  await expect(page.locator('svg path[stroke="#7c63ee"][stroke-width="2.8"]').first()).toBeVisible();
  await expect(page.getByText(/Conversion moyenne \d+,\d %/)).toBeVisible();
  await page.locator("#cbConv svg").first().screenshot({ path: "test-results/conversion-citroen.png" });
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("sans donnees quotidiennes, un message clair remplace la courbe", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.getByText("Conversion", { exact: true }).first().click();
  // "Marche entier" : la plupart des sites n'ont pas encore funnelDaily en local
  await expect(page.getByText("Conversion par jour")).toBeVisible();
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("module Pages (Search Console) : leads GA4 rattachés à la page d'atterrissage", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('[data-testid="scope-picker-toggle"]').click();
  await page.getByText("Aucun", { exact: true }).click();
  await page.locator('[data-testid="scope-search-input"]').fill("CITROEN FR");
  await page.locator('[data-testid="scope-item"]').filter({ hasText: "CITROEN FR" }).first().click();
  await page.keyboard.press("Escape");
  await page.mouse.click(5, 5);
  await page.locator('div[title="Search Console"]').first().click();
  await page.getByText("Pages", { exact: true }).first().click();      // thème « Pages » (vue Top pages par défaut)

  await expect(page.getByText("Leads GA4", { exact: true }).first()).toBeVisible();
  // filtre canal : Organique par defaut, pastille active sombre ; "Tous canaux" = totaux
  for (const c of ["Organique", "Payant", "Direct", "Autres", "Tous canaux"]) await expect(page.getByText(c, { exact: true }).first()).toBeVisible();
  await page.getByText("Tous canaux", { exact: true }).first().click();
  // l'ancienne colonne "Conv. GA4" (comptee par pagePath, donc toujours 0) a disparu
  await expect(page.getByText("Conv. GA4")).toHaveCount(0);
  // une page de contenu avec des leads rattaches : nombre de leads puis taux (pas "—", pas 0)
  const lignes = await page.evaluate(() => [...document.querySelectorAll("span")]
    .filter((e) => e.textContent.trim() === "/lp/leasing-social-voitures-electriques")
    .map((e) => e.parentElement.innerText.replace(/\s+/g, " ")));
  expect(lignes.some((t) => /\s[1-9][\d ]* \d+,\d{2} %$/.test(t)), lignes.join(" || ")).toBeTruthy();
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("onglet Avant / après V2 : indicateurs, jours exacts, écarts en points, info-bulle", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('[data-testid="scope-picker-toggle"]').click();
  await page.getByText("Aucun", { exact: true }).click();
  await page.locator('[data-testid="scope-search-input"]').fill("OPEL FR");
  await page.locator('[data-testid="scope-item"]').filter({ hasText: "OPEL FR" }).first().click();
  await page.keyboard.press("Escape");
  await page.mouse.click(5, 5);
  await page.getByText("Conversion", { exact: true }).first().click();               // thème « Conversion »
  await page.getByText("Avant / après V2", { exact: true }).first().click();         // vue du thème
  await expect(page.getByText("Parcours avant / après V2")).toBeVisible();
  await expect(page.getByText(/Avant : .+ \(\d+ j\) · Après : .+ \(\d+ j\)/)).toBeVisible();
  await expect(page.getByText("Visiteurs accueil / jour")).toBeVisible();
  await expect(page.getByText("Estimations / jour")).toBeVisible();
  // écarts de conversion en POINTS (jamais une variation relative étiquetée pt)
  await expect(page.getByText(/[+−]\d+,\d pt/).first()).toBeVisible();
  // info-bulle : visible au survol
  const info = page.locator(".dc-info").filter({ has: page.locator(".dc-tip", { hasText: "28 jours qui précèdent la bascule" }) }).first();
  await info.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300); // le défilement masque la bulle (voulu) : on survole une fois la page immobile
  await info.hover();
  await expect(page.locator("#dc-tipbox")).toBeVisible();
  await expect(page.locator("#dc-tipbox")).toContainText("28 jours qui précèdent la bascule");
  await page.locator("body").screenshot({ path: "test-results/v2-opel.png" });
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("info-bulle d'une tuile : jamais rognée par la carte, reste dans l'écran", async ({ page }) => {
  await page.goto("/", { waitUntil: "networkidle" });
  const icone = page.locator(".dc-info").filter({ has: page.locator(".dc-tip", { hasText: "Sessions GA4 de l'outil de reprise" }) }).first();
  await icone.hover();
  const bulle = page.locator("#dc-tipbox");
  await expect(bulle).toBeVisible();
  await expect(bulle).toContainText("Sessions GA4 de l'outil de reprise");
  const b = await bulle.boundingBox();
  const vp = page.viewportSize();
  expect(b.x).toBeGreaterThanOrEqual(0);
  expect(b.y).toBeGreaterThanOrEqual(0);
  expect(b.x + b.width).toBeLessThanOrEqual(vp.width);
  expect(b.y + b.height).toBeLessThanOrEqual(vp.height);
  await page.screenshot({ path: "test-results/tip-tuile.png" });
  await page.mouse.move(5, 300);
  await expect(bulle).toBeHidden();
});

test("Search Console : pas de point à 0 pour les jours sans donnée (délai de publication)", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('[data-testid="scope-picker-toggle"]').click();
  await page.getByText("Aucun", { exact: true }).click();
  await page.locator('[data-testid="scope-search-input"]').fill("CITROEN FR");
  await page.locator('[data-testid="scope-item"]').filter({ hasText: "CITROEN FR" }).first().click();
  await page.keyboard.press("Escape");
  await page.mouse.click(5, 5);
  await page.locator('div[title="Search Console"]').first().click();
  await page.waitForTimeout(600);
  // les données stockées s'arrêtent avant la fin de la période : le libellé le dit,
  // et la fin de l'axe est une zone hachurée « non publié » (jamais un point à 0)
  await expect(page.getByText(/données Search Console jusqu'au \d{2}\/\d{2}/)).toBeVisible();
  await expect(page.locator('svg rect[fill="url(#scHach)"]').first()).toBeVisible();
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("graphique Search Console : deux axes, moyenne 7 j, bulle de survol et pastilles", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('div[title="Search Console"]').first().click();
  await page.waitForTimeout(500);
  const graphe = page.locator('svg[viewBox="0 0 1000 262"]').first();
  await graphe.scrollIntoViewIfNeeded();
  await expect(page.getByText("Moyenne 7 jours", { exact: true })).toBeVisible();
  // la moyenne glissante est tracée ; la masquer via sa pastille la retire
  await expect(page.locator('svg path[stroke="#3b76e8"][stroke-width="2.8"]').first()).toBeVisible();
  const b = await graphe.boundingBox();
  await page.mouse.move(b.x + b.width * 0.5, b.y + b.height * 0.5);
  await expect(graphe.getByText(/^Moy\. 7 j /)).toBeVisible();
  await expect(graphe.getByText(/^CTR /)).toBeVisible();
  await page.getByText("Moyenne 7 jours", { exact: true }).click();
  await expect(page.locator('svg path[stroke="#3b76e8"][stroke-width="2.8"]')).toHaveCount(0);
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("Tableau : prévision, année sur année, saisonnalité, ruptures, qualité", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('div[title^="Tableau"]').first().click();
  for (const t of ["Prévision", "Année sur année", "Saisonnalité", "Ruptures de tendance", "Qualité des leads", "Marques reprises", "Marchés des sites"]) {
    await expect(page.getByText(t, { exact: true }).first()).toBeVisible();
  }
  await expect(page.getByText(/Projection fin \d{4}/).first()).toBeVisible();
  // bascule Sites -> Marques sans erreur, objectif cliquable
  await page.getByText("Marques", { exact: true }).first().click();
  await expect(page.getByText("Accélérations", { exact: true })).toBeVisible();
  await page.locator("span", { hasText: /^\d,\d{2} M$/ }).first().click().catch(() => {});
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("Search Console, Pages : l'URL est un lien vers la vraie page (nouvel onglet) + loupe pour les requêtes", async ({ page }) => {
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('[data-testid="scope-picker-toggle"]').click();
  await page.getByText("Aucun", { exact: true }).click();
  await page.locator('[data-testid="scope-search-input"]').fill("CITROEN FR");
  await page.locator('[data-testid="scope-item"]').filter({ hasText: "CITROEN FR" }).first().click();
  await page.keyboard.press("Escape"); await page.mouse.click(5, 5);
  await page.locator('div[title="Search Console"]').first().click();
  await page.getByText("Pages", { exact: true }).first().click();      // thème « Pages » (vue Top pages par défaut)
  const lien = page.locator('a[title="Ouvrir la page dans un nouvel onglet"]').first();
  await expect(lien).toBeVisible();
  expect(await lien.getAttribute("href")).toMatch(/^https:\/\/.+/);
  expect(await lien.getAttribute("target")).toBe("_blank");
  expect(await lien.getAttribute("rel")).toContain("noopener");
  await expect(page.locator('span[title="Voir les requêtes de cette page"]').first()).toBeVisible();
});

test("PageSpeed : synthèse du parc (moyennes, seuils, optimisations, marques)", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('div[title^="PageSpeed"]').first().click();
  for (const t of ["Synthèse du périmètre", "Répartition et seuils", "À optimiser en priorité", "Par marque", "Sites les plus lents"]) {
    await expect(page.getByText(t, { exact: true }).first()).toBeVisible();
  }
  await expect(page.getByText(/^\d+ \/ 100$/).first()).toBeVisible();
  await page.getByText("Desktop", { exact: true }).first().click();
  await expect(page.getByText("LCP (affichage principal)")).toBeVisible();
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});
