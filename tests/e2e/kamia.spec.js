// @ts-check
// KamIA : vrai agent (api/agent.js) à la place des conversations factices ; l'historique est lu / écrit par profil (api/kamia-conversations.js).
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40exemple.test", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });
});

test("KamIA : plus de conversation factice, vraie question -> /api/agent, réponse, agents consultés et graphique", async ({ page }) => {
  const erreurs = [], appels = [], sauvegardes = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.route("**/api/kamia-conversations", async (r) => {
    if (r.request().method() === "PUT") { sauvegardes.push(JSON.parse(r.request().postData() || "{}")); return r.fulfill({ json: { ok: true } }); }
    return r.fulfill({ json: { conversations: [{ id: "k-ancienne", title: "Question de la semaine dernière", updatedAt: 1, messageCount: 2 }] } });
  });
  await page.route("**/api/agent", async (r) => {
    appels.push(JSON.parse(r.request().postData() || "{}"));
    await r.fulfill({ json: { answer: "Les leads de PEUGEOT FR sont à 1 200 sur la période, **+8 %** vs la précédente.", verifie: true, agentsConsultes: ["Données", "Comparaison"],
      charts: [{ title: "Leads par semaine", type: "line", labels: ["S1", "S2", "S3"], series: [{ name: "PEUGEOT FR", values: [100, 140, 120] }] }], history: [{ role: "user", content: "x" }] } });
  });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('[data-chrome="chat"][data-fab]').click();
  for (const faux of ["Chute des leads", "Tunnel mobile", "Budget Paid", "742 contre 1 076"]) await expect(page.getByText(faux)).toHaveCount(0);   // plus aucune maquette
  await expect(page.getByText(/Je suis connectée aux vraies données/)).toBeVisible();
  await page.getByText("Nouvelle conversation").first().click();                                       // sélecteur d'historique
  await expect(page.getByText("Question de la semaine dernière")).toBeVisible();                       // historique réel du profil
  await page.getByText("Nouvelle conversation").first().click();                                       // referme
  await page.getByPlaceholder("Poser une question sur ce périmètre…").fill("Où sont les leads ?");
  await page.keyboard.press("Enter");
  await expect(page.getByText(/Les leads de PEUGEOT FR sont à 1 200/)).toBeVisible();
  await expect(page.getByText("Comparaison", { exact: true })).toBeVisible();                           // agents consultés
  await expect(page.getByText("Chiffres vérifiés dans les données")).toBeVisible();
  await expect(page.getByText("Leads par semaine")).toBeVisible();                                    // graphique issu de l'agent
  expect(appels.length).toBe(1);
  expect(appels[0].question).toContain("Où sont les leads ?");
  expect(appels[0].view.tab).toBeTruthy();
  await expect.poll(() => sauvegardes.length).toBe(1);                                                // conversation enregistrée
  expect(sauvegardes[0].upsert[0].messages.map((m) => m.role)).toEqual(["user", "assistant"]);
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("KamIA : erreur serveur -> message d'erreur clair, rien n'est inventé", async ({ page }) => {
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.route("**/api/kamia-conversations", (r) => r.fulfill({ json: { conversations: [] } }));
  await page.route("**/api/agent", (r) => r.fulfill({ status: 500, json: { error: "Erreur interne de l'assistant." } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('[data-chrome="chat"][data-fab]').click();
  await page.getByText("Compare ce périmètre au parc").click();
  await expect(page.getByText("Erreur interne de l'assistant.")).toBeVisible();
});
