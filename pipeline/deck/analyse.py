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
            "constats": c[:8], "lectures": (l or [F("Aucun signal d'alerte sur la période.", "No warning signal over the period.")])[:4], "recommandations": r[:4]}


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
    if ctx.brief.get("commentaire"):
        c.append(F("Contexte du DKAM : ", "DKAM context: ") + ctx.brief["commentaire"][:300])
    r.append(F("Valider ces lectures avec les marques (campagnes, évolutions des sites) avant la prochaine édition.", "Validate these readings with the brands (campaigns, site changes) before the next edition."))
    return {"message": message, "constats": c[:8], "lectures": (l or [F("Aucun signal d'alerte global sur la période.", "No global warning signal over the period.")])[:4], "recommandations": r[:4]}
