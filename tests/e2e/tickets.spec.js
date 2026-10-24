// @ts-check
// Tickets : formulaire, validation, envoi, suivi, gestion du statut.
// L'API (fonction Vercel) n'existe pas en local : /api/tickets est simulée.
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
});

function simule(page, { peutGerer = true, peutStatut = peutGerer, tickets = [] } = {}) {
  const posts = [];
  page.route("**/api/tickets", async (route) => {
    const req = route.request();
    if (req.method() === "GET") return route.fulfill({ json: { tickets, peutGerer, peutStatut, moi: "e2e@exemple.test" } });
    const body = req.postDataJSON();
    posts.push(body);
    if (body.action === "create") {
      // la liste du serveur contient le ticket créé (le dashboard la relit périodiquement)
      const ticket = { id: "T-20261011-ab12", type: body.type, priorite: body.priorite, titre: body.titre, description: body.description,
        statut: "nouveau", createdAt: Date.now(), updatedAt: Date.now(), auteur: "e2e@exemple.test", contexte: body.contexte, commentaires: [] };
      tickets.unshift(ticket);
      return route.fulfill({ json: { ok: true, ticket } });
    }
    const t = tickets.find((x) => x.id === body.id) || tickets[0];
    if (body.action === "status") return route.fulfill({ json: { ok: true, ticket: { ...t, statut: body.statut } } });
    return route.fulfill({ json: { ok: true, ticket: { ...t, commentaires: [{ auteur: "e2e@exemple.test", texte: body.texte, at: Date.now() }] } } });
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
    statut: "nouveau", createdAt: Date.now() - 3600e3, updatedAt: Date.now(), auteur: "b.martin@exemple.test", contexte: { onglet: "Search Console", nbSites: 1, sites: ["PEUGEOT FR"] }, commentaires: [] };
  const posts = simule(page, { tickets: [base] });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.getByText("Ticket", { exact: true }).first().click();
  await page.getByText(/^En cours/).click();
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
    createdAt: Date.now(), updatedAt: Date.now(), auteur: "e2e@exemple.test", contexte: {}, commentaires: [] };
  simule(page, { peutGerer: false, tickets: [base] });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.getByText("Ticket", { exact: true }).first().click();
  await page.getByText(/^En cours/).click();
  await page.getByText("Mon ticket").click();
  await expect(page.getByText("En cours", { exact: true })).toHaveCount(0);
});

test("les tickets résolus ou refusés passent dans l'onglet « Terminés », hors du suivi", async ({ page }) => {
  const base = { type: "bug", priorite: "normale", description: "x", createdAt: Date.now() - 5000, updatedAt: Date.now() - 1000, auteur: "e2e@exemple.test", contexte: {}, commentaires: [] };
  simule(page, { peutGerer: false, tickets: [
    { ...base, id: "T-1", titre: "Ticket en cours", statut: "en_cours" },
    { ...base, id: "T-2", titre: "Ticket résolu", statut: "resolu" },
    { ...base, id: "T-3", titre: "Ticket refusé", statut: "refuse" },
  ] });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.getByText("Ticket", { exact: true }).first().click();
  await page.getByText(/^En cours/).click();
  await expect(page.getByText("Ticket en cours")).toBeVisible();
  await expect(page.getByText("Ticket résolu")).toHaveCount(0);
  await expect(page.getByText(/^En cours \(1\)$/)).toBeVisible();
  await page.getByText(/^Terminés/).click();
  await expect(page.getByText("Ticket résolu")).toBeVisible();
  await expect(page.getByText("Ticket refusé")).toBeVisible();
  await expect(page.getByText("Ticket en cours")).toHaveCount(0);
  await expect(page.getByText(/^Terminés \(2\)$/)).toBeVisible();
});
