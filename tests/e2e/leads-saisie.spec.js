// @ts-check
// Pilotage des leads > carte « Projet d'achat » : part des demandes saisies par immatriculation ou par marque et modèle (colonne ENTRY du back-office).
const { test, expect } = require("@playwright/test");

test("projet d'achat : la saisie du véhicule (immatriculation / marque et modèle) s'affiche et fait 100 %", async ({ context, page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate(() => sessionStorage.setItem("psf_ui_state", JSON.stringify({ source: "tb", sites: ["PEUGEOT FR"], from: null, to: null, cmpMode: "none" })));
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("Saisie du véhicule", { exact: true })).toBeVisible();
  const lire = async (lib) => parseFloat((await page.locator("span", { hasText: new RegExp("^" + lib) }).locator("b").first().innerText()).replace(",", "."));
  const a = await lire("Par immatriculation"), m = await lire("Par marque et modèle");
  expect(a + m).toBeGreaterThan(99.8);
  expect(a + m).toBeLessThan(100.2);
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});
