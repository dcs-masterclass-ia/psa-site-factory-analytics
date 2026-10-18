/**
 * Insights du tableau de bord : constats CALCULÉS (jamais rédigés par un modèle) qui ont une valeur d'action, classés par impact en leads.
 *
 * Chaque insight répond à « qu'est-ce qui change, pourquoi, et combien ça pèse ? » avec des chiffres vérifiables à l'écran :
 *   - decomposition : variation des leads = effet trafic + effet conversion (exacte : L = S × taux) ;
 *   - canal         : le canal qui porte la hausse ou la baisse de trafic, et ce que ça représente en leads ;
 *   - tunnel        : l'étape qui laisse passer moins de monde qu'à la période précédente, et les leads perdus ;
 *   - appareils     : écart de conversion entre appareils, avec le gain si on en comble la moitié ;
 *   - segment       : canal × appareil qui convertit très au-dessus de la moyenne mais pèse peu ;
 *   - saisie        : parcours marque-modèle qui s'arrête plus tôt que le parcours plaque ;
 *   - parc          : conversion sous la médiane du parc, et leads à gagner pour la rejoindre ;
 *   - rupture       : semaine hors de la fourchette habituelle (écart-type).
 * Les gains « potentiels » sont des ordres de grandeur prudents (moitié de l'écart, +20 % de volume) et sont présentés comme tels.
 * Fonction pure (français / anglais), sans dépendance au DOM : testée par tests/api/insights.test.js.
 */
