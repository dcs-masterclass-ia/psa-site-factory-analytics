// @ts-check
// Deux personnes connectées en même temps : la vue de l'une (onglet, sites, période) n'influence jamais celle de l'autre.
const { test, expect } = require("@playwright/test");

async function ouvre(browser, email) {
  const context = await browser.newContext();
  await context.addCookies([{ name: "psf_user_email", value: encodeURIComponent(email), url: "http://localhost:8199" }]);
  const page = await context.newPage();
  await page.goto("/", { waitUntil: "networkidle" });
  return { context, page };
}
const etat = (page) => page.evaluate(() => sessionStorage.getItem("psf_ui_state"));

test("la vue d'un compte n'impacte pas celle d'un autre compte connecté en même temps", async ({ browser }) => {
  const a = await ouvre(browser, "a@autobiz.com");
  const b = await ouvre(browser, "b@autobiz.com");
  const avant = await etat(b.page);
  await a.page.evaluate(() => sessionStorage.setItem("psf_ui_state", JSON.stringify({ source: "sc", sites: ["PEUGEOT FR"], from: "2026-09-01", to: "2026-09-30", cmpMode: "none" })));
  await a.page.reload({ waitUntil: "networkidle" });
  await expect(a.page.getByText("Search Console").first()).toBeVisible();
  await b.page.waitForTimeout(1500);
  expect(await etat(b.page)).toBe(avant);
  expect(await b.page.evaluate(() => localStorage.getItem("psf_scope_recent"))).toBeNull();
  await b.page.reload({ waitUntil: "networkidle" });
  console.log("ETAT_B", await etat(b.page));
  expect(await etat(b.page)).not.toContain('"source":"sc"');
  await a.context.close(); await b.context.close();
});
