// @ts-check
// Captures d'image des modules (capture.js) : copie / PNG au survol, mode « Capture » avec export ZIP. L'image est toujours en thème clair.
const { test, expect } = require("@playwright/test");
const fs = require("fs");

test.beforeEach(async ({ context, page }) => {
  await context.addCookies([{ name: "psf_user_email", value: "prenom.nom%40autobiz.com", url: "http://localhost:8199" }]);
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: "http://localhost:8199" });
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); if (!sessionStorage.getItem("psf_cap_init")) { sessionStorage.setItem("psf_cap_init", "1"); if (!window.__sansCapture) localStorage.setItem("psf_capture", "1"); } } catch (e) {} });
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
});

const PNG = [0x89, 0x50, 0x4e, 0x47];

test("survol d'un module : pastille Copier / PNG ; PNG téléchargé et copie dans le presse-papiers", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.getByText("Tunnel de conversion").first().hover();
  await expect(page.getByText("Copier", { exact: true })).toBeVisible();
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByText("PNG", { exact: true }).click()]);
  expect(dl.suggestedFilename()).toMatch(/^converge-.*\.png$/);
  const chemin = await dl.path();
  const octets = fs.readFileSync(chemin);
  expect([...octets.subarray(0, 4)]).toEqual(PNG);
  expect(octets.length).toBeGreaterThan(20000);                                              // une vraie image, pas un vide
  await page.getByText("Tunnel de conversion").first().hover();
  await page.getByText("Copier", { exact: true }).click();
  await expect(page.getByText(/Image copiée/)).toBeVisible({ timeout: 20000 });
  const type = await page.evaluate(async () => { const it = (await navigator.clipboard.read())[0]; return it.types.join(","); });
  expect(type).toContain("image/png");
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("mode Capture : menu et en-tête masqués, compteur de modules, export ZIP d'une image par module", async ({ page }) => {
  test.setTimeout(120000);
  await page.goto("/", { waitUntil: "networkidle" });
  await page.getByTitle(/^Mode capture : exporter toute la vue/).click();
  await expect(page.locator('[data-chrome="rail"]')).toBeHidden();
  await expect(page.getByText(/^\d+ modules?$/)).toBeVisible();
  const [dl] = await Promise.all([page.waitForEvent("download", { timeout: 100000 }), page.getByText("Tout exporter (ZIP)").click()]);
  expect(dl.suggestedFilename()).toMatch(/^converge-captures-.*\.zip$/);
  const z = fs.readFileSync(await dl.path());
  expect(z.subarray(0, 2).toString()).toBe("PK");
  const nb = z.toString("latin1").split("PK\x03\x04").length - 1;
  expect(nb).toBeGreaterThanOrEqual(3);                                                    // plusieurs images dans l'archive
  expect(z.toString("latin1")).toMatch(/01-[a-z0-9-]+\.png/);
  await page.keyboard.press("Escape");
  await expect(page.locator('[data-chrome="rail"]')).toBeVisible();                          // retour à l'affichage normal
});

test("interrupteur « Capture » de l'en-tête : désactivé par défaut (aucune pastille), activé = pastille sur les modules et bouton d'export de la vue", async ({ page, context }) => {
  await context.addInitScript(() => { try { localStorage.removeItem("psf_capture"); sessionStorage.setItem("psf_cap_init", "1"); } catch (e) {} });
  await page.goto("/", { waitUntil: "networkidle" });
  const interrupteur = page.getByRole("switch");
  const exportVue = page.getByTitle(/^Mode capture : exporter toute la vue/);
  await page.getByText("Tunnel de conversion").first().hover();
  await expect(page.getByText("Copier", { exact: true })).toBeHidden();                        // rien sur les modules
  await expect(exportVue).toHaveCount(0);
  await expect(interrupteur).toHaveAttribute("aria-checked", "false");
  await expect(page.locator('[data-chrome="rail"]').getByRole("switch")).toHaveCount(0);       // plus d'interrupteur dans le menu latéral
  await interrupteur.click();
  await expect(interrupteur).toHaveAttribute("aria-checked", "true");
  await expect(exportVue).toBeVisible();
  await page.getByText("Tunnel de conversion").first().hover();
  await expect(page.getByText("Copier", { exact: true })).toBeVisible();
  await interrupteur.click();                                                                  // on remet à off
  await page.getByText("Tunnel de conversion").first().hover();
  await expect(page.getByText("Copier", { exact: true })).toBeHidden();
  expect(await page.evaluate(() => localStorage.getItem("psf_capture"))).toBe("0");
});
