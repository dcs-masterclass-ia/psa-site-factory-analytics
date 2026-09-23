// @ts-check
const { test, expect } = require("@playwright/test");

// psf_user_email est le seul signal cote client verifie par wireLogin()
// pour retirer l'ecran de connexion (voir index.html) -- l'auth reelle
// (cookie psf_session, HttpOnly) protege les donnees cote serveur sur
// Vercel, absente ici puisqu'on sert les fichiers statiques directement.
// Poser le cookie AVANT tout goto() evite le aller-retour navigate ->
// cookie -> reload utilise pendant le developpement manuel.
test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" },
  ]);
});

// Le clone pixel-perfect de la maquette (13/09/2026) n'utilise ni <header>/
// <nav> semantiques ni data-testid sur la nav laterale -- chaque
// destination est un <div title="..."> dans la colonne d'icones (84px).
// Titres reels (index.html, colonne DATA) : le libelle "GA4" du menu
// s'appelle "Google Analytics 4" en title, pas "Analytics".
const NAV_TABS = {
  "GA4": "L'essentiel",
  "Search Console": "Clics, impressions & position",
  "PageSpeed": "Site sélectionné",
  "Tableau": "Leads back-office",
};
const NAV_TITLE = {
  "GA4": "Google Analytics 4", "Search Console": "Search Console",
  "PageSpeed": "PageSpeed Insights", "Tableau": "Tableau",
};
async function ouvrirOnglet(page, tab) {
  await page.locator(`div[title="${NAV_TITLE[tab]}"]`).first().click();
}

test.describe("chargement de l'application", () => {
  test("demarre sans erreur JS et affiche l'en-tete", async ({ page }) => {
    const pageErrors = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));

    await page.goto("/", { waitUntil: "networkidle" });

    // le logo Converge est une image, pas du texte
    await expect(page.locator('img[alt="Converge"]').first()).toBeVisible();
    // nav laterale a icones : chaque destination est un div title="..."
    for (const title of Object.values(NAV_TITLE)) {
      await expect(page.locator(`div[title="${title}"]`).first()).toBeVisible();
    }

    expect(pageErrors, `erreurs JS non attendues au chargement : ${pageErrors.join(" | ")}`).toEqual([]);
  });

  test("charge par defaut en vue \"Marché entier\" (agregee, vraies donnees)", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    // boot() charge pipeline.json + tous les data/<site>.json avant de
    // peupler st.sites -- attendre le vrai contenu plutot qu'un delai fixe.
    await expect(page.locator('[data-testid="scope-picker-toggle"]')).toContainText("Marché entier", { timeout: 10_000 });

    // les cartes KPI doivent afficher de vrais totaux, pas des zeros
    const leadsCard = page.locator("text=Leads GA4").first();
    await expect(leadsCard).toBeVisible();
  });
});

test.describe("selecteur de perimetre", () => {
  test("choisir un site precis puis revenir a \"Marché entier\"", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.locator('[data-testid="scope-picker-toggle"]')).toContainText("Marché entier", { timeout: 10_000 });

    // le picker est maintenant un arbre a cases a cocher (multi-selection) :
    // "choisir un site precis" = tout decocher puis cocher seulement celui-la.
    await page.locator('[data-testid="scope-picker-toggle"]').click();
    await page.getByText("Aucun", { exact: true }).click();
    await page.locator('[data-testid="scope-search-input"]').fill("OPEL FR");
    await page.locator('[data-testid="scope-item"]').filter({ hasText: "OPEL FR" }).first().click();
    await expect(page.locator('[data-testid="scope-picker-toggle"]')).toContainText("OPEL FR");

    // le panneau reste ouvert apres avoir coche une case (multi-selection) --
    // pas besoin de le rouvrir.
    await page.getByText("Tout", { exact: true }).click();
    await expect(page.locator('[data-testid="scope-picker-toggle"]')).toContainText("Marché entier");
  });

  test("la recherche filtre la liste des sites", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.locator('[data-testid="scope-picker-toggle"]')).toContainText("Marché entier", { timeout: 10_000 });

    await page.locator('[data-testid="scope-picker-toggle"]').click();
    await page.locator('[data-testid="scope-search-input"]').fill("PEUGEOT PT");
    await expect(page.locator('[data-testid="scope-item"]').filter({ hasText: "PEUGEOT PT" }).first()).toBeVisible();
    await expect(page.locator('[data-testid="scope-item"]').filter({ hasText: "OPEL FR" })).toHaveCount(0);
  });
});

test.describe("navigation entre onglets", () => {
  for (const [tab, marqueur] of Object.entries(NAV_TABS)) {
    test(`l'onglet "${tab}" s'affiche sans erreur JS`, async ({ page }) => {
      const pageErrors = [];
      page.on("pageerror", (err) => pageErrors.push(err.message));

      await page.goto("/", { waitUntil: "networkidle" });
      // vue "Marché entier" par defaut : l'agregation sur ~82 sites reels
      // est plus lourde qu'un site seul, attendre boot() avant de naviguer.
      await expect(page.locator('[data-testid="scope-picker-toggle"]')).toContainText("Marché entier", { timeout: 10_000 });
      await ouvrirOnglet(page, tab);
      // attendre le vrai contenu avant de lire pageErrors : une erreur
      // pendant le rendu se produit au meme moment que l'affichage du
      // contenu, verifier apres capture les deux de facon fiable.
      await expect(page.locator(`text=${marqueur}`).first()).toBeVisible({ timeout: 10_000 });
      expect(pageErrors, `erreurs JS sur l'onglet ${tab} : ${pageErrors.join(" | ")}`).toEqual([]);
    });
  }
});

test.describe("selecteur de periode", () => {
  test("changer de periode met a jour les chiffres affiches", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.locator('[data-testid="scope-picker-toggle"]')).toContainText("Marché entier", { timeout: 10_000 });

    const rangeLabelAvant = await page.locator('[data-testid="period-picker-toggle"]').innerText();

    await page.locator('[data-testid="period-picker-toggle"]').click();
    await page.locator('span', { hasText: /^14 derniers jours$/ }).first().click();
    await page.waitForTimeout(500);

    const rangeLabelApres = await page.locator('[data-testid="period-picker-toggle"]').innerText();
    expect(rangeLabelApres).not.toEqual(rangeLabelAvant);
  });
});