(function (racine) {
  let EN = false;                                                       // langue du calcul en cours (réglée par calculeInsights)
  const L = (fr, en) => (EN ? en : fr);
  const pct = (v, d = 0) => { const t = (Math.abs(v) < 1e-9 ? 0 : v).toFixed(d); return EN ? t : t.replace(".", ","); };
  const signe = (v) => (v < 0 ? "−" : "+");
  const nf = (v) => String(Math.round(Math.abs(v))).replace(/\B(?=(\d{3})+(?!\d))/g, EN ? "," : " ");
  const gens = (v) => `${signe(v)}${nf(v)}`;
  const ARTICLE = (n) => (Math.abs(n) >= 1.5 ? "s" : "");

  /**
   * c = { en, hasCmp, L1, L0, S1, S0, canal1:{canal:sessions}, canal0, combos:[{canal,device,sessions,conversions}], steps1:[6], steps0:[6], etapes:[6 libellés],
   *       entree:{immat:[5], mm:[5]}|null, semaine:{actuelle, moyenne, ecartType}|null, parc:{rate, mediane, rang, total}|null, singleSite }
   * -> [{ id, type: "alerte"|"cause"|"opportunite", titre, texte, leads, lien }] trié par |leads| décroissant
   */
  function calculeInsights(c) {
    EN = !!c.en;
    const out = [];
    const S1 = c.S1 || 0, S0 = c.S0 || 0, L1 = c.L1 || 0, L0 = c.L0 || 0;
    const taux1 = S1 > 0 ? L1 / S1 : 0;

    // 1. décomposition de la variation des leads
    if (c.hasCmp && L0 > 0 && S0 > 0 && S1 > 0) {
      const c0 = L0 / S0, c1 = L1 / S1;
      const delta = L1 - L0, dTrafic = (S1 - S0) * c0, dConv = S1 * (c1 - c0);
      if (Math.abs(delta) >= Math.max(30, 0.08 * L0)) {
        const traficDomine = Math.abs(dTrafic) >= Math.abs(dConv);
        const ptConv = (c1 - c0) * 100;
        const sessPct = `${signe(S1 - S0)}${pct(Math.abs((S1 - S0) / S0 * 100), 1)} %`;
        const convTxt = `${signe(ptConv)}${pct(Math.abs(ptConv), 2)} pt`;
        const principal = traficDomine
          ? L(`c'est surtout le trafic de reprise (${sessPct} de sessions, ${gens(dTrafic)} lead${ARTICLE(dTrafic)}), la conversion (${convTxt}) ${dConv * delta >= 0 ? "amplifie" : "compense"} de ${gens(dConv)}`,
              `mostly the trade-in site traffic (${sessPct} sessions, ${gens(dTrafic)} lead${ARTICLE(dTrafic)}), conversion (${convTxt}) ${dConv * delta >= 0 ? "adds" : "offsets"} ${gens(dConv)}`)
          : L(`c'est surtout la conversion (${convTxt}, ${gens(dConv)} lead${ARTICLE(dConv)}), le trafic (${sessPct}) ${dTrafic * delta >= 0 ? "amplifie" : "compense"} de ${gens(dTrafic)}`,
              `mostly conversion (${convTxt}, ${gens(dConv)} lead${ARTICLE(dConv)}), traffic (${sessPct}) ${dTrafic * delta >= 0 ? "adds" : "offsets"} ${gens(dTrafic)}`);
        out.push({ id: "decomposition", type: delta < 0 ? "alerte" : "cause",
          titre: delta < 0 ? L("Leads en baisse : d'où ça vient", "Leads down: where it comes from") : L("Leads en hausse : d'où ça vient", "Leads up: where it comes from"),
          texte: `${L("Leads GA", "GA leads")} ${gens(delta)} (${signe(delta)}${pct(Math.abs(delta / L0 * 100), 1)} %) : ${principal}.`, leads: delta, lien: "contrib" });
        // la conversion va à contre-courant du total (ex. leads en hausse grâce au trafic, mais conversion en recul) : c'est un constat à part entière
        if (traficDomine && dConv * delta < 0 && Math.abs(dConv) >= Math.max(30, 0.08 * L0)) {
          out.push({ id: "conversion", type: dConv < 0 ? "alerte" : "cause",
            titre: dConv < 0 ? L("Conversion en recul malgré le trafic", "Conversion down despite traffic") : L("Conversion en hausse malgré le recul du trafic", "Conversion up despite lower traffic"),
            texte: dConv < 0
              ? L(`Le taux de conversion recule de ${pct(Math.abs(ptConv), 2)} pt (${pct(c0 * 100, 2)} % → ${pct(c1 * 100, 2)} %) : à trafic constant, ${nf(dConv)} leads de moins, masqués par la hausse des sessions.`,
                  `The conversion rate is down ${pct(Math.abs(ptConv), 2)} pt (${pct(c0 * 100, 2)}% → ${pct(c1 * 100, 2)}%): at constant traffic, ${nf(dConv)} fewer leads, hidden by higher sessions.`)
              : L(`Le taux de conversion progresse de ${pct(Math.abs(ptConv), 2)} pt (${pct(c0 * 100, 2)} % → ${pct(c1 * 100, 2)} %) : ${nf(dConv)} leads de plus, qui limitent l'effet de la baisse des sessions.`,
                  `The conversion rate is up ${pct(Math.abs(ptConv), 2)} pt (${pct(c0 * 100, 2)}% → ${pct(c1 * 100, 2)}%): ${nf(dConv)} more leads, limiting the effect of lower sessions.`),
            leads: dConv, lien: "conv" });
        }
      }
    }

    // 2. canal moteur de la variation de trafic
    if (c.hasCmp && c.canal1 && c.canal0 && S0 > 0 && taux1 > 0) {
      const dS = S1 - S0;
      let top = null;
      for (const ch of new Set([...Object.keys(c.canal1), ...Object.keys(c.canal0)])) {
        const a = c.canal1[ch] || 0, b = c.canal0[ch] || 0, d = a - b;
        if (!top || Math.abs(d) > Math.abs(top.d)) top = { ch, a, b, d };
      }
      if (top && Math.abs(top.d) >= 300 && Math.abs(top.d) >= 0.2 * Math.max(Math.abs(dS), 1) && (top.b === 0 || Math.abs(top.d) / top.b >= 0.15)) {
        const partPct = Math.min(100, Math.round(Math.abs(top.d / dS) * 100));
        const part = Math.abs(dS) > 0 && top.d * dS > 0
          ? L(` (${partPct} % de la ${dS < 0 ? "baisse" : "hausse"} totale du trafic)`, ` (${partPct}% of the total traffic ${dS < 0 ? "drop" : "increase"})`) : "";
        const leads = top.d * taux1;
        const rel = top.b > 0 ? `${signe(top.d)}${pct(Math.abs(top.d / top.b * 100), 0)} %` : L("nouveau", "new");
        out.push({ id: "canal", type: top.d < 0 ? "alerte" : "cause",
          titre: top.d < 0 ? L(`${top.ch} : trafic en recul`, `${top.ch}: traffic down`) : L(`${top.ch} : trafic en hausse`, `${top.ch}: traffic up`),
          texte: L(`${top.ch} : ${gens(top.d)} sessions (${rel}) vs la période précédente${part}, soit environ ${gens(leads)} leads au taux de conversion actuel.`,
                   `${top.ch}: ${gens(top.d)} sessions (${rel}) vs the previous period${part}, about ${gens(leads)} leads at the current conversion rate.`),
          leads, lien: "trend" });
      }
    }

    // 3. étape du tunnel qui se dégrade vs la période précédente
    if (c.hasCmp && c.steps1 && c.steps0 && c.steps1.length === 6 && c.steps0.length === 6) {
      let pire = null;
      for (let i = 1; i < 6; i++) {
        if (c.steps1[i - 1] < 500 || c.steps0[i - 1] < 500 || !c.steps0[i]) continue;
        const t1 = c.steps1[i] / c.steps1[i - 1], t0 = c.steps0[i] / c.steps0[i - 1];
        const perdus = (t0 - t1) * c.steps1[i - 1] * (c.steps1[i] > 0 ? c.steps1[5] / c.steps1[i] : 0);
        if (t0 > 0 && t1 / t0 - 1 <= -0.06 && perdus >= 20 && (!pire || perdus > pire.perdus)) pire = { i, t1, t0, perdus };
      }
      if (pire) {
        const nom = c.etapes ? c.etapes[pire.i] : "#" + (pire.i + 1);
        out.push({ id: "tunnel", type: "alerte", titre: L("Une étape du tunnel laisse passer moins de monde", "A funnel step lets fewer people through"),
          texte: L(`Étape « ${nom} » : ${pct(pire.t1 * 100, 1)} % des visiteurs de l'étape précédente passent, contre ${pct(pire.t0 * 100, 1)} % la période précédente (${signe(pire.t1 - pire.t0)}${pct(Math.abs(pire.t1 - pire.t0) * 100, 1)} pt) : environ ${nf(pire.perdus)} leads perdus.`,
                   `Step “${nom}”: ${pct(pire.t1 * 100, 1)}% of visitors from the previous step get through, versus ${pct(pire.t0 * 100, 1)}% in the previous period (${signe(pire.t1 - pire.t0)}${pct(Math.abs(pire.t1 - pire.t0) * 100, 1)} pt): about ${nf(pire.perdus)} leads lost.`),
          leads: -pire.perdus, lien: "leaks" });
      }
    }

    // 4. écart de conversion entre appareils, 5. segment canal × appareil performant mais peu volumineux
    const combos = (c.combos || []).filter((r) => r.sessions > 0);
    if (combos.length) {
      const parApp = {};
      combos.forEach((r) => { const a = parApp[r.device] || (parApp[r.device] = { s: 0, v: 0 }); a.s += r.sessions; a.v += r.conversions; });
      const apps = Object.entries(parApp).filter(([, a]) => a.s >= 300).map(([d, a]) => ({ d, s: a.s, taux: a.v / a.s })).sort((x, y) => y.taux - x.taux);
      const total = Object.values(parApp).reduce((s, a) => s + a.s, 0);
      if (apps.length >= 2) {
        const haut = apps[0], bas = apps[apps.length - 1];
        const gain = 0.5 * (haut.taux - bas.taux) * bas.s;
        if (haut.taux > bas.taux * 1.25 && gain >= 20 && bas.s / total >= 0.1) out.push({ id: "appareils", type: "opportunite",
          titre: L(`Conversion ${bas.d} en retrait`, `${bas.d} conversion lagging`),
          texte: L(`Sur ${bas.d} (${pct(bas.s / total * 100, 0)} % des sessions), ${pct(bas.taux * 100, 2)} % convertissent contre ${pct(haut.taux * 100, 2)} % sur ${haut.d} : combler la moitié de l'écart représente environ ${nf(gain)} leads de plus sur la période.`,
                   `On ${bas.d} (${pct(bas.s / total * 100, 0)}% of sessions), ${pct(bas.taux * 100, 2)}% convert versus ${pct(haut.taux * 100, 2)}% on ${haut.d}: closing half of the gap is worth about ${nf(gain)} more leads over the period.`),
          leads: gain, lien: "device" });
      }
      const S = combos.reduce((s, r) => s + r.sessions, 0), V = combos.reduce((s, r) => s + r.conversions, 0);
      const moy = S > 0 ? V / S : 0;
      const seg = combos.filter((r) => r.sessions >= 100 && r.sessions / S < 0.1 && moy > 0 && r.conversions / r.sessions >= 2 * moy)
        .map((r) => ({ ...r, taux: r.conversions / r.sessions, gain: 0.2 * r.conversions })).sort((x, y) => y.gain - x.gain)[0];
      if (seg && seg.gain >= 10) out.push({ id: "segment", type: "opportunite", titre: L(`${seg.canal} × ${seg.device} : à développer`, `${seg.canal} × ${seg.device}: worth growing`),
        texte: L(`${seg.canal} × ${seg.device} convertit ${pct(seg.taux / moy, 1)}× la moyenne (${pct(seg.taux * 100, 2)} %) mais ne pèse que ${pct(seg.sessions / S * 100, 1)} % des sessions : +20 % de volume sur ce segment ≈ ${nf(seg.gain)} leads.`,
                 `${seg.canal} × ${seg.device} converts ${pct(seg.taux / moy, 1)}× the average (${pct(seg.taux * 100, 2)}%) but is only ${pct(seg.sessions / S * 100, 1)}% of sessions: +20% volume on this segment ≈ ${nf(seg.gain)} leads.`),
        leads: seg.gain, lien: "device" });
    }

    // 6. parcours marque / modèle
    if (c.entree && c.entree.mm && c.entree.immat && c.entree.mm[0] >= 100 && c.entree.immat[0] >= 300) {
      const mm = c.entree.mm, im = c.entree.immat;
      const tMM = mm[4] / mm[0], tIM = im[4] / im[0], part = mm[0] / (mm[0] + im[0]);
      const gain = 0.5 * (tIM - tMM) * mm[0];
      if (tIM - tMM >= 0.05 && gain >= 10) out.push({ id: "saisie", type: "opportunite", titre: L("Parcours marque / modèle : abandon plus précoce", "Make / model journey: earlier drop-off"),
        texte: L(`${pct(part * 100, 0)} % des visiteurs de « Version » passent par marque / modèle (${nf(mm[0])}) : ${pct(tMM * 100, 1)} % vont jusqu'à l'estimation contre ${pct(tIM * 100, 1)} % en immatriculation. Réduire l'écart de moitié ≈ ${nf(gain)} estimations de plus.`,
                 `${pct(part * 100, 0)}% of “Version” visitors use make / model (${nf(mm[0])}): ${pct(tMM * 100, 1)}% reach the estimate versus ${pct(tIM * 100, 1)}% with the registration plate. Halving the gap ≈ ${nf(gain)} more estimates.`),
        leads: gain, lien: null });
    }

    // 7. position vs parc
    if (c.parc && c.singleSite && c.parc.mediane > 0 && S1 >= 2000 && c.parc.rate < c.parc.mediane - 0.8) {
      const gain = (c.parc.mediane - c.parc.rate) / 100 * S1;
      if (gain >= 20) out.push({ id: "parc", type: "opportunite", titre: L("Conversion sous la médiane du parc", "Conversion below the portfolio median"),
        texte: L(`Conversion ${pct(c.parc.rate, 1)} %, ${c.parc.rang}e sur ${c.parc.total} sites, sous la médiane du parc (${pct(c.parc.mediane, 1)} %). Rejoindre la médiane représente environ ${nf(gain)} leads de plus sur la période.`,
                 `Conversion ${pct(c.parc.rate, 1)}%, ranked ${c.parc.rang} of ${c.parc.total} sites, below the portfolio median (${pct(c.parc.mediane, 1)}%). Reaching the median is worth about ${nf(gain)} more leads over the period.`),
        leads: gain, lien: null });
    }

    // 8. rupture de la semaine
    const w = c.semaine;
    if (w && w.moyenne >= 50 && w.ecartType > 0) {
      const z = (w.actuelle - w.moyenne) / w.ecartType, ecart = w.actuelle - w.moyenne;
      if (Math.abs(z) >= 2 && Math.abs(ecart) / w.moyenne >= 0.15) out.push({ id: "rupture", type: ecart < 0 ? "alerte" : "cause",
        titre: ecart < 0 ? L("Semaine nettement sous la normale", "Week clearly below normal") : L("Semaine nettement au-dessus de la normale", "Week clearly above normal"),
        texte: L(`Leads des 7 derniers jours : ${nf(w.actuelle)} contre ${nf(w.moyenne)} attendus (± ${nf(w.ecartType)}), soit ${gens(ecart)} (${signe(ecart)}${pct(Math.abs(ecart / w.moyenne * 100), 0)} %), un écart de ${pct(Math.abs(z), 1)} écarts-types.`,
                 `Leads over the last 7 days: ${nf(w.actuelle)} versus ${nf(w.moyenne)} expected (± ${nf(w.ecartType)}), i.e. ${gens(ecart)} (${signe(ecart)}${pct(Math.abs(ecart / w.moyenne * 100), 0)}%), a gap of ${pct(Math.abs(z), 1)} standard deviations.`),
        leads: ecart, lien: "alerts" });
    }

    return out.sort((a, b) => Math.abs(b.leads) - Math.abs(a.leads));
  }

  const api = { calculeInsights };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  racine.psfInsights = api;
})(typeof window !== "undefined" ? window : globalThis);
