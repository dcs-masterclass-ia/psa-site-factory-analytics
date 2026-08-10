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

// un marqueur de contenu reel, propre a chaque onglet -- plus robuste que
// verifier des couleurs CSS d'implementation (le curseur actif est un
// element a part qui glisse sous les items, voir navItemStyle/
// tabIndicatorRef dans index.html).
const NAV_TABS = {
  "GA4": "Vue d'ensemble",
  "Search Console": "Clics, impressions & position",
  "Comparaison V2": "Rapport hebdomadaire V2",
  "PageSpeed": "Performance des sites de reprise",
  "Tableau": "Leads back-office",
  "KamIA": "Comment puis-je t'aider",
};
// mega-menu (10/08/2026) : la barre du haut n'affiche plus que des
// groupes ("Google", "Analyse", KamIA a part) -- un onglet n'est plus
// directement visible/cliquable depuis la barre, il faut d'abord ouvrir
// son groupe. null = pas de groupe (KamIA reste un item direct).
// "Tableau" (ex-BigQuery, active le 10/08/2026) : onglet dedie aux leads
// back-office, separe de GA4 pour ne jamais melanger les deux sources.
const NAV_GROUP_OF = {
  "GA4": "Google", "Search Console": "Google", "PageSpeed": "Google", "Tableau": "Google",
  "Comparaison V2": "Analyse",
  "KamIA": null,
};
// libelle affiche dans la carte du mega-menu, quand il differe de la cle
// NAV_TABS ci-dessus (seul GA4 -> "Analytics" differe actuellement).
const NAV_ITEM_LABEL = { "GA4": "Analytics" };
async function ouvrirOnglet(page, tab) {
  const groupe = NAV_GROUP_OF[tab];
  if (groupe) {
    await page.locator("nav button", { hasText: groupe }).first().click();
    await page.locator("button", { hasText: NAV_ITEM_LABEL[tab] || tab }).first().click();
  } else {
    await page.locator("nav div", { hasText: tab }).first().click();
  }
}

test.describe("chargement de l'application", () => {
  test("demarre sans erreur JS et affiche l'en-tete", async ({ page }) => {
    const pageErrors = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));

    await page.goto("/", { waitUntil: "networkidle" });

    await expect(page.locator("header, nav").first()).toBeVisible();
    // le logo Converge est une image (logo-converge-noir.webp), pas du texte
    await expect(page.locator('img[alt="Converge"]').first()).toBeVisible();
    // mega-menu : seuls les GROUPES ("Google", "Analyse") + KamIA sont
    // directement visibles dans la barre repliee, pas chaque onglet.
    for (const label of ["Google", "Analyse", "KamIA"]) {
      await expect(page.locator("nav", { hasText: label }).first()).toBeVisible();
    }

    expect(pageErrors, `erreurs JS non attendues au chargement : ${pageErrors.join(" | ")}`).toEqual([]);
  });

  test("charge par defaut en vue \"Tous les sites\" (agregee)", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.locator("text=Tous les sites").first()).toBeVisible();
    await expect(page.locator("text=vue agrégée").first()).toBeVisible();

    // les cartes KPI doivent afficher de vrais totaux, pas des zeros
    const leadsCard = page.locator("text=Leads").first();
    await expect(leadsCard).toBeVisible();
  });
});

test.describe("selecteur de site", () => {
  test("l'option \"Pas de site sélectionné\" bascule en vue agregee", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });

    // choisit d'abord un site precis...
    // data-testid stable : depuis le mega-menu (10/08/2026), les boutons
    // "Google"/"Analyse" portent aussi aria-expanded et precedent celui-ci
    // dans le DOM -- .first() sur aria-expanded seul seul ne cible plus le
    // bon bouton.
    await page.locator('[data-testid="site-picker-toggle"]').click();
    await page.locator('input[placeholder="Rechercher un site…"]').fill("OPEL FR");
    await page.locator('div[role="button"]').filter({ hasText: "OPEL FR" }).first().click();
    await expect(page.locator('button[aria-expanded]:has-text("OPEL FR")')).toBeVisible();

    // ...puis revient a la vue agregee
    // data-testid stable : depuis le mega-menu (10/08/2026), les boutons
    // "Google"/"Analyse" portent aussi aria-expanded et precedent celui-ci
    // dans le DOM -- .first() sur aria-expanded seul seul ne cible plus le
    // bon bouton.
    await page.locator('[data-testid="site-picker-toggle"]').click();
    await page.locator("text=Pas de site sélectionné").click();
    await expect(page.locator("text=Tous les sites").first()).toBeVisible();
  });

  test("la recherche filtre la liste des sites", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    // data-testid stable : depuis le mega-menu (10/08/2026), les boutons
    // "Google"/"Analyse" portent aussi aria-expanded et precedent celui-ci
    // dans le DOM -- .first() sur aria-expanded seul seul ne cible plus le
    // bon bouton.
    await page.locator('[data-testid="site-picker-toggle"]').click();
    await page.locator('input[placeholder="Rechercher un site…"]').fill("PEUGEOT PT");
    await expect(page.locator('div[role="button"]').filter({ hasText: "PEUGEOT PT" }).first()).toBeVisible();
    await expect(page.locator('div[role="button"]').filter({ hasText: "OPEL FR" })).toHaveCount(0);
  });
});

test.describe("navigation entre onglets", () => {
  for (const [tab, marqueur] of Object.entries(NAV_TABS)) {
    test(`l'onglet "${tab}" s'affiche sans erreur JS`, async ({ page }) => {
      const pageErrors = [];
      page.on("pageerror", (err) => pageErrors.push(err.message));

      await page.goto("/", { waitUntil: "networkidle" });
      // mega-menu (10/08/2026) : un onglet groupe (GA4/Search Console/
      // PageSpeed/Comparaison V2) n'est plus visible/cliquable directement
      // dans la barre, il faut d'abord ouvrir son groupe -- voir
      // ouvrirOnglet(). KamIA reste un item direct, inchange.
      await ouvrirOnglet(page, tab);
      // vue "tous les sites" par defaut : l'agregation sur 64 sites est
      // plus lourde qu'un site seul, attendre le vrai contenu plutot
      // qu'un delai fixe.
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

    // ancien locator :has-text("j") supposait un libelle de periode par
    // defaut contenant "j" (ex. "28 j") -- casse le 10/08/2026 quand le
    // defaut est passe a "Mois precedent" (aucun "j" dans le libelle).
    // data-testid stable, independant du libelle affiche.
    await page.locator('[data-testid="period-picker-toggle"]').click();
    await page.locator('button:has-text("12 mois")').click();
    await page.waitForTimeout(800);

    await expect(page.locator("text=12 derniers mois").first()).toBeVisible();
  });
});
