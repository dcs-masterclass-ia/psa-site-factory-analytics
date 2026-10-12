/* Langue du dashboard (FR / EN) — traduction à l'exécution.
 *
 * Le dashboard est écrit en français. Ce module remplace, quand la langue est « en », chaque texte affiché dont la
 * version française figure dans le dictionnaire (i18n-en.js : I18N_EN, généré par scripts/build-i18n.py depuis
 * i18n/en/*.json). Une clé peut contenir des valeurs variables {0}, {1}… : « Voir les {0} canaux » -> « See all {0} channels ».
 * Un texte absent du dictionnaire reste tel quel (noms de sites, contenu saisi par les utilisateurs, valeurs) :
 * on ne traduit jamais ce qu'on ne connaît pas.
 *
 * Valeurs insérées par le gabarit : le rendu les place dans <span class="sc-interp">, ce qui coupe le texte en
 * plusieurs nœuds (« Voir les » + 18 + « canaux »). Un élément qui ne contient que du texte et ces spans est donc
 * traduit en bloc (clé « Voir les {0} canaux »), en conservant l'ordre des valeurs.
 *
 * Fonctionnement : parcours des nœuds texte et des attributs title / placeholder / aria-label / alt, puis un
 * MutationObserver traduit chaque nouveau texte écrit par le rendu. L'original français est conservé (WeakMap) :
 * repasser en FR restaure exactement le texte d'origine. Préférence mémorisée dans localStorage (psf_lang).
 * API : window.i18n = { lang, set(l), t(texteFr) }.
 */
