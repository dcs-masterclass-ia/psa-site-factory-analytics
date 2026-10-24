// @ts-check
// Alerte de mise à jour des tickets : pastille sur « Ticket » + modal centré flou à l'ouverture.
const { test, expect } = require("@playwright/test");

test("l'auteur est alerté quand son ticket change de statut ou reçoit une réponse", async ({ page, context }) => {
  const moi = "asktaprof@gmail.com";
  await context.addCookies([{ name: "psf_user_email", value: encodeURIComponent(moi), url: "http://localhost:8199" }]);
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  const t0 = Date.now() - 3600000;
  const tickets = [
    { id: "T-1", type: "optimisation", priorite: "normale", titre: "Total par canal", description: "Ajouter un total par canal", statut: "resolu", createdAt: t0, updatedAt: t0 + 1000, auteur: moi,
      commentaires: [{ auteur: "x@exemple.test", texte: "Statut : en_cours → resolu", at: t0 + 1000, systeme: true }, { auteur: "x@exemple.test", texte: "Livré, tu peux vérifier sur tous les marchés.", at: t0 + 2000 }] },
    { id: "T-2", type: "bug", priorite: "normale", titre: "Écart de leads", description: "Écart avec le BO sur septembre", statut: "refuse", createdAt: t0, updatedAt: t0 + 1000, auteur: moi,
      commentaires: [{ auteur: "x@exemple.test", texte: "Statut : nouveau → refuse", at: t0 + 1000, systeme: true }] },
    { id: "T-3", type: "question", priorite: "normale", titre: "Définition de la conversion", description: "Comment est calculée la conversion ?", statut: "nouveau", createdAt: t0, updatedAt: t0, auteur: moi, commentaires: [] },
  ];
  await page.route("**/api/tickets", (r) => r.fulfill({ json: { tickets: tickets, peutGerer: false, moi } }));
  await page.route("**/api/events", (r) => r.fulfill({ json: { events: [], peutEcrire: false } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await expect(page.getByText("2 tickets mis à jour")).toBeVisible({ timeout: 8000 });
  await expect(page.getByText("C'est traité : la modification est en ligne.")).toBeVisible();
  await expect(page.getByText("Ton ticket n'a pas été retenu.")).toBeVisible();
  await expect(page.getByText("Livré, tu peux vérifier sur tous les marchés.")).toBeVisible();
  await page.screenshot({ path: process.env.TMPDIR + "/tk-alerte.png" });
  await page.getByText("Voir mes tickets", { exact: true }).click();
  await expect(page.getByText("Écart de leads")).toBeVisible();
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(3000);
  await expect(page.getByText("2 tickets mis à jour")).toHaveCount(0);
  expect(erreurs).toEqual([]);
});
