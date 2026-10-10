"""Analyse calculée par règles (aucune IA, coût nul) : décompositions chiffrées + saisonnalité + dynamique + mix, puis un message clé,
des lectures (hypothèses signalées) et des recommandations rattachées au facteur qui domine.

Méthode, pour une marque et une période de référence :
 1. Leads = sessions × ratio leads/session -> effet trafic et effet ratio (en leads, somme = écart total).
 2. Chaîne GA4 utilisateurs -> In Journey -> hot leads : contribution (log) de l'audience, de l'entrée dans le tunnel et de l'estimation.
 3. Canaux : contribution de chaque canal à l'écart de sessions, évolution du mix.
 4. Saisonnalité : la même évolution (période vs précédente) observée les 2 années précédentes ; l'écart actuel est-il dans la norme ?
 5. Dynamique : mois complets de la période vs N-1, accélération ou ralentissement du dernier mois.
 6. Mix projets d'achat et sources d'acquisition ; poids de la marque et surperformance vs le périmètre.
Règle d'or : aucun pourcentage sous 100 de base (« n.s. »), aucune cause affirmée (« Hypothèse : », « Point d'attention : »).
"""

import math

from .donnees import PROJETS

SEUIL_BASE = 100
SEUIL_ECART = 10          # % : variation significative
SEUIL_PTS = 3             # points de part : glissement de mix significatif
DOMINE = 0.6              # un facteur « domine » s'il porte au moins 60 % de l'écart


def _var(c, r):
    """Variation en % (arrondie à l'entier, comme à l'affichage : ce qui est dit « −10 % » est classé comme tel) ; None si base < 100."""
    return None if (r is None or c is None or r < SEUIL_BASE) else round((c - r) / r * 100)


def _sg(t, v):
    """Nombre signé lisible : +86 / −468."""
    return ("+" if v > 0 else "−" if v < 0 else "") + t.nb(abs(v))


class _Marque:
    """Calculs d'une marque (ou du périmètre entier si m=None) sur la période et ses références."""

    def __init__(self, ctx, m=None):
        self.ctx, self.m, self.d, self.t = ctx, m, ctx.d, ctx.t
        self.per = ctx.per
        self.refs = ctx.refs
        d = self.d
        self.L = lambda p: d.leads_total(p, m)
        self.S = lambda p: sum(d.canaux(p, m).values()) if m else sum(sum(d.canaux(p, x).values()) for x in d.marques)
        self.proj = lambda p: d.leads(p, m)

    def fr(self, a, b):
        return a if self.ctx.langue == "fr" else b


def _decomp(L, Lc, Lr, Sc, Sr):
    """-> (effet_trafic, effet_ratio) en leads ; None si la référence est trop faible."""
    if Sr < SEUIL_BASE or Lr < SEUIL_BASE or Sc <= 0:
        return None
    et = (Sc - Sr) * Lr / Sr
    return et, (Lc - Lr) - et


def _saisonnier(x, per):
    """Évolutions de la même période vs sa précédente, pour les 2 années antérieures -> liste de %."""
    if per.type == "annee":
        return []
    out = []
    for k in (1, 2):
        p = type(per)(per.type, per.annee - k, per.indice)
        v = _var(x.L(p), x.L(p.precedente()))
        if v is not None:
            out.append(v)
    return out


def _mois_complets(ctx, x):
    """[(libellé, valeur courante, valeur N-1)] des mois entièrement écoulés de la période."""
    from .periodes import Periode, MOIS_COURTS
    dernier = ctx.d.dernier_jour_leads()
    out = []
    for a, mo in ctx.per.mois():
        if not dernier or Periode("mois", a, mo).fin.isoformat() > dernier:
            continue
        cur = ctx.d.leads_mensuels(a, x.m)[mo - 1]
        ref = ctx.d.leads_mensuels(a - 1, x.m)[mo - 1]
        lib = MOIS_COURTS[ctx.langue][mo - 1] if isinstance(MOIS_COURTS, dict) else MOIS_COURTS[mo - 1]
        out.append((lib, cur, ref))
    return out


def _serie(ctx, f, nb=4, mini=SEUIL_BASE):
    """[(année, valeur)] de la même période sur les années passées (valeurs >= mini) puis l'année courante en dernier."""
    per = ctx.per
    out = []
    for k in range(nb, -1, -1):
        v = f(type(per)(per.type, per.annee - k, per.indice))
        if v is not None and v >= mini:
            out.append((per.annee - k, v))
    return out


def _rang(serie):
    """Place de la dernière valeur : 'bas' (plus bas de la série), 'haut', ou None ; + année de référence."""
    if len(serie) < 3:
        return None, None
    cur = serie[-1][1]
    passees = serie[:-1]
    if cur <= min(v for _, v in passees):
        return "bas", serie[0][0]
    if cur >= max(v for _, v in passees):
        return "haut", serie[0][0]
    return None, None


