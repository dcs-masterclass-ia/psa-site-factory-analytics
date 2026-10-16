// @ts-check
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" },
  ]);
});

const toggle = p => p.locator('[data-testid="scope-picker-toggle"]');
const summary = p => p.locator('[data-testid="scope-summary"]');
const market = (p, c) => p.locator('[data-testid="scope-market"]').filter({ hasText: new RegExp("^" + c + "$") });
const brand = (p, b) => p.locator('[data-testid="scope-brand"]').filter({ hasText: new RegExp("^" + b + "$") });

async function ouvre(page) {
  await page.goto("/");
  await expect(toggle(page)).toContainText("Marché entier", { timeout: 15_000 });
  await toggle(page).click();
  await page.getByText("Aucun", { exact: true }).click();
}

test("pastille marché FR : tous les sites France", async ({ page }) => {
  await ouvre(page);
  await market(page, "FR").click();
  await expect(summary(page)).toContainText("France · Toutes les marques → ");
  await page.locator('[data-testid="scope-expand"]').click();
  const n = await page.locator('[data-testid="scope-item"]').count();
  expect(n).toBeGreaterThan(5);
  for (const t of await page.locator('[data-testid="scope-item"]').allInnerTexts()) expect(t).toMatch(/ FR/);
  await expect(summary(page)).toContainText(`→ ${n} sites`);
});

test("FR + Peugeot : PEUGEOT FR seul", async ({ page }) => {
  await ouvre(page);
  await market(page, "FR").click();
  await brand(page, "Peugeot").click();
  await expect(summary(page)).toContainText("France · Peugeot → 1 site");
  await expect(toggle(page)).toContainText("PEUGEOT FR");
});

test("croisement FR+BE x Peugeot+Citroën = 4 sites", async ({ page }) => {
  await ouvre(page);
  for (const c of ["FR", "BE"]) await market(page, c).click();
  for (const b of ["Peugeot", "Citroën"]) await brand(page, b).click();
  await expect(summary(page)).toContainText("France + Belgique · 2 marques → 4 sites");
});

test("raccourci BELUX", async ({ page }) => {
  await ouvre(page);
  await page.locator('[data-testid="scope-shortcut"]').filter({ hasText: "BELUX" }).click();
  await expect(summary(page)).toContainText("Belgique + Luxembourg · Toutes les marques");
  await expect(market(page, "BE")).toHaveAttribute("aria-pressed", "true");
  await expect(market(page, "LU")).toHaveAttribute("aria-pressed", "true");
});

test("dépliage puis décocher un site : sélection personnalisée", async ({ page }) => {
  await ouvre(page);
  await market(page, "FR").click();
  await page.locator('[data-testid="scope-expand"]').click();
  await page.locator('[data-testid="scope-item"]').first().click();
  await expect(summary(page)).toContainText("Sélection personnalisée · ");
  await page.locator('[data-testid="scope-item"]').first().click();
  await expect(summary(page)).toContainText("France · Toutes les marques → ");
});

test("recherche libre, Échap, dernières sélections", async ({ page }) => {
  await ouvre(page);
  await page.locator('[data-testid="scope-search-input"]').fill("OPEL FR");
  await page.locator('[data-testid="scope-item"]').filter({ hasText: "OPEL FR" }).first().click();
  await expect(toggle(page)).toContainText("OPEL FR");
  await page.keyboard.press("Escape");
  await expect(page.locator('[data-testid="scope-search-input"]')).toHaveCount(0);
  await toggle(page).click();
  await expect(page.locator('[data-testid="scope-recent"]').first()).toContainText("OPEL FR · 1 site");
  await page.getByText("Tout", { exact: true }).click();
  await expect(toggle(page)).toContainText("Marché entier");
  await page.locator('[data-testid="scope-recent"]').first().click();
  await expect(toggle(page)).toContainText("OPEL FR");
});
