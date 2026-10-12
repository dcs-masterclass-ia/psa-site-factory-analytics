// @ts-check
// Langue du dashboard : bascule FR / EN, mémorisation, retour exact au français, aucun accent français résiduel sur GA4.
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context, page }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
  await page.route("**/api/events", (r) => r.fulfill({ json: { events: [], peutEcrire: false } }));
});

test("bascule EN : textes traduits, nombres à l'anglaise, retour FR identique, préférence mémorisée", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.goto("/", { waitUntil: "networkidle" });
  await expect(page.getByText("Tunnel de conversion").first()).toBeVisible();
  await page.waitForTimeout(1500); // les données arrivent site par site : on compare les libellés, pas les chiffres
  const lettres = () => page.evaluate(() => document.body.innerText.replace(/[^A-Za-zÀ-ÿ]/g, ""));
  const avant = await lettres();

  await page.locator('[aria-label="English"]').click();
  await expect(page.getByText("Conversion funnel").first()).toBeVisible();
  await expect(page.getByText("Tunnel de conversion")).toHaveCount(0);
  await expect(page.getByText("Key figures", { exact: true }).first()).toBeVisible();
  // nombres : plus d'espace insécable ni de virgule décimale dans les KPI (« 7,1 % » -> « 7.1% »)
  const en = await page.evaluate(() => document.body.innerText);
  expect(en).not.toMatch(/\d,\d\s?%/);

  // la préférence survit au rechargement
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("Conversion funnel").first()).toBeVisible();

  // retour au français : le texte est exactement celui d'origine
  await page.locator('[aria-label="Français"]').click();
  await expect(page.getByText("Tunnel de conversion").first()).toBeVisible();
  await page.waitForTimeout(400);
  const apres = await lettres();
  expect(apres).toBe(avant);
  expect(erreurs).toEqual([]);
});

test("EN : aucun texte français accentué sur la vue GA4 principale", async ({ page }) => {
  await page.addInitScript(() => { try { localStorage.setItem("psf_lang", "en"); } catch (e) {} });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const restes = await page.evaluate(() => {
    const ok = new Set(["Français", "Español"]);
    const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) {
      const p = n.parentElement; if (!p || /^(SCRIPT|STYLE|TEXTAREA)$/.test(p.nodeName)) continue;
      const t = n.nodeValue.replace(/\s+/g, " ").trim();
      if (/[éèêàùçôîû]/i.test(t) && !ok.has(t)) out.push(t);
    }
    return out;
  });
  expect(restes).toEqual([]);
});
