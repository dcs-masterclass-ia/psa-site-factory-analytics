// @ts-check
// Espace OEM : page de choix STLA / OEM, données Ford (data/oem/), GA4 seulement, aucun écran Stellantis (Search Console, PageSpeed, leads, KamIA).
const { test, expect } = require("@playwright/test");

test.use({ storageState: { cookies: [], origins: [] } });       // navigateur vierge : aucun espace mémorisé

async function ouvre(context, page, avant) {
  const erreurs = [];
  page.on("console", (m) => { if (/renderVals|FAILED/.test(m.text())) erreurs.push(m.text().slice(0, 200)); });
  page.on("pageerror", (e) => erreurs.push(e.message));
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  if (avant) await page.addInitScript(avant);
  await page.goto("/", { waitUntil: "networkidle" });
  return erreurs;
}

test("première visite : la page de choix propose STLA et OEM, sans charger les données", async ({ context, page }) => {
  const demandes = [];
  page.on("request", (r) => demandes.push(r.url()));
  const erreurs = await ouvre(context, page);
  await expect(page.locator("#espaceScreen")).toBeVisible();
  await expect(page.locator("#espaceScreen .espace-carte")).toHaveCount(2);
  if (process.env.OEM_CAPTURES) await page.screenshot({ path: process.env.OEM_CAPTURES + "/1-page-de-choix.png" });
  expect(demandes.filter((u) => /\/data\/[a-z-]+\.json/.test(u) && !/\/oem\//.test(u))).toEqual([]);      // aucun fichier de site chargé avant le choix
  expect(erreurs).toEqual([]);
});

test("choisir OEM : le site Ford s'affiche en GA4, sans les onglets Stellantis", async ({ context, page }) => {
  const erreurs = await ouvre(context, page);
  await page.locator('#espaceScreen [data-espace="oem"]').click();
  await expect(page.locator("#espaceScreen")).toHaveCount(0);
  await page.waitForTimeout(1500);
  const texte = await page.locator("body").innerText();
  expect(texte).toContain("1 site");                                   // le seul site OEM (Ford) ; le parc Stellantis n'est pas chargé
  await expect(page.getByText("Search Console", { exact: true })).toHaveCount(0);
  await expect(page.getByText("PageSpeed", { exact: true })).toHaveCount(0);
  await expect(page.getByText("KamIA", { exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem("psf_espace"))).toBe("oem");
  if (process.env.OEM_CAPTURES) await page.screenshot({ path: process.env.OEM_CAPTURES + "/2-espace-oem-ford-ga4.png" });
  expect(erreurs).toEqual([]);
});

test("le choix est mémorisé, et la pastille d'espace ramène à la page de choix", async ({ context, page }) => {
  await ouvre(context, page, () => { if (!sessionStorage.getItem("__amorce")) { sessionStorage.setItem("__amorce", "1"); localStorage.setItem("psf_espace", "oem"); } });       // amorce une seule fois (sinon elle rejouerait après le rechargement)
  await page.waitForTimeout(1200);
  expect(await page.locator("body").innerText()).toContain("1 site");
  await page.getByTitle("Changer d'espace (STLA / OEM)").click();
  await page.waitForLoadState("networkidle");
  await expect(page.locator("#espaceScreen")).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("psf_espace"))).toBeNull();
});

test("choisir STLA : le parc Stellantis est inchangé", async ({ context, page }) => {
  const erreurs = await ouvre(context, page);
  await page.locator('#espaceScreen [data-espace="stla"]').click();
  await page.waitForTimeout(2500);
  const texte = await page.locator("body").innerText();
  expect(texte).toMatch(/91 sites|8\d sites/);
  expect(texte).not.toMatch(/(^|\D)1 site\b/);
  expect(erreurs).toEqual([]);
});


test("leads Ford : l'onglet Leads s'ouvre avec les leads du back-office (si le fichier existe)", async ({ context, page }) => {
  const erreurs = await ouvre(context, page);
  await page.locator('#espaceScreen [data-espace="oem"]').click();
  await page.waitForTimeout(1500);
  const fichier = await (await page.request.get("/data/oem/ford-fr.json")).json();
  test.skip(!fichier.leads || !fichier.leads.total, "pas de leads back-office dans les données de test");
  await page.getByText("Leads", { exact: true }).first().click();
  await expect(page.getByText("Pilotage des leads").first()).toBeVisible();
  await expect(page.getByText("Leads par jour")).toBeVisible();
  await expect(page.getByText("Search Console", { exact: true })).toHaveCount(0);
  expect(erreurs).toEqual([]);
});

// Captures du rendu clair / sombre (OEM_CAPTURES=<dossier>) : page de choix avec les logos, puis écran Ford.
for (const theme of ["light", "dark"]) {
  test(`rendu ${theme} : page de choix (logos) et espace OEM`, async ({ context, page }) => {
    const erreurs = await ouvre(context, page, `localStorage.setItem("psf_theme", "${theme}")`);
    await expect(page.locator("#espaceScreen .espace-logo")).toHaveCount(2);
    for (const img of await page.locator("#espaceScreen .espace-logo").all()) {
      await expect(img).toBeVisible();
      expect(await img.evaluate((el) => /** @type {HTMLImageElement} */ (el).naturalWidth)).toBeGreaterThan(50);       // logo réellement chargé (servi par Converge, pas par un site tiers)
    }
    expect(await page.evaluate(() => document.documentElement.getAttribute("data-theme"))).toBe(theme);
    if (process.env.OEM_CAPTURES) await page.screenshot({ path: `${process.env.OEM_CAPTURES}/choix-${theme}.png` });
    await page.locator('#espaceScreen [data-espace="oem"]').click();
    await page.waitForTimeout(1500);
    if (process.env.OEM_CAPTURES) await page.screenshot({ path: `${process.env.OEM_CAPTURES}/oem-ford-${theme}.png` });
    expect(erreurs).toEqual([]);
  });
}