def _historique(ctx, x, m):
    """Contexte long : même période sur les années passées (leads, sessions, conversion), 12 mois glissants, Search Console, V2.
    -> (constats, lectures, signaux) ; signaux = {'sessions': 'bas'|'haut'|None, 'leads': ..., 'conv': ...}"""
    t, d, F = ctx.t, ctx.d, x.fr
    per = ctx.per
    c, l, sig = [], [], {}
    traj = lambda serie, fmt=t.nb: " → ".join(f"{a} : {fmt(v)}" for a, v in serie)
    # leads
    sl = _serie(ctx, x.L)
    if len(sl) >= 3:
        r, a0 = _rang(sl)
        sig["leads"] = r
        fin = F(" (plus bas niveau de la série)", " (lowest level in the series)") if r == "bas" else F(" (plus haut niveau de la série)", " (highest level in the series)") if r == "haut" else ""
        c.append(F(f"Historique des leads, même période : {traj(sl)}{fin}.", f"Lead history, same period: {traj(sl)}{fin}."))
    # sessions (séries GA4 : seulement les années entièrement couvertes)
    premier = d.premier_jour_trafic()
    ss = [(a, v) for a, v in _serie(ctx, x.S) if premier and f"{a}-{per.debut.month:02d}-01" >= premier]
    if len(ss) >= 3:
        r, a0 = _rang(ss)
        sig["sessions"] = r
        fin = F(" (plus bas niveau de la série)", " (lowest level in the series)") if r == "bas" else F(" (plus haut niveau de la série)", " (highest level in the series)") if r == "haut" else ""
        c.append(F(f"Historique des sessions : {traj(ss)}{fin}.", f"Session history: {traj(ss)}{fin}."))
    # conversion quotidienne GA4 (estimation ÷ accueil) : années où l'étape estimation existe
    cv = []
    for k in range(4, -1, -1):
        p = type(per)(per.type, per.annee - k, per.indice)
        a, e = d.funnel(p, m)
        if a >= SEUIL_BASE and e > 0:
            cv.append((p.annee, e / a * 100))
    if len(cv) >= 3:
        r, _ = _rang(cv)
        sig["conv"] = r
        fin = F(" (plus haut niveau de la série)", " (highest level in the series)") if r == "haut" else F(" (plus bas niveau de la série)", " (lowest level in the series)") if r == "bas" else ""
        c.append(F(f"Historique du taux de conversion (estimations ÷ visiteurs de l'accueil) : {traj(cv, lambda v: t.pct(v, 1))}{fin}.",
                   f"Conversion history (estimates ÷ home visitors): {traj(cv, lambda v: t.pct(v, 1))}{fin}."))
    # 12 mois glissants
    dernier = d.dernier_jour_leads()
    if dernier:
        from datetime import date
        fin = date.fromisoformat(dernier)
        a1 = fin.year * 12 + fin.month - 1
        def somme(debut, n):
            tot = 0
            for k in range(debut, debut + n):
                a, mo = divmod(k, 12)
                tot += d.leads_mensuels(a, m)[mo]
            return tot
        # derniers 12 mois complets (le mois du dernier jour n'est complet que si c'est le dernier jour du mois)
        import calendar
        fin_complet = a1 if fin.day == calendar.monthrange(fin.year, fin.month)[1] else a1 - 1
        r12, p12 = somme(fin_complet - 11, 12), somme(fin_complet - 23, 12)
        v12 = _var(r12, p12)
        if v12 is not None:
            c.append(F(f"12 mois glissants : {t.nb(r12)} leads ({t.pct(v12, 0, signe=True)} vs les 12 mois précédents).", f"Rolling 12 months: {t.nb(r12)} leads ({t.pct(v12, 0, signe=True)} vs previous 12 months)."))
            sig["roulant"] = v12
    # Search Console
    g0 = d.gsc(per, m)
    if g0:
        parts = []
        for cle, p in ctx.refs:
            g1 = d.gsc(p, m)
            if g1 and g1[1] >= SEUIL_BASE:
                vc, vi = _var(g0[0], g1[0]), _var(g0[1], g1[1])
                parts.append(F(f"clics {t.pct(vc, 0, signe=True) if vc is not None else 'n.s.'}, impressions {t.pct(vi, 0, signe=True) if vi is not None else 'n.s.'}, position {t.dec(g0[2], 1)} (vs {t.dec(g1[2], 1)}) vs {ctx.et(p)}",
                               f"clicks {t.pct(vc, 0, signe=True) if vc is not None else 'n.s.'}, impressions {t.pct(vi, 0, signe=True) if vi is not None else 'n.s.'}, position {t.dec(g0[2], 1)} (vs {t.dec(g1[2], 1)}) vs {ctx.et(p)}"))
        if parts:
            c.append(F("Search Console (visibilité naturelle) : ", "Search Console (organic visibility): ") + " ; ".join(parts) + ".")
            sig["gsc"] = True
    # V2
    if m:
        v2 = d.v2_dates(m)
        if v2:
            ds = ", ".join(f"{p} {v[8:10]}/{v[5:7]}/{v[:4]}" for p, v in sorted(v2.items()))
            dans = any(per.debut.isoformat() <= v <= per.fin.isoformat() for v in v2.values())
            c.append(F(f"Parcours V2 déployé : {ds}.", f"V2 journey deployed: {ds}.") + (F(" Basculement pendant la période : les mesures mélangent ancien et nouveau parcours.", " Switch during the period: measures mix old and new journey.") if dans else ""))
            if dans:
                l.append(F("Point d'attention : la bascule V2 a eu lieu pendant la période ; comparer les périodes avant/après (diapositive V2) avant de conclure sur la tendance.", "Watch point: the V2 switch happened during the period; compare before/after (V2 slide) before concluding on the trend."))
    # lectures issues de l'historique
    if sig.get("sessions") == "bas":
        l.append(F("Point d'attention : l'audience est au plus bas niveau de l'historique disponible pour cette période ; le recul n'est pas une simple variation ponctuelle.", "Watch point: audience is at its lowest level in the available history for this period; the decline is not a one-off variation."))
    if sig.get("sessions") == "bas" and sig.get("leads") not in ("bas", None) and sig.get("conv") == "haut":
        l.append(F("Les leads résistent grâce à une conversion au plus haut de l'historique : l'efficacité du parcours compense en partie la baisse d'audience.", "Leads hold thanks to conversion at its historical high: journey efficiency partly offsets the audience decline."))
    if sig.get("conv") == "bas":
        l.append(F("Point d'attention : la conversion est au plus bas de l'historique ; le parcours est à auditer en priorité.", "Watch point: conversion is at its historical low; the journey should be audited first."))
    if sig.get("roulant") is not None and sig["roulant"] <= -SEUIL_ECART:
        l.append(F("La tendance de fond (12 mois glissants) est elle aussi en baisse : le recul ne se limite pas à cette période.", "The underlying trend (rolling 12 months) is also down: the decline is not limited to this period."))
    elif sig.get("roulant") is not None and sig["roulant"] >= SEUIL_ECART:
        l.append(F("La tendance de fond (12 mois glissants) est en hausse : la période s'inscrit dans une dynamique plus large.", "The underlying trend (rolling 12 months) is up: the period is part of a broader momentum."))
    return c, l, sig


