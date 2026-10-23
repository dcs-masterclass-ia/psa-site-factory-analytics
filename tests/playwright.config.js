// @ts-check
const { defineConfig, devices } = require("@playwright/test");

// Sert le vrai index.html + les vraies data/*.json du repo (pas de
// mocks/fixtures) : la racine du projet est un dossier au-dessus de tests/.
const PORT = 8199;

module.exports = defineConfig({
  // serveur statique local mono-thread (python http.server) : en parallele il perd
  // des fichiers de donnees (82 JSON charges a chaque page) -> faux zeros
  workers: 1,
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    // les specs existantes testent l'espace STLA : le dernier choix d'espace (page de choix STLA / OEM) est préchargé ; tests/e2e/oem.spec.js repart d'un navigateur vierge
    storageState: { cookies: [], origins: [{ origin: `http://localhost:${PORT}`, localStorage: [{ name: "psf_espace", value: "stla" }] }] },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1600, height: 1000 } } },
  ],
  webServer: {
    command: `python3 -m http.server ${PORT} --directory ..`,
    url: `http://localhost:${PORT}/`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
