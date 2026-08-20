// Bundle le panneau Hermes/KamIA beta (React + AG-UI) en un seul fichier
// statique, sans bundler React/ReactDOM (deja charges en globals par
// support.js) -- coherent avec le reste du repo (zero build step Vercel).
const esbuild = require("esbuild");
const path = require("path");

esbuild
  .build({
    entryPoints: [path.join(__dirname, "src/index.js")],
    outfile: path.join(__dirname, "../../hermes-agui.js"),
    bundle: true,
    minify: true,
    format: "iife",
    target: "es2020",
    alias: {
      react: path.join(__dirname, "src/react-shim.js"),
      "react-dom/client": path.join(__dirname, "src/reactdom-shim.js"),
    },
    banner: {
      js: "// GENERATED from panel/hermes-agui/src/*.js -- do not edit, rebuild with `cd panel/hermes-agui && node build.js`.\n",
    },
  })
  .then(() => console.log("hermes-agui.js built."))
  .catch(() => process.exit(1));