def analyse_marque(ctx, m):
    """-> {"message","constats","lectures","recommandations"} ou None si le volume est trop faible."""
    x = _Marque(ctx, m)
    t, d, F = ctx.t, ctx.d, x.fr
    Lc, Sc = x.L(ctx.per), x.S(ctx.per)
    if Lc < SEUIL_BASE and Sc < SEUIL_BASE:
        return None
    c, l, r = [], [], []
    message = None
    pa = ctx.refs[0][1] if ctx.refs else None
    # --- chiffres de base
    evs = []
    for _, p in ctx.refs:
        v = _var(Lc, x.L(p))
        if v is not None:
            evs.append(f"{t.pct(v, 0, signe=True)} vs {ctx.et(p)}")
    c.append(F(f"{t.nb(Lc)} leads sur {ctx.et(ctx.per)}", f"{t.nb(Lc)} leads in {ctx.et(ctx.per)}") + (f" ({' ; '.join(evs)})" if evs else "")
             + (F(" : volume trop faible pour conclure.", ": volume too low to conclude.") if Lc < SEUIL_BASE else "."))
    if Lc < SEUIL_BASE:
        r.append(F("Cumuler sur une période plus longue avant toute décision sur cette marque.", "Accumulate a longer period before any decision on this brand."))
        return {"message": F("Volume de leads trop faible pour une lecture fiable.", "Lead volume too low for a reliable reading."),
                "constats": c, "lectures": [], "recommandations": r}
    vl = vs = None
    canaux_c = d.canaux(ctx.per, m)
    if pa is not None:
        Lr, Sr = x.L(pa), x.S(pa)
        vl, vs = _var(Lc, Lr), _var(Sc, Sr)
        # 1. effet trafic / ratio
        dec = _decomp(None, Lc, Lr, Sc, Sr)
        dom = None
        if dec and abs(Lc - Lr) >= 30:
            et, er = dec
            tot = abs(et) + abs(er)
            part_t = abs(et) / tot if tot else 0
            dom = "trafic" if part_t >= DOMINE else ("ratio" if part_t <= 1 - DOMINE else "mixte")
            c.append(F(f"Écart de {_sg(t, Lc - Lr)} leads vs {ctx.et(pa)} : {_sg(t, et)} dus au trafic (sessions), {_sg(t, er)} dus au ratio leads/sessions ({t.dec(Lr / Sr * 100, 1)} % → {t.dec(Lc / Sc * 100, 1)} %).",
                       f"Gap of {_sg(t, Lc - Lr)} leads vs {ctx.et(pa)}: {_sg(t, et)} from traffic (sessions), {_sg(t, er)} from the leads/sessions ratio ({t.dec(Lr / Sr * 100, 1)}% → {t.dec(Lc / Sc * 100, 1)}%)."))
        # 2. chaîne GA4
        uc, ur = d.utilisateurs(ctx.per, m), d.utilisateurs(pa, m)
        chaine = None
        if uc and ur and min(uc["utilisateurs"], ur["utilisateurs"], uc["in_journey"], ur["in_journey"], uc["hot_leads"], ur["hot_leads"]) >= 1:
            fa = math.log(uc["utilisateurs"] / ur["utilisateurs"])
            fe = math.log((uc["in_journey"] / uc["utilisateurs"]) / (ur["in_journey"] / ur["utilisateurs"]))
            fh = math.log((uc["hot_leads"] / uc["in_journey"]) / (ur["hot_leads"] / ur["in_journey"]))
            chaine = sorted([(abs(fa), "audience", fa), (abs(fe), "entrée", fe), (abs(fh), "estimation", fh)], reverse=True)
            ent_c, ent_r = uc["in_journey"] / uc["utilisateurs"] * 100, ur["in_journey"] / ur["utilisateurs"] * 100
            est_c, est_r = uc["hot_leads"] / uc["in_journey"] * 100, ur["hot_leads"] / ur["in_journey"] * 100
            c.append(F(f"Parcours : {t.nb(uc['utilisateurs'])} utilisateurs ({t.evol(uc['utilisateurs'], ur['utilisateurs'])[0]}), {t.pct(ent_c, 0)} entrent dans le tunnel ({t.pts(ent_c - ent_r)}), "
                       f"{t.pct(est_c, 0)} déposent une estimation ({t.pts(est_c - est_r)}) : {t.nb(uc['hot_leads'])} hot leads.",
                       f"Journey: {t.nb(uc['utilisateurs'])} users ({t.evol(uc['utilisateurs'], ur['utilisateurs'])[0]}), {t.pct(ent_c, 0)} enter the funnel ({t.pts(ent_c - ent_r)}), "
                       f"{t.pct(est_c, 0)} submit an estimate ({t.pts(est_c - est_r)}): {t.nb(uc['hot_leads'])} hot leads."))
        # 3. canaux
        ref_can = d.canaux(pa, m)
        delta = {k: canaux_c.get(k, 0) - ref_can.get(k, 0) for k in set(canaux_c) | set(ref_can)}
        dtot = sum(delta.values())
        contrib = sorted(delta.items(), key=lambda kv: -abs(kv[1]))
        if abs(dtot) >= SEUIL_BASE and contrib:
            k0, v0 = contrib[0]
            if v0 * dtot > 0 and abs(v0) / abs(dtot) >= 0.3:
                c.append(F(f"{k0} explique {t.pct(abs(v0) / abs(dtot) * 100, 0)} de l'écart de sessions ({_sg(t, v0)} sur {_sg(t, dtot)}).",
                           f"{k0} accounts for {t.pct(abs(v0) / abs(dtot) * 100, 0)} of the session gap ({_sg(t, v0)} out of {_sg(t, dtot)})."))
        sc_ = sum(canaux_c.values()) or 1
        sr_ = sum(ref_can.values()) or 1
        glis = sorted(((canaux_c.get(k, 0) / sc_ - ref_can.get(k, 0) / sr_) * 100, k) for k in set(canaux_c) | set(ref_can))
        gl = [(v, k) for v, k in glis if abs(v) >= SEUIL_PTS and max(canaux_c.get(k, 0), ref_can.get(k, 0)) >= SEUIL_BASE]
        if gl:
            v, k = max(gl, key=lambda a: abs(a[0]))
            c.append(F(f"Mix des canaux : {k} passe de {t.pct(ref_can.get(k, 0) / sr_ * 100, 0)} à {t.pct(canaux_c.get(k, 0) / sc_ * 100, 0)} des sessions ({t.pts(v)}).",
                       f"Channel mix: {k} goes from {t.pct(ref_can.get(k, 0) / sr_ * 100, 0)} to {t.pct(canaux_c.get(k, 0) / sc_ * 100, 0)} of sessions ({t.pts(v)})."))
        # 4. projets
        pc, pr = x.proj(ctx.per), x.proj(pa)
        dp = {k: pc[k] - pr[k] for k in pc}
        if abs(Lc - Lr) >= 30 and sum(abs(v) for v in dp.values()):
            kp, vp = max(dp.items(), key=lambda kv: abs(kv[1]) if kv[1] * (Lc - Lr) > 0 else -1)
            if vp * (Lc - Lr) > 0 and abs(vp) / abs(Lc - Lr) >= 0.5:
                reste = (Lc - Lr) - vp
                if abs(vp) > abs(Lc - Lr):
                    c.append(F(f"L'écart vient de {t[kp]} ({_sg(t, vp)} leads) ; les autres projets le compensent en partie ({_sg(t, reste)}).",
                               f"The gap comes from {t[kp]} ({_sg(t, vp)} leads); other projects partly offset it ({_sg(t, reste)})."))
                else:
                    c.append(F(f"{t[kp]} porte {t.pct(abs(vp) / abs(Lc - Lr) * 100, 0)} de l'écart de leads ({_sg(t, vp)}).", f"{t[kp]} accounts for {t.pct(abs(vp) / abs(Lc - Lr) * 100, 0)} of the lead gap ({_sg(t, vp)})."))
        sh_c, sh_r = pc["VN"] / Lc * 100, (pr["VN"] / Lr * 100 if Lr else None)
        if sh_r is not None and abs(sh_c - sh_r) >= SEUIL_PTS:
            c.append(F(f"Mix des projets : la part de New cars passe de {t.pct(sh_r, 0)} à {t.pct(sh_c, 0)} ({t.pts(sh_c - sh_r)}).", f"Project mix: the New cars share goes from {t.pct(sh_r, 0)} to {t.pct(sh_c, 0)} ({t.pts(sh_c - sh_r)})."))
        # 5. saisonnalité
        sais = _saisonnier(x, ctx.per)
        norme = None
        if sais and vl is not None:
            lo, hi = min(sais), max(sais)
            norme = (lo - 5) <= vl <= (hi + 5)
            c.append(F(f"Saisonnalité : sur les deux années précédentes, cette période a évolué de {t.pct(lo, 0, signe=True)} à {t.pct(hi, 0, signe=True)} vs sa précédente ; cette année {t.pct(vl, 0, signe=True)}"
                       f" ({'dans la norme saisonnière' if norme else 'hors de la norme saisonnière'}).",
                       f"Seasonality: over the previous two years this period moved {t.pct(lo, 0, signe=True)} to {t.pct(hi, 0, signe=True)} vs its predecessor; this year {t.pct(vl, 0, signe=True)}"
                       f" ({'within the seasonal norm' if norme else 'outside the seasonal norm'})."))
        # 6. dynamique mensuelle
        mois = _mois_complets(ctx, x)
        yoy = [(lib, _var(a, b)) for lib, a, b in mois]
        yoy_ok = [(lib, v) for lib, v in yoy if v is not None]
        if len(yoy_ok) >= 2:
            (l0, v0), (l1, v1) = yoy_ok[0], yoy_ok[-1]
            c.append(F(f"Dynamique : {l0} {t.pct(v0, 0, signe=True)} vs N-1, {l1} {t.pct(v1, 0, signe=True)} vs N-1 : "
                       + ("l'écart se creuse." if v1 < v0 - 5 else "l'écart se résorbe." if v1 > v0 + 5 else "écart stable."),
                       f"Momentum: {l0} {t.pct(v0, 0, signe=True)} vs LY, {l1} {t.pct(v1, 0, signe=True)} vs LY: " + ("the gap is widening." if v1 < v0 - 5 else "the gap is closing." if v1 > v0 + 5 else "gap stable.")))
        # 7. sources
        if d.acquisition_disponible(ctx.per) and d.acquisition_disponible(pa):
            sc2 = {k: sum(v.values()) for k, v in d.sources(ctx.per, m).items()}
            sr2 = {k: sum(v.values()) for k, v in d.sources(pa, m).items()}
            tc2, tr2 = sum(sc2.values()), sum(sr2.values())
            if tc2 >= SEUIL_BASE and tr2 >= SEUIL_BASE:
                gs = [((sc2[k] / tc2 - sr2[k] / tr2) * 100, k) for k in sc2 if k != "Autre"]
                v, k = max(gs, key=lambda a: abs(a[0]))
                if abs(v) >= SEUIL_PTS:
                    c.append(F(f"Sources des leads : {k} passe de {t.pct(sr2[k] / tr2 * 100, 0)} à {t.pct(sc2[k] / tc2 * 100, 0)} ({t.pts(v)}).", f"Lead sources: {k} goes from {t.pct(sr2[k] / tr2 * 100, 0)} to {t.pct(sc2[k] / tc2 * 100, 0)} ({t.pts(v)})."))
                if sc2.get("Autre", 0) / tc2 * 100 >= 30:
                    l.append(F(f"Point d'attention : {t.pct(sc2['Autre'] / tc2 * 100, 0)} des leads n'ont pas de source identifiée (« Autre ») ; l'analyse par source est partielle.",
                               f"Watch point: {t.pct(sc2['Autre'] / tc2 * 100, 0)} of leads have no identified source (“Other”); source analysis is partial."))
        hc, hl, sig = _historique(ctx, x, m)
        l.extend(hl)
        # --- message clé
        seas = ""
        if norme is True:
            seas = F(" ; évolution dans la norme saisonnière", "; within the seasonal norm")
        elif norme is False:
            seas = F(" ; au-delà de la norme saisonnière", "; beyond the seasonal norm")
        if vl is not None and abs(vl) >= SEUIL_ECART:
            sens = F("recul", "decline") if vl < 0 else F("hausse", "increase")
            if dom == "trafic":
                message = F(f"Leads {t.pct(vl, 0, signe=True)} vs {ctx.et(pa)} : {sens} porté principalement par l'audience (sessions {t.pct(vs, 0, signe=True) if vs is not None else 'n.s.'}){seas}.",
                            f"Leads {t.pct(vl, 0, signe=True)} vs {ctx.et(pa)}: {sens} mainly driven by audience (sessions {t.pct(vs, 0, signe=True) if vs is not None else 'n.s.'}){seas}.")
            elif dom == "ratio":
                message = F(f"Leads {t.pct(vl, 0, signe=True)} vs {ctx.et(pa)} : {sens} porté principalement par le ratio leads/sessions, pas par l'audience{seas}.",
                            f"Leads {t.pct(vl, 0, signe=True)} vs {ctx.et(pa)}: {sens} mainly driven by the leads/sessions ratio, not audience{seas}.")
            else:
                message = F(f"Leads {t.pct(vl, 0, signe=True)} vs {ctx.et(pa)} : {sens} partagé entre audience et ratio leads/sessions{seas}.",
                            f"Leads {t.pct(vl, 0, signe=True)} vs {ctx.et(pa)}: {sens} shared between audience and leads/sessions ratio{seas}.")
        elif vl is not None:
            message = F(f"Leads stables ({t.pct(vl, 0, signe=True)} vs {ctx.et(pa)}){seas}.", f"Leads stable ({t.pct(vl, 0, signe=True)} vs {ctx.et(pa)}){seas}.")
        if message and sig.get("sessions") == "bas":
            message += F(" Audience au plus bas de l'historique pour cette période.", " Audience at its historical low for this period.")
        elif message and sig.get("conv") == "haut":
            message += F(" Conversion au plus haut de l'historique.", " Conversion at its historical high.")
        # --- lectures
        if dom == "trafic" and contrib and abs(dtot) >= SEUIL_BASE:
            k0, v0 = contrib[0]
            l.append(F(f"Hypothèse : le mouvement du canal {k0} ({_sg(t, v0)} sessions) pilote l'écart ; à confirmer avec le calendrier et les budgets des campagnes.",
                       f"Hypothesis: the {k0} channel movement ({_sg(t, v0)} sessions) drives the gap; to be confirmed against campaign calendar and budgets."))
        if dom == "ratio":
            f0 = chaine[0] if chaine else None
            cible = {"audience": "", "entrée": F("l'entrée dans le tunnel (première étape)", "funnel entry (first step)"), "estimation": F("l'étape d'estimation", "the estimation step")}
            if f0 and f0[1] != "audience":
                l.append(F(f"Hypothèse : le ratio se joue surtout sur {cible[f0[1]]} ; à vérifier : parcours, performance des pages, changements récents.", f"Hypothesis: the ratio is mostly decided at {cible[f0[1]]}; check journey, page performance, recent changes."))
            else:
                l.append(F("Hypothèse : à audience comparable, la conversion varie ; vérifier la qualité du trafic et les changements récents du parcours.", "Hypothesis: with comparable audience, conversion varies; check traffic quality and recent journey changes."))
        if norme is True and vl is not None and vl < 0:
            l.append(F("La baisse suit le profil saisonnier habituel : elle ne signale pas à elle seule une dégradation de performance.", "The decline follows the usual seasonal pattern: it does not by itself signal a performance deterioration."))
        if norme is False and vl is not None:
            l.append(F("Point d'attention : l'écart dépasse ce que la saisonnalité explique ; chercher une cause propre à la période.", "Watch point: the gap exceeds what seasonality explains; look for a period-specific cause."))
        if len(yoy_ok) >= 2 and yoy_ok[-1][1] < yoy_ok[0][1] - 5:
            l.append(F(f"Point d'attention : le dernier mois ({yoy_ok[-1][0]}) est en retrait par rapport au début de période ; la dynamique entrante est plus faible que la moyenne affichée.", f"Watch point: the latest month ({yoy_ok[-1][0]}) lags the start of the period; incoming momentum is weaker than the average shown."))
        elif len(yoy_ok) >= 2 and yoy_ok[-1][1] > yoy_ok[0][1] + 5:
            l.append(F(f"Le dernier mois ({yoy_ok[-1][0]}) est mieux orienté que le début de période : dynamique plus favorable que la moyenne affichée.", f"The latest month ({yoy_ok[-1][0]}) is better oriented than the start: momentum more favourable than the period average."))
        un = canaux_c.get("Unassigned", 0)
        if Sc and un / Sc * 100 >= 10:
            l.append(F(f"Point d'attention : {t.pct(un / Sc * 100, 0)} des sessions sont « Unassigned » ; l'attribution des canaux est à fiabiliser (balisage UTM).", f"Watch point: {t.pct(un / Sc * 100, 0)} of sessions are “Unassigned”; channel attribution needs fixing (UTM tagging)."))
            r.append(F("Corriger le balisage UTM des campagnes pour réduire les sessions non attribuées.", "Fix campaign UTM tagging to reduce unassigned sessions."))
        # --- recommandations rattachées au facteur dominant
        if dom == "trafic" and contrib and vl is not None:
            k0 = contrib[0][0]
            if vl < 0:
                r.append(F(f"Faire le point avec l'équipe média sur {k0} : budget, ciblage et calendrier de la période, et plan de rattrapage chiffré.", f"Review {k0} with the media team: budget, targeting and calendar for the period, with a quantified catch-up plan."))
            else:
                r.append(F(f"Identifier ce qui a fonctionné sur {k0} (messages, budget, timing) et le reproduire sur les marques en retrait.", f"Identify what worked on {k0} (messages, budget, timing) and replicate it on lagging brands."))
        if dom == "ratio" and vl is not None:
            etape = (chaine[0][1] if chaine and chaine[0][1] != "audience" else None)
            if vl < 0:
                r.append(F(f"Auditer le parcours, en priorité {'l’entrée dans le tunnel' if etape == 'entrée' else 'l’étape d’estimation' if etape == 'estimation' else 'étape par étape'} : abandons, temps de chargement, changements récents.",
                           f"Audit the journey, first {'funnel entry' if etape == 'entrée' else 'the estimation step' if etape == 'estimation' else 'step by step'}: drop-offs, load time, recent changes."))
            else:
                r.append(F("Documenter ce qui améliore la conversion (parcours, message, offre) et le déployer sur les marques dont le ratio est plus faible.", "Document what improves conversion (journey, message, offer) and roll it out to brands with a lower ratio."))
        if dom == "mixte" and vl is not None and vl < 0:
            r.append(F("Traiter d'abord le levier le plus rapide : calendrier média pour l'audience, puis audit du parcours pour la conversion.", "Start with the fastest lever: media calendar for audience, then journey audit for conversion."))
        if vl is None or abs(vl) < SEUIL_ECART:
            r.append(F("Maintenir le suivi : surveiller le ratio leads/sessions et le premier canal, avec une alerte à ±10 %.", "Keep monitoring: track the leads/sessions ratio and the top channel, with an alert at ±10%."))
        r.append(F("Valider ces lectures avec l'équipe marque (campagnes, évolutions du site) avant la prochaine édition.", "Validate these readings with the brand team (campaigns, site changes) before the next edition."))
    return {"message": message or F("Pas de période de référence : lecture descriptive uniquement.", "No reference period: descriptive reading only."),
            "historique": hc if pa is not None else [], "constats": c[:8], "lectures": (l or [F("Aucun signal d'alerte sur la période.", "No warning signal over the period.")])[:6], "recommandations": r[:4]}


