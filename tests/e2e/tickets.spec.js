// @ts-check
// Tickets : formulaire, validation, envoi, suivi, gestion du statut.
// L'API (fonction Vercel) n'existe pas en local : /api/tickets est simulée.
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
});

function simule(page, { peutGerer = true, tickets = [] } = {}) {
  const posts = [];
  page.route("**/api/tickets", async (route) => {
    const req = route.request();
    if (req.method() === "GET") return route.fulfill({ json: { tickets, peutGerer, moi: "e2e@autobiz.com" } });
    const body = req.postDataJSON();
    posts.push(body);
    if (body.action === "create")
      return route.fulfill({ json: { ok: true, ticket: { id: "T-20261011-ab12", type: body.type, priorite: body.priorite, titre: body.titre, description: body.description,
        statut: "nouveau", createdAt: Date.now(), updatedAt: Date.now(), auteur: "e2e@autobiz.com", contexte: body.contexte, commentaires: [] } } });
    const t = tickets.find((x) => x.id === body.id) || tickets[0];
    if (body.action === "status") return route.fulfill({ json: { ok: true, ticket: { ...t, statut: body.statut } } });
    return route.fulfill({ json: { ok: true, ticket: { ...t, commentaires: [{ auteur: "e2e@autobiz.com", texte: body.texte, at: Date.now() }] } } });
  });
  return posts;
}

test("créer un ticket : validation, envoi avec contexte, retour dans le suivi", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  const posts = simule(page);
  await page.goto("/", { waitUntil: "networkidle" });
  await page.getByText("Ticket", { exact: true }).first().click();
  await expect(page.getByText("Contexte joint automatiquement")).toBeVisible();

  const envoyer = page.getByText("Envoyer le ticket");
  await envoyer.click();                                   // formulaire vide : rien ne part
  expect(posts.length).toBe(0);

  await page.getByText("Bug de données", { exact: true }).click();
  await page.getByPlaceholder("En une phrase").fill("Leads FR faux en septembre");
  await page.locator("textarea").fill("Le total FR du Tableau ne correspond pas au BO sur septembre.");
  await envoyer.click();

  await expect(page.getByText(/Ticket T-20261011-ab12 créé/)).toBeVisible();
  expect(posts.length).toBe(1);
  expect(posts[0]).toMatchObject({ action: "create", type: "bug", priorite: "normale", titre: "Leads FR faux en septembre" });
  expect(posts[0].contexte.nbSites).toBeGreaterThan(0);
  expect(posts[0].contexte.periode.from).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  await expect(page.getByText("Leads FR faux en septembre").first()).toBeVisible();   // dans le suivi
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("suivi : un gestionnaire change le statut et commente", async ({ page }) => {
  const base = { id: "T-20261001-0001", type: "optimisation", priorite: "haute", titre: "Export CSV des pages", description: "Pouvoir exporter le tableau Pages en CSV.",
    statut: "nouveau", createdAt: Date.now() - 3600e3, updatedAt: Date.now(), auteur: "b.moumni@autobiz.com", contexte: { onglet: "Search Console", nbSites: 1, sites: ["PEUGEOT FR"] }, commentaires: [] };
  const posts = simule(page, { tickets: [base] });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.getByText("Ticket", { exact: true }).first().click();
  await page.getByText(/^Suivi/).click();
  await expect(page.getByText("Export CSV des pages")).toBeVisible();
  await expect(page.getByText("Priorité haute")).toBeVisible();
  await page.getByText("Export CSV des pages").click();
  await expect(page.getByText("Pouvoir exporter le tableau Pages en CSV.")).toBeVisible();
  await page.getByText("En cours", { exact: true }).click();
  await expect.poll(() => posts.at(-1)).toMatchObject({ action: "status", id: "T-20261001-0001", statut: "en_cours" });
  await page.getByPlaceholder("Ajouter un commentaire…").fill("Pris en compte, prévu la semaine prochaine.");
  await page.getByText("Envoyer", { exact: true }).click();
  await expect.poll(() => posts.at(-1)).toMatchObject({ action: "comment", texte: "Pris en compte, prévu la semaine prochaine." });
});

test("profil sans droit de gestion : pas de boutons de statut", async ({ page }) => {
  const base = { id: "T-20261001-0002", type: "bug", priorite: "normale", titre: "Mon ticket", description: "Description suffisante ici.", statut: "nouveau",
    createdAt: Date.now(), updatedAt: Date.now(), auteur: "e2e@autobiz.com", contexte: {}, commentaires: [] };
  simule(page, { peutGerer: false, tickets: [base] });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.getByText("Ticket", { exact: true }).first().click();
  await page.getByText(/^Suivi/).click();
  await page.getByText("Mon ticket").click();
  await expect(page.getByText("En cours", { exact: true })).toHaveCount(0);
});
