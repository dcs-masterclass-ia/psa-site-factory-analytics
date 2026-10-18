/**
 * Captures d'image des modules de Converge (pour les DKAM : coller dans PowerPoint sans passer par une capture d'écran manuelle).
 *
 *  1. Survol d'un module : une petite pastille « Copier / PNG » apparaît ; un clic copie l'image du module dans le presse-papiers (ou la télécharge).
 *  2. Mode « Capture » (bouton de l'en-tête) : menu et en-tête masqués, « Tout exporter » = une image par module dans un ZIP, « Vue entière » = une seule image.
 *
 * L'image est toujours en thème clair, en haute résolution (x2), avec une ligne de contexte en pied : périmètre, période, comparaison, onglet, date et personne.
 * Dépendances : html-to-image.js (MIT) et capture-fonts.js (Poppins, OFL), chargés à la première capture ; tout est servi par le site lui-même (CSP).
 * Les logos hébergés ailleurs ne sont pas embarqués (connect-src 'self') : ils sont remplacés par un vide plutôt que de faire échouer la capture.
 */
(function () {
  if (window.psfCapture) return;

  // un « module » = une carte blanche à bord arrondi (style commun à tout le tableau de bord). On teste le style CALCULÉ : le texte de l'attribut style
  // n'a pas toujours le même format selon le navigateur.
  const estCarte = (el) => {
    if (!el || el.nodeType !== 1 || el.tagName !== "DIV") return false;
    const cs = getComputedStyle(el);
    const rayon = parseFloat(cs.borderTopLeftRadius);
    return rayon >= 14 && rayon <= 22 && parseFloat(cs.borderTopWidth) >= 1 && cs.backgroundColor === "rgb(255, 255, 255)";
  };
  const VIDE = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
  const TXT = (fr, en) => ((window.i18n && window.i18n.lang) === "en" ? en : fr);
  let bouton = null, courant = null, toast = null, barre = null, enCours = false;
  // désactivé par défaut : interrupteur « Capture » du menu (localStorage psf_capture = 1). Désactivé = aucune pastille sur les modules, pas de mode capture.
  const actif = () => { try { return localStorage.getItem("psf_capture") === "1"; } catch (e) { return false; } };

  // ---------- utilitaires
  const attend = (ms) => new Promise((r) => setTimeout(r, ms));
  const raf2 = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  const slug = (t) => String(t || "module").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 48) || "module";
  const horsInterface = (el) => !el.closest('[data-chrome], [data-capture-ui], [role="dialog"]');
  const visible = (el) => { const r = el.getBoundingClientRect(); return r.width >= 220 && r.height >= 70 && el.offsetParent !== null; };

  function modules() {
    const tous = [...document.querySelectorAll('div[style*="radius"]')].filter((el) => horsInterface(el) && visible(el) && estCarte(el));
    return tous.filter((el) => !tous.some((autre) => autre !== el && autre.contains(el)));      // le plus englobant seulement
  }
  function carteSous(cible) {
    if (!cible || !cible.closest || cible.closest("[data-capture-ui]")) return null;
    for (let el = cible, n = 0; el && el !== document.body && n < 14; el = el.parentElement, n++) {
      if (estCarte(el) && horsInterface(el) && visible(el)) return el;
    }
    return null;
  }
  function titreDe(el) {
    const l = String(el.innerText || "").split("\n").map((t) => t.trim()).find((t) => t.length > 2);
    return l || "module";
  }

  // ---------- chargement paresseux des dépendances
  function charge(src) {
    return new Promise((ok, ko) => {
      const s = document.createElement("script");
      s.src = src; s.onload = ok; s.onerror = () => ko(new Error("chargement " + src));
      document.head.appendChild(s);
    });
  }
  async function dependances() {
    if (!window.htmlToImage) await charge("./html-to-image.js");
    if (!window.PSF_FONT_CSS) await charge("./capture-fonts.js");
    try { await document.fonts.load("500 22px Poppins"); } catch (e) { /* la police de la page suffit */ }
  }

  // ---------- rendu d'un élément en canvas (+ pied de page de contexte)
  function contexte() {
    let c = {};
    try { c = (window.psfCaptureCtx && window.psfCaptureCtx()) || {}; } catch (e) { /* contexte absent : pied minimal */ }
    const g = [c.tab, c.scope && (c.scope + (c.sites ? " (" + c.sites + " site" + (c.sites > 1 ? "s" : "") + ")" : "")), c.from && (c.from + " → " + c.to), c.cmp].filter(Boolean).join(" · ");
    const d = new Date();
    const date = String(d.getDate()).padStart(2, "0") + "/" + String(d.getMonth() + 1).padStart(2, "0") + "/" + d.getFullYear();
    return { gauche: g, droite: "Converge · " + (c.user || "") + (c.user ? " · " : "") + date };
  }
  async function rendu(el, { pleinePage } = {}) {
    await dependances();
    const racine = document.documentElement, avant = racine.getAttribute("data-theme");
    const sombre = avant === "dark";
    if (sombre) { racine.setAttribute("data-theme", "light"); await raf2(); }          // l'image est toujours en thème clair
    try {
      const opts = { pixelRatio: 2, backgroundColor: "#ffffff", fontEmbedCSS: window.PSF_FONT_CSS, imagePlaceholder: VIDE, cacheBust: false,
        filter: (n) => !(n.nodeType === 1 && n.hasAttribute && n.hasAttribute("data-capture-ui")), style: { margin: "0", transform: "none" } };
      if (pleinePage) { opts.width = el.scrollWidth; opts.height = el.scrollHeight; opts.style = Object.assign({}, opts.style, { overflow: "visible", height: el.scrollHeight + "px", maxHeight: "none" }); }
      const url = await window.htmlToImage.toPng(el, opts);
      const img = await new Promise((ok, ko) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => ko(new Error("image")); i.src = url; });
      const pied = 64, c = document.createElement("canvas");
      c.width = img.width; c.height = img.height + pied;
      const x = c.getContext("2d");
      x.fillStyle = "#ffffff"; x.fillRect(0, 0, c.width, c.height);
      x.drawImage(img, 0, 0);
      x.fillStyle = "#ececf2"; x.fillRect(0, img.height + 6, c.width, 2);
      const ctx = contexte();
      x.font = "500 22px Poppins, Arial, sans-serif"; x.textBaseline = "middle";
      x.fillStyle = "#6d727a"; x.textAlign = "left"; x.fillText(ctx.gauche, 24, img.height + pied / 2 + 3, c.width * 0.62);
      x.fillStyle = "#a3a7ae"; x.textAlign = "right"; x.fillText(ctx.droite, c.width - 24, img.height + pied / 2 + 3, c.width * 0.36);
      return c;
    } finally { if (sombre) racine.setAttribute("data-theme", avant); }
  }
  const blobDe = (canvas) => new Promise((ok, ko) => canvas.toBlob((b) => (b ? ok(b) : ko(new Error("png"))), "image/png"));

  function telecharge(blob, nom) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = nom; document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
  }

  // ---------- ZIP (sans compression : aucun besoin de bibliothèque)
  const TABLE = (() => { const t = []; for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  const crc32 = (u8) => { let c = 0xffffffff; for (let i = 0; i < u8.length; i++) c = TABLE[(c ^ u8[i]) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  function zip(fichiers) {                                   // [{ nom, octets: Uint8Array }]
    const enc = new TextEncoder(), parts = [], centrale = [];
    let decalage = 0;
    const d = new Date(), heure = (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1), jour = ((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate();
    for (const f of fichiers) {
      const nom = enc.encode(f.nom), crc = crc32(f.octets), n = f.octets.length;
      const loc = new DataView(new ArrayBuffer(30));
      loc.setUint32(0, 0x04034b50, true); loc.setUint16(4, 20, true); loc.setUint16(6, 0x0800, true); loc.setUint16(8, 0, true); loc.setUint16(10, heure, true); loc.setUint16(12, jour, true);
      loc.setUint32(14, crc, true); loc.setUint32(18, n, true); loc.setUint32(22, n, true); loc.setUint16(26, nom.length, true); loc.setUint16(28, 0, true);
      parts.push(loc.buffer, nom, f.octets);
      const cen = new DataView(new ArrayBuffer(46));
      cen.setUint32(0, 0x02014b50, true); cen.setUint16(4, 20, true); cen.setUint16(6, 20, true); cen.setUint16(8, 0x0800, true); cen.setUint16(10, 0, true); cen.setUint16(12, heure, true); cen.setUint16(14, jour, true);
      cen.setUint32(16, crc, true); cen.setUint32(20, n, true); cen.setUint32(24, n, true); cen.setUint16(28, nom.length, true); cen.setUint32(42, decalage, true);
      centrale.push(cen.buffer, nom);
      decalage += 30 + nom.length + n;
    }
    const taille = centrale.reduce((s, p) => s + (p.byteLength || p.length), 0);
    const fin = new DataView(new ArrayBuffer(22));
    fin.setUint32(0, 0x06054b50, true); fin.setUint16(8, fichiers.length, true); fin.setUint16(10, fichiers.length, true); fin.setUint32(12, taille, true); fin.setUint32(16, decalage, true);
    return new Blob([...parts, ...centrale, fin.buffer], { type: "application/zip" });
  }

  // ---------- interface
  function message(texte, ok = true, duree = 2400) {
    if (!toast) {
      toast = document.createElement("div"); toast.setAttribute("data-capture-ui", "");
      toast.style.cssText = "position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:100000;font:600 13.5px Poppins,system-ui,sans-serif;border-radius:999px;padding:10px 18px;box-shadow:0 14px 30px -14px rgba(20,16,40,.5);pointer-events:none;transition:opacity .2s";
      document.body.appendChild(toast);
    }
    toast.textContent = texte; toast.style.background = ok ? "#1b1636" : "#a33c39"; toast.style.color = "#fff"; toast.style.opacity = "1";
    clearTimeout(toast._t); if (duree) toast._t = setTimeout(() => { toast.style.opacity = "0"; }, duree);
  }
  const ICONE_COPIE = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="8" width="12" height="12" rx="2.5"/><path d="M16 8V6.5A2.5 2.5 0 0 0 13.5 4h-7A2.5 2.5 0 0 0 4 6.5v7A2.5 2.5 0 0 0 6.5 16H8"/></svg>';
  const ICONE_PNG = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v12M7 11l5 5 5-5M5 20h14"/></svg>';

  function creeBouton() {
    bouton = document.createElement("div"); bouton.setAttribute("data-capture-ui", "");
    bouton.style.cssText = "position:fixed;z-index:9000;display:none;align-items:center;gap:2px;padding:3px;border-radius:999px;background:#fff;border:1px solid #e0d9fb;box-shadow:0 10px 24px -12px rgba(124,99,238,.6);font:600 12px Poppins,system-ui,sans-serif";
    const b = (html, titre, action) => {
      const e = document.createElement("button"); e.type = "button"; e.title = titre; e.setAttribute("aria-label", titre); e.innerHTML = html;
      e.style.cssText = "display:inline-flex;align-items:center;gap:6px;height:30px;padding:0 11px;border:0;border-radius:999px;background:transparent;color:#4b35c8;cursor:pointer;font:inherit;white-space:nowrap";
      e.onmouseenter = () => { e.style.background = "#f1edff"; }; e.onmouseleave = () => { e.style.background = "transparent"; };
      e.onclick = (ev) => { ev.stopPropagation(); action(); };
      return e;
    };
    bouton.append(b(ICONE_COPIE + "<span>" + TXT("Copier", "Copy") + "</span>", TXT("Copier l'image du module", "Copy the module image"), () => capturer("copie")),
                  b(ICONE_PNG + "<span>PNG</span>", TXT("Télécharger l'image du module", "Download the module image"), () => capturer("png")));
    document.body.appendChild(bouton);
  }
  function placeBouton() {
    if (!courant || !bouton) return;
    const r = courant.getBoundingClientRect();
    if (r.bottom < 60 || r.top > innerHeight - 20) { bouton.style.display = "none"; return; }
    bouton.style.display = "flex";
    const w = bouton.offsetWidth || 150;
    bouton.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.right - w - 10)) + "px";
    bouton.style.top = Math.max(r.top + 10, 64) + "px";
  }
  function survol(e) {
    if (enCours || !actif()) return;
    if (bouton && (e.target === bouton || bouton.contains(e.target))) return;
    const c = carteSous(e.target);
    if (c !== courant) { courant = c; if (!c && bouton) bouton.style.display = "none"; }
    if (c) placeBouton();
  }

  async function capturer(mode) {
    if (!courant || enCours) return;
    const el = courant, titre = titreDe(el);
    enCours = true; if (bouton) bouton.style.display = "none"; message(TXT("Capture en cours…", "Capturing…"), true, 0);
    try {
      const canvas = await rendu(el);
      const nom = "converge-" + slug(titre) + ".png";
      if (mode === "copie" && navigator.clipboard && window.ClipboardItem) {
        try { await navigator.clipboard.write([new ClipboardItem({ "image/png": blobDe(canvas) })]); message(TXT("Image copiée : colle-la dans PowerPoint", "Image copied: paste it into PowerPoint")); }
        catch (e) { telecharge(await blobDe(canvas), nom); message(TXT("Copie impossible ici : image téléchargée", "Copy not possible here: image downloaded")); }
      } else { telecharge(await blobDe(canvas), nom); message(TXT("Image téléchargée", "Image downloaded")); }
    } catch (e) {
      console.error("[capture]", e); message(TXT("Capture impossible pour ce module", "Capture failed for this module"), false, 3500);
    } finally { enCours = false; }
  }

  // ---------- mode « Capture » : toute la vue
  function styleMode(actif) {
    let s = document.getElementById("psf-capture-style");
    if (actif && !s) { s = document.createElement("style"); s.id = "psf-capture-style"; s.textContent = 'html.psf-capture [data-chrome]{display:none!important}'; document.head.appendChild(s); }
    document.documentElement.classList.toggle("psf-capture", !!actif);
  }
  function creeBarre() {
    barre = document.createElement("div"); barre.setAttribute("data-capture-ui", "");
    barre.style.cssText = "position:fixed;left:50%;top:16px;transform:translateX(-50%);z-index:100001;display:flex;align-items:center;gap:6px;padding:6px;border-radius:999px;background:#fff;border:1px solid #e0d9fb;box-shadow:0 18px 40px -16px rgba(124,99,238,.65);font:600 13px Poppins,system-ui,sans-serif;color:#4b35c8;white-space:nowrap";
    const b = (txt, action, plein) => {
      const e = document.createElement("button"); e.type = "button"; e.textContent = txt;
      e.style.cssText = "height:34px;padding:0 15px;border:0;border-radius:999px;cursor:pointer;font:inherit;" + (plein ? "background:linear-gradient(135deg,#8f78f2,#6f55e8);color:#fff" : "background:#f1edff;color:#4b35c8");
      e.onclick = action; return e;
    };
    const etiquette = document.createElement("span"); etiquette.style.cssText = "padding:0 10px 0 12px;color:#6d727a;font-weight:500"; etiquette.id = "psf-capture-n";
    barre.append(etiquette, b(TXT("Tout exporter (ZIP)", "Export all (ZIP)"), toutExporter, true), b(TXT("Vue entière (PNG)", "Whole view (PNG)"), vueEntiere), b(TXT("Quitter", "Exit") + " · Échap", () => bascule(false)));
    document.body.appendChild(barre);
  }
  function majCompteur() { const e = document.getElementById("psf-capture-n"); if (e) { const n = modules().length; e.textContent = n + " " + TXT(n > 1 ? "modules" : "module", n > 1 ? "modules" : "module"); } }

  async function toutExporter() {
    if (enCours) return;
    const liste = modules();
    if (!liste.length) { message(TXT("Aucun module à capturer dans cette vue", "No module to capture in this view"), false, 3000); return; }
    enCours = true; if (bouton) bouton.style.display = "none";
    const fichiers = [], noms = new Set();
    try {
      for (let i = 0; i < liste.length; i++) {
        message(TXT("Capture ", "Capturing ") + (i + 1) + " / " + liste.length + "…", true, 0);
        try {
          const canvas = await rendu(liste[i]);
          let nom = String(i + 1).padStart(2, "0") + "-" + slug(titreDe(liste[i])) + ".png";
          while (noms.has(nom)) nom = "x" + nom; noms.add(nom);
          fichiers.push({ nom, octets: new Uint8Array(await (await blobDe(canvas)).arrayBuffer()) });
        } catch (e) { console.error("[capture] module", i + 1, e); }
      }
      if (!fichiers.length) throw new Error("aucune image");
      const c = (window.psfCaptureCtx && window.psfCaptureCtx()) || {};
      telecharge(zip(fichiers), "converge-captures-" + slug([c.tab, c.scope].filter(Boolean).join(" ")) + (c.from ? "-" + c.from.replace(/\//g, "") + "_" + c.to.replace(/\//g, "") : "") + ".zip");
      message(fichiers.length + " " + TXT("images dans le ZIP", "images in the ZIP"), true, 3500);
    } catch (e) { console.error("[capture]", e); message(TXT("Export impossible", "Export failed"), false, 3500); }
    finally { enCours = false; }
  }
  async function vueEntiere() {
    if (enCours) return;
    const entete = document.querySelector('[data-chrome="header"]');
    const zone = entete && entete.nextElementSibling;
    if (!zone) return;
    enCours = true; message(TXT("Capture de la vue entière…", "Capturing the whole view…"), true, 0);
    try {
      const canvas = await rendu(zone, { pleinePage: true });
      const c = (window.psfCaptureCtx && window.psfCaptureCtx()) || {};
      telecharge(await blobDe(canvas), "converge-" + slug([c.tab, c.scope].filter(Boolean).join(" ")) + "-vue.png");
      message(TXT("Image téléchargée", "Image downloaded"));
    } catch (e) { console.error("[capture]", e); message(TXT("Capture impossible", "Capture failed"), false, 3500); }
    finally { enCours = false; }
  }
  function bascule(actif) {
    const on = actif === undefined ? !document.documentElement.classList.contains("psf-capture") : !!actif;
    if (on && !barre) creeBarre();
    styleMode(on);
    if (barre) barre.style.display = on ? "flex" : "none";
    if (on) { majCompteur(); clearInterval(bascule._t); bascule._t = setInterval(majCompteur, 1500); message(TXT("Mode capture : survole un module pour le copier, ou exporte toute la vue", "Capture mode: hover a module to copy it, or export the whole view"), true, 3500); }
    else { clearInterval(bascule._t); courant = null; if (bouton) bouton.style.display = "none"; }
  }

  // ---------- démarrage
  function init() {
    creeBouton();
    document.addEventListener("mousemove", survol, { passive: true });
    document.addEventListener("scroll", () => { if (courant) placeBouton(); }, { passive: true, capture: true });
    window.addEventListener("resize", () => { if (courant) placeBouton(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && document.documentElement.classList.contains("psf-capture")) bascule(false); });
  }
  if (document.body) init(); else document.addEventListener("DOMContentLoaded", init);

  window.psfCapture = { enabled: actif, setEnabled: (v) => { if (!v) { bascule(false); courant = null; if (bouton) bouton.style.display = "none"; } }, toggle: () => { if (actif()) bascule(); }, actif: () => document.documentElement.classList.contains("psf-capture"), _modules: modules, _zip: zip };
})();