def marque(ctx, m):
    return analyse_marque(ctx, m)


def globale(ctx):
    """Analyse du périmètre : contributions des marques, décomposition, saisonnalité, mix projets."""
    d, t = ctx.d, ctx.t
    x = _Marque(ctx, None)
    F = x.fr
    per = ctx.per
    Lc, Sc = x.L(per), x.S(per)
    c, l, r = [], [], []
    pa = ctx.refs[0][1] if ctx.refs else None
    evs = [f"{t.pct(_var(Lc, x.L(p)), 0, signe=True)} vs {ctx.et(p)}" for _, p in ctx.refs if _var(Lc, x.L(p)) is not None]
    c.append(F(f"{t.nb(Lc)} leads sur {ctx.et(per)}", f"{t.nb(Lc)} leads in {ctx.et(per)}") + (f" ({' ; '.join(evs)})" if evs else "") + F(f", {len(d.marques)} marques.", f", {len(d.marques)} brands."))
    message = F("Pas de période de référence : lecture descriptive uniquement.", "No reference period: descriptive reading only.")
    if pa is not None:
        Lr, Sr = x.L(pa), x.S(pa)
        vl = _var(Lc, Lr)
        dec = _decomp(None, Lc, Lr, Sc, Sr)
        dom = None
        if dec and abs(Lc - Lr) >= 30:
            et, er = dec
            tot = abs(et) + abs(er)
            dom = "trafic" if abs(et) / tot >= DOMINE else ("ratio" if abs(et) / tot <= 1 - DOMINE else "mixte")
            c.append(F(f"Écart de {_sg(t, Lc - Lr)} leads vs {ctx.et(pa)} : {_sg(t, et)} dus au trafic (sessions {t.evol(Sc, Sr)[0]}), {_sg(t, er)} dus au ratio leads/sessions.",
                       f"Gap of {_sg(t, Lc - Lr)} leads vs {ctx.et(pa)}: {_sg(t, et)} from traffic (sessions {t.evol(Sc, Sr)[0]}), {_sg(t, er)} from the leads/sessions ratio."))
        # contribution des marques
        dm = sorted(((x2 := d.leads_total(per, m)) - d.leads_total(pa, m), m) for m in d.marques)
        tot_d = Lc - Lr
        if abs(tot_d) >= 30 and len(d.marques) >= 3:
            bons = [(v, m) for v, m in (dm if tot_d < 0 else dm[::-1]) if v * tot_d > 0][:2]
            if bons:
                part = sum(v for v, _ in bons) / tot_d * 100
                c.append(F(f"{' et '.join(ctx.nom(m) for _, m in bons)} expliquent {t.pct(part, 0)} de l'écart ({', '.join(_sg(t, v) for v, _ in bons)} leads).",
                           f"{' and '.join(ctx.nom(m) for _, m in bons)} explain {t.pct(part, 0)} of the gap ({', '.join(_sg(t, v) for v, _ in bons)} leads)."))
        # dispersion
        vm = {m: _var(d.leads_total(per, m), d.leads_total(pa, m)) for m in d.marques}
        mes = {m: v for m, v in vm.items() if v is not None}
        if mes:
            nb_b = sum(1 for v in mes.values() if v <= -SEUIL_ECART)
            nb_h = sum(1 for v in mes.values() if v >= SEUIL_ECART)
            c.append(F(f"Sur {len(mes)} marques mesurables : {nb_h} en hausse, {nb_b} en baisse (seuil ±{SEUIL_ECART} %), {len(mes) - nb_h - nb_b} stables.",
                       f"Out of {len(mes)} measurable brands: {nb_h} up, {nb_b} down (threshold ±{SEUIL_ECART}%), {len(mes) - nb_h - nb_b} stable."))
        # saisonnalité
        sais = _saisonnier(x, per)
        norme = None
        if sais and vl is not None:
            lo, hi = min(sais), max(sais)
            norme = (lo - 5) <= vl <= (hi + 5)
            c.append(F(f"Saisonnalité : sur les deux années précédentes, cette période a évolué de {t.pct(lo, 0, signe=True)} à {t.pct(hi, 0, signe=True)} vs sa précédente ; cette année {t.pct(vl, 0, signe=True)} ({'dans' if norme else 'hors de'} la norme).",
                       f"Seasonality: previous two years moved {t.pct(lo, 0, signe=True)} to {t.pct(hi, 0, signe=True)} vs predecessor; this year {t.pct(vl, 0, signe=True)} ({'within' if norme else 'outside'} the norm)."))
        # mix projets
        pc, pr = x.proj(per), x.proj(pa)
        if Lc and Lr:
            sc_, sr_ = pc["VN"] / Lc * 100, pr["VN"] / Lr * 100
            if abs(sc_ - sr_) >= SEUIL_PTS:
                c.append(F(f"Mix des projets : la part de New cars passe de {t.pct(sr_, 0)} à {t.pct(sc_, 0)} ({t.pts(sc_ - sr_)}).", f"Project mix: New cars share goes from {t.pct(sr_, 0)} to {t.pct(sc_, 0)} ({t.pts(sc_ - sr_)})."))
        # concentration
        par = {m: d.leads_total(per, m) for m in d.marques}
        m0 = max(par, key=par.get)
        if Lc and par[m0] / Lc * 100 >= 50:
            c.append(F(f"{ctx.nom(m0)} concentre {t.pct(par[m0] / Lc * 100, 0)} des leads : la performance du périmètre en dépend fortement.", f"{ctx.nom(m0)} concentrates {t.pct(par[m0] / Lc * 100, 0)} of leads: the perimeter's performance depends heavily on it."))
        # message, lectures, recommandations
        seas = (F(" ; dans la norme saisonnière", "; within the seasonal norm") if norme else F(" ; au-delà de la norme saisonnière", "; beyond the seasonal norm")) if norme is not None else ""
        if vl is not None and abs(vl) >= SEUIL_ECART:
            sens = F("recul", "decline") if vl < 0 else F("hausse", "increase")
            cause = {"trafic": F("porté principalement par l'audience", "mainly driven by audience"), "ratio": F("porté principalement par le ratio leads/sessions", "mainly driven by the leads/sessions ratio"),
                     "mixte": F("partagé entre audience et ratio leads/sessions", "shared between audience and ratio"), None: ""}[dom]
            message = F(f"Leads {t.pct(vl, 0, signe=True)} vs {ctx.et(pa)} : {sens} {cause}{seas}.", f"Leads {t.pct(vl, 0, signe=True)} vs {ctx.et(pa)}: {sens} {cause}{seas}.")
        elif vl is not None:
            message = F(f"Leads stables ({t.pct(vl, 0, signe=True)} vs {ctx.et(pa)}){seas}.", f"Leads stable ({t.pct(vl, 0, signe=True)} vs {ctx.et(pa)}){seas}.")
        if mes and nb_b >= max(2, len(mes) // 2):
            l.append(F(f"Point d'attention : {nb_b} marques sur {len(mes)} reculent ; effet commun probable (saisonnalité, marché) à distinguer des causes propres à chaque marque.", f"Watch point: {nb_b} of {len(mes)} brands are down; likely a common effect (seasonality, market) to separate from brand-specific causes."))
        if norme is True and vl is not None and vl < 0:
            l.append(F("La baisse du périmètre suit le profil saisonnier habituel ; l'attention se porte sur les marques qui s'en écartent.", "The perimeter decline follows the usual seasonal profile; attention goes to brands that deviate."))
        if norme is False:
            l.append(F("Point d'attention : l'écart dépasse la saisonnalité habituelle ; une cause propre à la période est à rechercher.", "Watch point: the gap exceeds usual seasonality; a period-specific cause should be sought."))
        if mes and nb_h:
            l.append(F("Les marques en hausse peuvent servir de référence aux autres (canaux, messages, parcours).", "Growing brands can serve as a reference for the others (channels, messages, journey)."))
        if mes and nb_b:
            pires = sorted(((v, m) for m, v in mes.items() if v <= -SEUIL_ECART))[:3]
            r.append(F(f"Prioriser un plan d'action sur {', '.join(ctx.nom(m) for _, m in pires)} (voir les analyses par marque).", f"Prioritise an action plan on {', '.join(ctx.nom(m) for _, m in pires)} (see brand analyses)."))
        if mes and nb_h:
            meil = sorted(((v, m) for m, v in mes.items() if v >= SEUIL_ECART), reverse=True)[:3]
            r.append(F(f"Documenter et partager les pratiques de {', '.join(ctx.nom(m) for _, m in meil)}.", f"Document and share the practices of {', '.join(ctx.nom(m) for _, m in meil)}."))
    hc, hl, sig = _historique(ctx, x, None)
    l.extend(hl)
    if sig.get("sessions") == "bas":
        message += F(" Audience au plus bas de l'historique pour cette période.", " Audience at its historical low for this period.")
    prec = ctx.brief.get("_edition_precedente")
    if prec and prec.get("etapes"):
        et = prec["etapes"]
        n = lambda st: sum(1 for e in et if (e.get("statut") or "a_faire") == st)
        c.append(F(f"Suivi de l'édition précédente ({prec['periode']}) : {len(et)} actions, {n('fait')} faites, {n('en_cours')} en cours, {n('a_faire')} à faire, {n('bloque')} bloquées.",
                   f"Follow-up of the previous edition ({prec['periode']}): {len(et)} actions, {n('fait')} done, {n('en_cours')} in progress, {n('a_faire')} to do, {n('bloque')} blocked."))
        for e in [e for e in et if (e.get("statut") or "a_faire") in ("bloque", "a_faire", "en_cours")][:2]:
            l.append(F(f"Action encore ouverte : « {e.get('item', '')[:100]} » ({e.get('responsable') or '—'}).", f"Action still open: “{e.get('item', '')[:100]}” ({e.get('responsable') or '—'})."))
    if ctx.brief.get("commentaire"):
        c.append(F("Contexte du DKAM : ", "DKAM context: ") + ctx.brief["commentaire"][:300])
    r.append(F("Valider ces lectures avec les marques (campagnes, évolutions des sites) avant la prochaine édition.", "Validate these readings with the brands (campaigns, site changes) before the next edition."))
    return {"message": message, "historique": hc, "constats": c[:8], "lectures": (l or [F("Aucun signal d'alerte global sur la période.", "No global warning signal over the period.")])[:6], "recommandations": r[:4]}


# =====================================================================================================================
# Analyse par diapositive : chaque diapositive qui affiche des résultats porte son « Analyse » et sa « Recommandation »
# =====================================================================================================================
def _coupe(txt, n=210):
    return txt if len(txt) <= n else txt[:n].rsplit(" ", 1)[0] + "…"


def _fin(res):
    a, r = res
    return [_coupe(x) for x in a if x][:2], [_coupe(x) for x in r if x][:2]


def _tendance_longue(ctx, x, m):
    """Phrase d'historique courte (même période, années passées) pour les leads, ou None."""
    F, t = x.fr, ctx.t
    sl = _serie(ctx, x.L)
    if len(sl) < 3:
        return None
    r, _ = _rang(sl)
    suite = " → ".join(f"{a} : {t.nb(v)}" for a, v in sl[-4:])
    fin = F(" (plus bas de la série)", " (lowest of the series)") if r == "bas" else F(" (plus haut de la série)", " (highest of the series)") if r == "haut" else ""
    return F(f"Même période, années passées : {suite}{fin}.", f"Same period, past years: {suite}{fin}.")


def s_leads_marques(ctx, cle, ref):
    """Diapo « leads par marque » vs une référence."""
    d, t = ctx.d, ctx.t
    x = _Marque(ctx, None)
    F = x.fr
    per = ctx.per
    Lc, Lr = x.L(per), x.L(ref)
    a, r = [], []
    v = _var(Lc, Lr)
    dm = sorted(((d.leads_total(per, m) - d.leads_total(ref, m), m) for m in d.marques))
    tot = Lc - Lr
    if v is not None:
        a.append(F(f"Leads {t.pct(v, 0, signe=True)} vs {ctx.et(ref)} ({_sg(t, tot)}).", f"Leads {t.pct(v, 0, signe=True)} vs {ctx.et(ref)} ({_sg(t, tot)})."))
    else:
        a.append(F("Base de comparaison trop faible pour un pourcentage global.", "Comparison base too small for an overall percentage."))
    if abs(tot) >= 30 and len(d.marques) >= 3:
        mv = [(vv, m) for vv, m in (dm if tot < 0 else dm[::-1]) if vv * tot > 0][:2]
        if mv:
            part = sum(vv for vv, _ in mv) / tot * 100
            a.append(F(f"{' et '.join(ctx.nom(m) for _, m in mv)} portent {t.pct(min(part, 100), 0)} de l'écart ({', '.join(_sg(t, vv) for vv, _ in mv)} leads).",
                       f"{' and '.join(ctx.nom(m) for _, m in mv)} account for {t.pct(min(part, 100), 0)} of the gap ({', '.join(_sg(t, vv) for vv, _ in mv)} leads)."))
    if cle == "prec":
        sais = _saisonnier(x, per)
        if sais and v is not None:
            lo, hi = min(sais), max(sais)
            dans = (lo - 5) <= v <= (hi + 5)
            a.append(F(f"Saisonnalité : les 2 années passées, cette période a évolué de {t.pct(lo, 0, signe=True)} à {t.pct(hi, 0, signe=True)} ; {'dans' if dans else 'hors de'} la norme cette année.",
                       f"Seasonality: past 2 years this period moved {t.pct(lo, 0, signe=True)} to {t.pct(hi, 0, signe=True)}; {'within' if dans else 'outside'} the norm this year."))
    else:
        h = _tendance_longue(ctx, x, None)
        if h:
            a.append(h)
    bas = [(vv, m) for vv, m in dm if vv < 0 and _var(d.leads_total(per, m), d.leads_total(ref, m)) is not None and _var(d.leads_total(per, m), d.leads_total(ref, m)) <= -SEUIL_ECART]
    haut = [(vv, m) for vv, m in dm[::-1] if vv > 0 and _var(d.leads_total(per, m), d.leads_total(ref, m)) is not None and _var(d.leads_total(per, m), d.leads_total(ref, m)) >= SEUIL_ECART]
    if bas:
        r.append(F(f"Prioriser un plan d'action sur {', '.join(ctx.nom(m) for _, m in bas[:3])} (voir leur détail dans la section marques).", f"Prioritise an action plan on {', '.join(ctx.nom(m) for _, m in bas[:3])} (see brand section)."))
    if haut:
        r.append(F(f"Documenter ce qui fonctionne chez {', '.join(ctx.nom(m) for _, m in haut[:3])} et le déployer ailleurs.", f"Document what works at {', '.join(ctx.nom(m) for _, m in haut[:3])} and roll it out elsewhere."))
    if not r:
        r.append(F("Maintenir le suivi : aucune marque ne s'écarte de façon significative.", "Keep monitoring: no brand deviates significantly."))
    return _fin((a, r))


def s_mensuel(ctx, projet=None):
    """Diapo « leads par mois » (tous projets ou New cars)."""
    d, t = ctx.d, ctx.t
    F = ctx.t.l == "fr" and (lambda a, b: a) or (lambda a, b: b)
    dernier = d.dernier_jour_leads()
    from .periodes import Periode, MOIS_COURTS
    a_, r_ = [], []
    cur, ref = [], []
    for mo in range(1, 13):
        if not dernier or Periode("mois", ctx.per.annee, mo).fin.isoformat() > dernier:
            continue
        cur.append((mo, d.leads_mensuels(ctx.per.annee, projet=projet)[mo - 1], d.leads_mensuels(ctx.per.annee - 1, projet=projet)[mo - 1]))
    lib = MOIS_COURTS[ctx.langue]
    ev = [(mo, _var(c, rr), c) for mo, c, rr in cur if _var(c, rr) is not None]
    if not ev:
        return [], []
    baisses = [e for e in ev if e[1] <= -SEUIL_ECART]
    hausses = [e for e in ev if e[1] >= SEUIL_ECART]
    a_.append(F(f"{len(baisses)} mois sur {len(ev)} sont en baisse vs {ctx.per.annee - 1}, {len(hausses)} en hausse (seuil ±{SEUIL_ECART} %).", f"{len(baisses)} of {len(ev)} months are down vs {ctx.per.annee - 1}, {len(hausses)} up (threshold ±{SEUIL_ECART}%)."))
    pire = min(ev, key=lambda e: e[1]); mieux = max(ev, key=lambda e: e[1])
    a_.append(F(f"Meilleur mois : {lib[mieux[0] - 1]} ({t.pct(mieux[1], 0, signe=True)}) ; plus faible : {lib[pire[0] - 1]} ({t.pct(pire[1], 0, signe=True)}).", f"Best month: {lib[mieux[0] - 1]} ({t.pct(mieux[1], 0, signe=True)}); weakest: {lib[pire[0] - 1]} ({t.pct(pire[1], 0, signe=True)})."))
    if len(ev) >= 3:
        k = 3
        dernier3 = sum(e[1] for e in ev[-k:]) / k
        avant = sum(e[1] for e in ev[:-k]) / max(1, len(ev) - k) if len(ev) > k else None
        if avant is not None and abs(dernier3 - avant) >= 5:
            a_.append(F(f"Les {k} derniers mois s'écartent de N-1 de {t.pct(dernier3, 0, signe=True)} en moyenne, contre {t.pct(avant, 0, signe=True)} avant : dynamique {'qui s’améliore' if dernier3 > avant else 'qui se dégrade'}.",
                        f"The last {k} months deviate from last year by {t.pct(dernier3, 0, signe=True)} on average vs {t.pct(avant, 0, signe=True)} before: momentum {'improving' if dernier3 > avant else 'deteriorating'}."))
    if baisses:
        r_.append(F(f"Cibler les mois en retrait ({', '.join(lib[e[0] - 1] for e in baisses[:3])}) : calendrier média et temps forts à planifier.", f"Target lagging months ({', '.join(lib[e[0] - 1] for e in baisses[:3])}): plan media calendar and key moments."))
    if hausses:
        r_.append(F(f"Reproduire les leviers des mois forts ({', '.join(lib[e[0] - 1] for e in hausses[:3])}).", f"Replicate the levers of strong months ({', '.join(lib[e[0] - 1] for e in hausses[:3])})."))
    if not r_:
        r_.append(F("Courbe alignée sur N-1 : maintenir le suivi mensuel.", "Curve in line with last year: keep monthly follow-up."))
    return _fin((a_, r_))


def s_table(ctx):
    """Diapo « trafic & leads » (ratio leads/sessions par marque)."""
    d, t = ctx.d, ctx.t
    F = ctx.t.l == "fr" and (lambda a, b: a) or (lambda a, b: b)
    per = ctx.per
    rows = []
    for m in d.marques:
        S, L = sum(d.canaux(per, m).values()), d.leads_total(per, m)
        if S >= SEUIL_BASE and L >= 30:
            rows.append((L / S * 100, m, S, L))
    a, r = [], []
    if len(rows) >= 2:
        rows.sort(reverse=True)
        a.append(F(f"Ratio leads/sessions : {ctx.nom(rows[0][1])} {t.dec(rows[0][0], 1)} % (le plus élevé), {ctx.nom(rows[-1][1])} {t.dec(rows[-1][0], 1)} % (le plus bas).", f"Leads/sessions ratio: {ctx.nom(rows[0][1])} {t.dec(rows[0][0], 1)}% (highest), {ctx.nom(rows[-1][1])} {t.dec(rows[-1][0], 1)}% (lowest)."))
        r.append(F(f"Comparer le parcours de {ctx.nom(rows[-1][1])} à celui de {ctx.nom(rows[0][1])} pour identifier ce qui explique l'écart de conversion.", f"Compare {ctx.nom(rows[-1][1])}'s journey with {ctx.nom(rows[0][1])}'s to explain the conversion gap."))
    if ctx.refs:
        p = ctx.refs[0][1]
        div = []
        for m in d.marques:
            vs = _var(sum(d.canaux(per, m).values()), sum(d.canaux(p, m).values()))
            vl = _var(d.leads_total(per, m), d.leads_total(p, m))
            if vs is not None and vl is not None and abs(vs - vl) >= 20:
                div.append((m, vs, vl))
        for m, vs, vl in div[:2]:
            a.append(F(f"{ctx.nom(m)} : sessions {t.pct(vs, 0, signe=True)} mais leads {t.pct(vl, 0, signe=True)} vs {ctx.et(p)} : le trafic ne suffit pas à expliquer les leads.", f"{ctx.nom(m)}: sessions {t.pct(vs, 0, signe=True)} but leads {t.pct(vl, 0, signe=True)} vs {ctx.et(p)}: traffic alone doesn't explain leads."))
        if div:
            r.append(F(f"Creuser {ctx.nom(div[0][0])} : écart entre audience et leads (qualité du trafic, parcours, périmètre de mesure).", f"Dig into {ctx.nom(div[0][0])}: gap between audience and leads (traffic quality, journey, measurement scope)."))
    return _fin((a, r))


def s_projets(ctx, marques):
    d, t = ctx.d, ctx.t
    F = ctx.t.l == "fr" and (lambda a, b: a) or (lambda a, b: b)
    per = ctx.per
    ref = ctx.refs[-1][1] if ctx.refs else None
    a, r = [], []
    shifts = []
    for m in marques:
        c = d.leads(per, m); tc = sum(c.values())
        if tc < SEUIL_BASE:
            continue
        sh = c["VN"] / tc * 100
        if ref:
            rr = d.leads(ref, m); tr = sum(rr.values())
            if tr >= SEUIL_BASE:
                shifts.append((sh - rr["VN"] / tr * 100, m, sh))
    if shifts:
        shifts.sort()
        lo, hi = shifts[0], shifts[-1]
        if abs(hi[0]) >= SEUIL_PTS or abs(lo[0]) >= SEUIL_PTS:
            a.append(F(f"Part New cars : {ctx.nom(hi[1])} {t.pts(hi[0])} ({t.pct(hi[2], 0)}), {ctx.nom(lo[1])} {t.pts(lo[0])} ({t.pct(lo[2], 0)}) vs {ctx.et(ref)}.", f"New cars share: {ctx.nom(hi[1])} {t.pts(hi[0])} ({t.pct(hi[2], 0)}), {ctx.nom(lo[1])} {t.pts(lo[0])} ({t.pct(lo[2], 0)}) vs {ctx.et(ref)}."))
        else:
            a.append(F("Le mix des projets d'achat est stable sur les marques du groupe.", "The purchase-project mix is stable across the group's brands."))
        if lo[0] <= -SEUIL_PTS:
            r.append(F(f"Sur {ctx.nom(lo[1])}, la part New cars recule : vérifier la mise en avant de l'offre reprise + achat neuf sur le parcours.", f"On {ctx.nom(lo[1])} the New cars share is falling: check how the trade-in + new car offer is promoted in the journey."))
    tot = {pj: sum(d.leads(per, m)[pj] for m in marques) for pj in PROJETS}
    T = sum(tot.values())
    if T >= SEUIL_BASE:
        top = max(tot, key=tot.get)
        a.append(F(f"Sur le groupe : {t[top]} représente {t.pct(tot[top] / T * 100, 0)} des {t.nb(T)} leads.", f"Across the group: {t[top]} is {t.pct(tot[top] / T * 100, 0)} of {t.nb(T)} leads."))
    if not r:
        r.append(F("Utiliser la part Trade-in only comme cible de qualification : ces leads n'ont pas de projet d'achat à ce stade.", "Use the Trade-in-only share as a qualification target: these leads have no purchase project yet."))
    return _fin((a, r))


def s_trafic(ctx, m):
    d, t = ctx.d, ctx.t
    x = _Marque(ctx, m)
    F = x.fr
    per = ctx.per
    can = d.canaux(per, m)
    S = sum(can.values())
    a, r = [], []
    if not S:
        return [], []
    if ctx.refs:
        p = ctx.refs[0][1]
        ref = d.canaux(p, m)
        Sr = sum(ref.values())
        v = _var(S, Sr)
        delta = {k: can.get(k, 0) - ref.get(k, 0) for k in set(can) | set(ref)}
        dtot = sum(delta.values())
        k0, v0 = max(delta.items(), key=lambda kv: abs(kv[1]))
        if v is not None:
            a.append(F(f"Sessions {t.pct(v, 0, signe=True)} vs {ctx.et(p)} ({_sg(t, dtot)}) ; {k0} pèse {_sg(t, v0)}" + (F(f", soit {t.pct(abs(v0) / abs(dtot) * 100, 0)} de l'écart.", f", i.e. {t.pct(abs(v0) / abs(dtot) * 100, 0)} of the gap.") if dtot and v0 * dtot > 0 and abs(v0) <= abs(dtot) else "."),
                       f"Sessions {t.pct(v, 0, signe=True)} vs {ctx.et(p)} ({_sg(t, dtot)}); {k0} weighs {_sg(t, v0)}."))
            if abs(v0) >= SEUIL_BASE:
                r.append(F(f"{'Faire le point avec l’équipe média sur' if v0 < 0 else 'Capitaliser sur'} {k0} : budget, ciblage, calendrier.", f"{'Review with the media team' if v0 < 0 else 'Build on'} {k0}: budget, targeting, calendar."))
    u = d.utilisateurs(per, m)
    if u and u["utilisateurs"] >= SEUIL_BASE and u["in_journey"]:
        ent, est = u["in_journey"] / u["utilisateurs"] * 100, u["hot_leads"] / u["in_journey"] * 100
        a.append(F(f"Parcours : {t.pct(ent, 0)} des utilisateurs entrent dans le tunnel, {t.pct(est, 0)} d'entre eux déposent une estimation.", f"Journey: {t.pct(ent, 0)} of users enter the funnel, {t.pct(est, 0)} of them submit an estimate."))
        if ent < 40:
            r.append(F("Tester une accroche et un appel à l'action plus visibles sur la première étape (entrée dans le tunnel faible).", "Test a more visible hook and call to action on the first step (low funnel entry)."))
    sess_h = [(aa, v) for aa, v in _serie(ctx, x.S) if d.premier_jour_trafic() and f"{aa}-{per.debut.month:02d}-01" >= d.premier_jour_trafic()]
    if len(sess_h) >= 3:
        rg, _ = _rang(sess_h)
        a.append(F("Sessions, même période : " + " → ".join(f"{aa} : {t.nb(v)}" for aa, v in sess_h[-4:]) + (" (plus bas de la série)." if rg == "bas" else " (plus haut de la série)." if rg == "haut" else "."),
                   "Sessions, same period: " + " → ".join(f"{aa}: {t.nb(v)}" for aa, v in sess_h[-4:]) + (" (lowest of the series)." if rg == "bas" else " (highest of the series)." if rg == "haut" else ".")))
    un = can.get("Unassigned", 0)
    if un / S * 100 >= 10:
        r.append(F(f"Corriger le balisage UTM : {t.pct(un / S * 100, 0)} des sessions sont « Unassigned ».", f"Fix UTM tagging: {t.pct(un / S * 100, 0)} of sessions are “Unassigned”."))
    if not r:
        r.append(F("Maintenir le suivi du premier canal et du taux d'entrée dans le tunnel (alerte à ±10 %).", "Keep tracking the top channel and funnel-entry rate (alert at ±10%)."))
    return _fin((a, r))


def s_leads_marque(ctx, m):
    d, t = ctx.d, ctx.t
    x = _Marque(ctx, m)
    F = x.fr
    per = ctx.per
    Lc = x.L(per)
    a, r = [], []
    pa = ctx.refs[0][1] if ctx.refs else None
    if pa is not None:
        Lr = x.L(pa)
        v = _var(Lc, Lr)
        if v is not None:
            pc, pr = x.proj(per), x.proj(pa)
            dp = {k: pc[k] - pr[k] for k in pc}
            kp = max(dp, key=lambda k: abs(dp[k]))
            a.append(F(f"Leads {t.pct(v, 0, signe=True)} vs {ctx.et(pa)} ; le projet qui bouge le plus : {t[kp]} ({_sg(t, dp[kp])}).", f"Leads {t.pct(v, 0, signe=True)} vs {ctx.et(pa)}; biggest mover: {t[kp]} ({_sg(t, dp[kp])})."))
            sais = _saisonnier(x, per)
            if sais:
                lo, hi = min(sais), max(sais)
                dans = (lo - 5) <= v <= (hi + 5)
                a.append(F(f"Saisonnalité (2 années passées : {t.pct(lo, 0, signe=True)} à {t.pct(hi, 0, signe=True)}) : {'dans' if dans else 'hors de'} la norme cette année.", f"Seasonality (past 2 years: {t.pct(lo, 0, signe=True)} to {t.pct(hi, 0, signe=True)}): {'within' if dans else 'outside'} the norm this year."))
                if not dans:
                    r.append(F("L'écart dépasse la saisonnalité : rechercher une cause propre à la période (campagne, site, parcours) avec l'équipe marque.", "The gap exceeds seasonality: look for a period-specific cause (campaign, site, journey) with the brand team."))
            elif v <= -SEUIL_ECART:
                r.append(F("Identifier avec l'équipe marque les causes du recul (campagnes, site, parcours) et fixer un objectif de rattrapage.", "Identify the causes of the decline with the brand team (campaigns, site, journey) and set a catch-up target."))
    h = _tendance_longue(ctx, x, m)
    if h:
        a.append(h)
    c = d.leads(per, m)
    if Lc >= SEUIL_BASE and c["SANS"] + c["VN"] + c.get("VO", 0) >= 0:
        ti = c.get("SANS", 0)
        if ti / Lc * 100 >= 40:
            r.append(F(f"{t.pct(ti / Lc * 100, 0)} des leads sont « Trade-in only » : travailler la qualification vers un projet d'achat.", f"{t.pct(ti / Lc * 100, 0)} of leads are “Trade-in only”: work on qualifying towards a purchase project."))
    if not r:
        r.append(F("Maintenir le suivi mensuel et partager les bonnes pratiques avec les autres marques.", "Keep monthly follow-up and share good practice with other brands."))
    return _fin((a, r))


def s_sources(ctx, m):
    d, t = ctx.d, ctx.t
    F = ctx.t.l == "fr" and (lambda a, b: a) or (lambda a, b: b)
    per = ctx.per
    if not d.acquisition_disponible(per):
        return [], []
    sc = {k: sum(v.values()) for k, v in d.sources(per, m).items()}
    tc = sum(sc.values())
    a, r = [], []
    if tc < SEUIL_BASE:
        return [], []
    top = max(sc, key=sc.get)
    a.append(F(f"Source principale : {top} ({t.pct(sc[top] / tc * 100, 0)} des {t.nb(tc)} leads).", f"Main source: {top} ({t.pct(sc[top] / tc * 100, 0)} of {t.nb(tc)} leads)."))
    if ctx.refs and d.acquisition_disponible(ctx.refs[0][1]):
        p = ctx.refs[0][1]
        sr = {k: sum(v.values()) for k, v in d.sources(p, m).items()}
        tr = sum(sr.values())
        if tr >= SEUIL_BASE:
            gs = [((sc[k] / tc - sr[k] / tr) * 100, k) for k in sc if k != "Autre"]
            vv, k = max(gs, key=lambda z: abs(z[0]))
            if abs(vv) >= SEUIL_PTS:
                a.append(F(f"{k} passe de {t.pct(sr[k] / tr * 100, 0)} à {t.pct(sc[k] / tc * 100, 0)} des leads ({t.pts(vv)}) vs {ctx.et(p)}.", f"{k} goes from {t.pct(sr[k] / tr * 100, 0)} to {t.pct(sc[k] / tc * 100, 0)} of leads ({t.pts(vv)}) vs {ctx.et(p)}."))
                r.append(F(f"{'Renforcer' if vv > 0 else 'Comprendre le recul de'} {k} : budget, messages et calendrier associés.", f"{'Reinforce' if vv > 0 else 'Understand the decline of'} {k}: associated budget, messages and calendar."))
    if sc.get("Autre", 0) / tc * 100 >= 30:
        a.append(F(f"{t.pct(sc['Autre'] / tc * 100, 0)} des leads sont sans source identifiée (« Autre ») : lecture partielle.", f"{t.pct(sc['Autre'] / tc * 100, 0)} of leads have no identified source (“Other”): partial reading."))
        r.append(F("Fiabiliser le suivi des sources (balisage des campagnes) pour une analyse complète.", "Make source tracking reliable (campaign tagging) for a complete analysis."))
    if not r:
        r.append(F("Mesurer la qualité des leads par source (taux New cars) avant d'arbitrer les budgets.", "Measure lead quality by source (New cars rate) before arbitrating budgets."))
    return _fin((a, r))