(function () {
  var K = "psf_lang", lang = "fr";
  try { var v = localStorage.getItem(K); if (v === "en" || v === "fr") lang = v; } catch (e) {}

  var esc = function (x) { return x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); };
  var DICT = window.I18N_EN || {};
  // clés avec valeurs {n} : motifs pour les textes déjà assemblés (une seule chaîne), les plus longs (précis) d'abord
  var PATS = Object.keys(DICT).filter(function (k) { return /\{\d\}/.test(k); })
    .sort(function (a, b) { return b.length - a.length; })
    .map(function (k) { return [new RegExp("^" + esc(k).replace(/\\\{\d\\\}/g, "(.*?)") + "$"), DICT[k]]; });
  // mots et locutions remplacés dans n'importe quel texte (jours, mois, états…), plus longs d'abord
  var WORDS = window.I18N_WORDS || {};
  var WORDS_RE = Object.keys(WORDS).length
    ? new RegExp("(^|[^A-Za-zÀ-ÿ])(" + Object.keys(WORDS).sort(function (a, b) { return b.length - a.length; }).map(esc).join("|") + ")(?![A-Za-zÀ-ÿ])", "g")
    : null;
  var ATTRS = ["title", "placeholder", "aria-label", "alt"];
  var LETTRES = /[A-Za-zÀ-ÿ]/;
  var textes = new WeakMap(); // nœud texte -> { fr, en }
  var attrs = new WeakMap();  // élément -> { attribut: { fr, en } }

  var norm = function (s) { return s.replace(/[\s ]+/g, " ").trim(); };

  /** Nombres à la française -> anglaise : « 27 651 » -> « 27,651 », « 7,1 % » -> « 7.1% ». */
  function nombres(t) {
    return t
      .replace(/(\d)[\u202f\u00a0 ](?=\d{3}(?!\d))/g, "$1,")
      .replace(/(\d),(\d)/g, function (_, a, b) { return a + "." + b; })
      .replace(/(\d) %/g, "$1%");
  }
  // la virgule de milliers (27,651) ne doit pas être reprise comme décimale : on applique les milliers d'abord sur les groupes à espace
  function nombresSur(t) {
    return t.replace(/\d{1,3}(?:[\u202f\u00a0 ]\d{3})+(?:,\d+)?|\d+,\d+/g, function (n) {
      var ent = n, dec = "";
      var k = n.lastIndexOf(",");
      if (k >= 0) { ent = n.slice(0, k); dec = "." + n.slice(k + 1); }
      return ent.replace(/[\u202f\u00a0 ]/g, ",") + dec;
    }).replace(/(\d) %/g, "$1%");
  }
  function mots(t) { return WORDS_RE ? t.replace(WORDS_RE, function (_, a, w) { return a + WORDS[w]; }) : t; }

  /** Traduit un texte français ; null si inconnu. Espaces de début/fin conservés. */
  function traduit(txt) {
    var m = /^(\s*)([\s\S]*?)(\s*)$/.exec(txt), cle = norm(m[2]), sortie = null;
    if (!cle) return null;
    if (Object.prototype.hasOwnProperty.call(DICT, cle)) sortie = DICT[cle];
    else {
      for (var i = 0; i < PATS.length && sortie === null; i++) {
        var r = PATS[i][0].exec(cle);
        if (r) sortie = PATS[i][1].replace(/\{(\d)\}/g, function (_, k) {
          var v = r[+k + 1];
          if (v == null) return "";
          // une valeur qui est elle-même un texte connu (« Marché entier », « Km → Coordonnées ») est traduite
          return Object.prototype.hasOwnProperty.call(DICT, v) ? DICT[v] : v;
        });
      }
    }
    var base = sortie === null ? cle : sortie, fin = mots(nombresSur(base));
    if (sortie === null && fin === cle) return null;
    return m[1] + fin + m[3];
  }

  function texte(n) {
    if (n.parentNode && n.parentNode.nodeName === "TEXTAREA") return;
    var v = n.nodeValue, rec = textes.get(n);
    if (rec && v === rec.en) { if (lang === "fr") { n.nodeValue = rec.fr; textes.delete(n); } return; }
    if (lang !== "en" || !v || !/[A-Za-zÀ-ÿ0-9]/.test(v)) return;
    var t = traduit(v);
    if (t !== null && t !== v) { textes.set(n, { fr: v, en: t }); n.nodeValue = t; }
  }

  /** Élément dont les enfants sont uniquement du texte et des valeurs <span class="sc-interp"> : traduit en bloc. */
  function bloc(el) {
    var kids = el.childNodes, segs = [""], nb = 0, i, k;
    for (i = 0; i < kids.length; i++) {
      k = kids[i];
      if (k.nodeType === 3) segs[segs.length - 1] += k.nodeValue;
      else if (k.nodeType === 1 && k.className === "sc-interp") { nb++; segs.push(""); }
      else return false;
    }
    if (!nb || !LETTRES.test(segs.join(""))) return false;
    var cle = norm(segs.map(function (x, j) { return j ? "{" + (j - 1) + "}" + x : x; }).join(""));
    if (!Object.prototype.hasOwnProperty.call(DICT, cle)) return false;
    var parts = DICT[cle].split(/\{(\d)\}/); // [texte0, idx, texte1, idx, ...]
    var out = [parts[0]];
    for (i = 1; i < parts.length; i += 2) { if (+parts[i] !== (i - 1) / 2) return false; out.push(parts[i + 1]); }
    if (out.length !== segs.length) return false;
    // un nœud texte par segment : le premier porte la traduction, les suivants du même segment sont vidés
    var seg = 0, vu = false;
    for (i = 0; i < kids.length; i++) {
      k = kids[i];
      if (k.nodeType === 1) { seg++; vu = false; continue; }
      var rec = textes.get(k), v = k.nodeValue;
      if (rec && v === rec.en) { vu = true; continue; }
      var en = vu ? "" : out[seg];
      vu = true;
      textes.set(k, { fr: v, en: en });
      k.nodeValue = en;
    }
    return true;
  }

  function attribut(el, a) {
    var v = el.getAttribute(a); if (v == null) return;
    var map = attrs.get(el) || {}, rec = map[a];
    if (rec && v === rec.en) { if (lang === "fr") { el.setAttribute(a, rec.fr); delete map[a]; } return; }
    if (lang !== "en" || !/[A-Za-zÀ-ÿ0-9]/.test(v)) return;
    var t = traduit(v);
    if (t !== null && t !== v) { map[a] = { fr: v, en: t }; attrs.set(el, map); el.setAttribute(a, t); }
  }

  function parcourt(racine) {
    if (!racine) return;
    if (racine.nodeType === 3) { texte(racine); return; }
    if (racine.nodeType !== 1) return;
    var tag = racine.nodeName;
    if (tag === "SCRIPT" || tag === "STYLE") return;
    ATTRS.forEach(function (a) { if (racine.hasAttribute && racine.hasAttribute(a)) attribut(racine, a); });
    if (tag === "TEXTAREA") return; // son contenu est saisi par l'utilisateur ; seuls ses attributs (placeholder) se traduisent
    if (lang === "en" && racine.querySelector && racine.querySelector(":scope > .sc-interp")) bloc(racine);
    var w = document.createTreeWalker(racine, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
      acceptNode: function (n) { return /^(SCRIPT|STYLE)$/.test(n.nodeName) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT; }
    });
    var n;
    while ((n = w.nextNode())) {
      if (n.nodeType === 3) texte(n);
      else {
        ATTRS.forEach(function (a) { if (n.hasAttribute(a)) attribut(n, a); });
        if (lang === "en" && n.querySelector(":scope > .sc-interp")) bloc(n);
      }
    }
  }

  var file = [], planifie = false;
  function planifier(n) {
    file.push(n);
    if (planifie) return;
    planifie = true;
    requestAnimationFrame(function () { planifie = false; var f = file; file = []; f.forEach(parcourt); });
  }

  function observe() {
    new MutationObserver(function (muts) {
      if (lang !== "en") return;
      muts.forEach(function (m) {
        if (m.type === "characterData") texte(m.target);
        else if (m.type === "attributes") attribut(m.target, m.attributeName);
        else m.addedNodes.forEach(planifier);
      });
    }).observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  }

  function applique() {
    document.documentElement.lang = lang;
    parcourt(document.body);
    document.title = lang === "en" ? (traduit(window.__titreFr || document.title) || document.title) : (window.__titreFr || document.title);
  }

  window.i18n = {
    get lang() { return lang; },
    set: function (l) {
      if (l !== "fr" && l !== "en") return;
      lang = l;
      try { localStorage.setItem(K, l); } catch (e) {}
      applique();
    },
    /** Traduit un texte français dans le code : identique en FR. ctx lève une ambiguïté (« Mar » = mardi ou mars) : clé « ctx|texte ». */
    t: function (fr, ctx) {
      if (lang !== "en") return fr;
      if (ctx && Object.prototype.hasOwnProperty.call(DICT, ctx + "|" + fr)) return DICT[ctx + "|" + fr];
      var t = traduit(fr); return t === null ? fr : t;
    },
  };

  function init() { window.__titreFr = document.title; observe(); if (lang === "en") applique(); }
  if (document.body) init(); else document.addEventListener("DOMContentLoaded", init);
})();
