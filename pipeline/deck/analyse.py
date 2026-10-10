"""Analyse calculée par règles (aucun appel à une IA, coût nul) à partir des chiffres de la présentation.

Chaque phrase est produite par une règle à seuil explicite sur des valeurs déjà affichées dans les diapositives ; les causes ne
sont jamais affirmées (« Hypothèse : … », « Point d'attention : … »). Les pourcentages respectent la règle « base < 100 = n.s. ».
"""

SEUIL_BASE = 100          # sous ce volume de référence : pas de pourcentage
SEUIL_ECART = 10          # % : variation jugée significative
SEUIL_CANAL = 100         # sessions : un canal ne « bouge » que s'il pèse au moins ça des deux côtés
SEUIL_UNASSIGNED = 10     # % de sessions « Unassigned » à partir duquel on signale les UTM

TXT = {
    "fr": {
        "leads": "{n} leads {et}{ev}.",
        "sessions": "{n} sessions trade-in {et}{ev}.",
        "projet": "{p} représentent {pct} des leads ({n}).",
        "canal_top": "{c} est le premier canal : {pct} des sessions.",
        "canal_hausse": "Canal en plus forte hausse vs {et} : {c} ({ev}).",
        "canal_baisse": "Canal en plus forte baisse vs {et} : {c} ({ev}).",
        "tunnel": "{pct} des utilisateurs entrent dans le tunnel (In Journey) ; {conv} d'entre eux déposent une estimation (hot leads : {hot}).",
        "source_top": "Source principale des leads : {s} ({pct}).",
        "petit": "Volume trop faible pour conclure ({n} leads sur la période).",
        "lec_audience": "Point d'attention : le trafic et les leads reculent ensemble ; la baisse d'audience explique probablement l'essentiel du recul (à confirmer par canal).",
        "lec_conversion": "Hypothèse : le trafic tient mais les leads reculent, donc la conversion se dégrade ; à vérifier : tunnel, performance des pages, changements récents (à confirmer).",
        "lec_gain": "Hypothèse : les leads progressent malgré moins de trafic, donc la conversion s'améliore (à confirmer).",
        "lec_croissance": "Point d'attention : la hausse des leads suit celle du trafic ; vérifier qu'elle vient bien des canaux à fort potentiel.",
        "lec_canal": "Point d'attention : {c} a perdu {n} sessions vs {et} ; vérifier les campagnes et budgets liés à ce canal.",
        "lec_unassigned": "Point d'attention : {pct} des sessions sont « Unassigned » ; le suivi des paramètres UTM est à vérifier.",
        "lec_tunnel": "Point d'attention : seuls {pct} des utilisateurs entrent dans le tunnel ; l'accroche de la page d'accueil est un levier.",
        "lec_stable": "Pas d'écart significatif sur la période : performance stable.",
        "rec_audience": "Relancer l'audience : revoir l'allocation des canaux en baisse et le calendrier des campagnes.",
        "rec_conversion": "Auditer le tunnel étape par étape (abandons, temps de chargement) et comparer avec les marques qui progressent.",
        "rec_canal": "Faire le point avec l'équipe média sur {c} (budget, ciblage, calendrier).",
        "rec_unassigned": "Corriger le balisage UTM des campagnes pour réduire les sessions non attribuées.",
        "rec_tunnel": "Tester une accroche et un appel à l'action plus visibles sur la première étape.",
        "rec_capitaliser": "Capitaliser : identifier ce qui fonctionne (canaux, messages) et le dupliquer sur les marques en retrait.",
        "rec_suivi": "Maintenir le suivi mensuel et réévaluer à la prochaine édition.",
        "rec_petit": "Cumuler sur une période plus longue avant toute décision sur cette marque.",
        "g_total": "{n} leads {et}{ev} sur {nb} marques.",
        "g_hausse": "En hausse vs {et} : {liste}.",
        "g_baisse": "En baisse vs {et} : {liste}.",
        "g_conc": "{m} concentre {pct} des leads du périmètre.",
        "g_lec_baisses": "Point d'attention : {nb} marques sur {tot} sont en baisse vs {et} ; vérifier s'il s'agit d'un effet commun (saisonnalité, marché) ou propre à chaque marque.",
        "g_lec_hausses": "Les marques en hausse peuvent servir de référence aux autres (canaux, messages, parcours).",
        "g_lec_conc": "Point d'attention : la performance du périmètre dépend fortement de {m}.",
        "g_rec_baisse": "Prioriser un plan d'action sur {liste}.",
        "g_rec_hausse": "Documenter les bonnes pratiques de {liste} et les partager.",
        "g_rec_suivi": "Valider avec les marques les points ouverts avant la prochaine édition.",
        "pt": "pt",
    },
    "en": {
        "leads": "{n} leads {et}{ev}.",
        "sessions": "{n} trade-in sessions {et}{ev}.",
        "projet": "{p} account for {pct} of leads ({n}).",
        "canal_top": "{c} is the top channel: {pct} of sessions.",
        "canal_hausse": "Fastest-growing channel vs {et}: {c} ({ev}).",
        "canal_baisse": "Steepest-declining channel vs {et}: {c} ({ev}).",
        "tunnel": "{pct} of users enter the journey (In Journey); {conv} of them submit an estimate (hot leads: {hot}).",
        "source_top": "Main lead source: {s} ({pct}).",
        "petit": "Volume too low to conclude ({n} leads over the period).",
        "lec_audience": "Watch point: traffic and leads are falling together; the audience decline probably explains most of the drop (to be confirmed by channel).",
        "lec_conversion": "Hypothesis: traffic holds but leads decline, so conversion is deteriorating; check the journey, page performance and recent changes (to be confirmed).",
        "lec_gain": "Hypothesis: leads grow despite less traffic, so conversion is improving (to be confirmed).",
        "lec_croissance": "Watch point: the lead increase follows traffic growth; check it comes from high-potential channels.",
        "lec_canal": "Watch point: {c} lost {n} sessions vs {et}; check the related campaigns and budgets.",
        "lec_unassigned": "Watch point: {pct} of sessions are « Unassigned »; UTM tagging needs checking.",
        "lec_tunnel": "Watch point: only {pct} of users enter the journey; the home-step hook is a lever.",
        "lec_stable": "No significant change over the period: stable performance.",
        "rec_audience": "Rebuild audience: review the allocation of declining channels and the campaign calendar.",
        "rec_conversion": "Audit the journey step by step (drop-offs, load time) and compare with brands that are growing.",
        "rec_canal": "Review {c} with the media team (budget, targeting, calendar).",
        "rec_unassigned": "Fix campaign UTM tagging to reduce unassigned sessions.",
        "rec_tunnel": "Test a more visible hook and call to action on the first step.",
        "rec_capitaliser": "Build on what works (channels, messages) and replicate it on lagging brands.",
        "rec_suivi": "Keep the monthly follow-up and reassess at the next edition.",
        "rec_petit": "Accumulate a longer period before any decision on this brand.",
        "g_total": "{n} leads {et}{ev} across {nb} brands.",
        "g_hausse": "Up vs {et}: {liste}.",
        "g_baisse": "Down vs {et}: {liste}.",
        "g_conc": "{m} concentrates {pct} of the perimeter's leads.",
        "g_lec_baisses": "Watch point: {nb} of {tot} brands are down vs {et}; check whether it is a common effect (seasonality, market) or brand-specific.",
        "g_lec_hausses": "Growing brands can serve as a reference for the others (channels, messages, journey).",
        "g_lec_conc": "Watch point: the perimeter's performance depends heavily on {m}.",
        "g_rec_baisse": "Prioritise an action plan on {liste}.",
        "g_rec_hausse": "Document and share best practices from {liste}.",
        "g_rec_suivi": "Validate open points with the brands before the next edition.",
        "pt": "pt",
    },
}


def _var(cur, ref):
    """Variation en % ou None si la base est trop faible."""
    return None if (ref is None or cur is None or ref < SEUIL_BASE) else (cur - ref) / ref * 100


def _evs(ctx, cur, refs):
    """« (−10 % vs T2-2026 ; −12 % vs T3-2025) » ; ignore les références à base faible ; chaîne vide s'il n'y en a aucune."""
    parts = []
    for ref, et in refs:
        v = _var(cur, ref)
        if v is not None:
            parts.append(f"{ctx.t.pct(v, 0, signe=True)} vs {et}")
    return f" ({' ; '.join(parts)})" if parts else ""


def marque(ctx, m):
    """-> {"constats","lectures","recommandations"} pour une marque (listes de phrases) ou None si rien à dire."""
    d, t = ctx.d, ctx.t
    X = TXT[ctx.langue]
    per = ctx.per
    lt, lt0 = d.leads_total(per, m), d.leads(per, m)
    can = d.canaux(per, m)
    sess = sum(can.values())
    c, l, r = [], [], []
    if lt < SEUIL_BASE and sess < SEUIL_BASE:
        return None
    # --- constats
    ref_main = ctx.refs[0] if ctx.refs else None
    evs = _evs(ctx, lt, [(d.leads_total(p, m), ctx.et(p)) for _, p in ctx.refs])
    c.append(X["leads"].format(n=t.nb(lt), et=ctx.et(per), ev=evs))
    sevs = _evs(ctx, sess, [(sum(d.canaux(p, m).values()), ctx.et(p)) for _, p in ctx.refs])
    if sess:
        c.append(X["sessions"].format(n=t.nb(sess), et=ctx.et(per), ev=sevs))
    if lt >= SEUIL_BASE:
        pj = max(lt0, key=lt0.get)
        c.append(X["projet"].format(p=t[pj], pct=t.pct(lt0[pj] / lt * 100, 0), n=t.nb(lt0[pj])))
    else:
        c.append(X["petit"].format(n=t.nb(lt)))
    top = sorted(can, key=lambda k: -can[k])
    if sess >= SEUIL_BASE and top:
        c.append(X["canal_top"].format(c=top[0], pct=t.pct(can[top[0]] / sess * 100, 0)))
    u = d.utilisateurs(per, m)
    if u and u["utilisateurs"] >= SEUIL_BASE and u["in_journey"]:
        c.append(X["tunnel"].format(pct=t.pct(u["in_journey"] / u["utilisateurs"] * 100, 0), conv=t.pct(u["hot_leads"] / u["in_journey"] * 100, 0), hot=t.nb(u["hot_leads"])))
    if d.acquisition_disponible(per) and lt >= SEUIL_BASE:
        src = {sg: sum(v.values()) for sg, v in d.sources(per, m).items()}
        tot = sum(src.values())
        if tot >= SEUIL_BASE:
            s0 = max(src, key=src.get)
            c.append(X["source_top"].format(s=s0, pct=t.pct(src[s0] / tot * 100, 0)))
    # --- lectures et recommandations, sur la première référence disponible
    if lt < SEUIL_BASE:
        r.append(X["rec_petit"])
    elif ref_main:
        cle, p = ref_main
        vl, vs = _var(lt, d.leads_total(p, m)), _var(sess, sum(d.canaux(p, m).values()))
        if vl is not None and vs is not None:
            if vl <= -SEUIL_ECART and vs <= -SEUIL_ECART:
                l.append(X["lec_audience"]); r.append(X["rec_audience"])
            elif vl <= -SEUIL_ECART and vs > -SEUIL_ECART:
                l.append(X["lec_conversion"]); r.append(X["rec_conversion"])
            elif vl >= SEUIL_ECART and vs <= -SEUIL_ECART:
                l.append(X["lec_gain"]); r.append(X["rec_capitaliser"])
            elif vl >= SEUIL_ECART:
                l.append(X["lec_croissance"]); r.append(X["rec_capitaliser"])
        refc = d.canaux(p, m)
        var = [(can.get(k, 0) - refc.get(k, 0), k) for k in set(can) | set(refc) if max(can.get(k, 0), refc.get(k, 0)) >= SEUIL_CANAL and refc.get(k, 0) >= SEUIL_BASE]
        if var:
            hausse, baisse = max(var), min(var)
            if hausse[0] > 0 and _var(can.get(hausse[1], 0), refc.get(hausse[1], 0)) is not None:
                c.append(X["canal_hausse"].format(et=ctx.et(p), c=hausse[1], ev=t.pct(_var(can.get(hausse[1], 0), refc[hausse[1]]), 0, signe=True)))
            if baisse[0] < 0 and _var(can.get(baisse[1], 0), refc[baisse[1]]) is not None:
                c.append(X["canal_baisse"].format(et=ctx.et(p), c=baisse[1], ev=t.pct(_var(can.get(baisse[1], 0), refc[baisse[1]]), 0, signe=True)))
                if abs(baisse[0]) >= SEUIL_CANAL:
                    l.append(X["lec_canal"].format(c=baisse[1], n=t.nb(-baisse[0]), et=ctx.et(p))); r.append(X["rec_canal"].format(c=baisse[1]))
    un = can.get("Unassigned", 0)
    if sess >= SEUIL_BASE and un / sess * 100 >= SEUIL_UNASSIGNED:
        l.append(X["lec_unassigned"].format(pct=t.pct(un / sess * 100, 0))); r.append(X["rec_unassigned"])
    if u and u["utilisateurs"] >= SEUIL_BASE and u["in_journey"] / u["utilisateurs"] * 100 < 40:
        l.append(X["lec_tunnel"].format(pct=t.pct(u["in_journey"] / u["utilisateurs"] * 100, 0))); r.append(X["rec_tunnel"])
    if not l:
        l.append(X["lec_stable"])
    r.append(X["rec_suivi"])
    return {"constats": c[:5], "lectures": l[:4], "recommandations": r[:4]}


def globale(ctx):
    d, t = ctx.d, ctx.t
    X = TXT[ctx.langue]
    per = ctx.per
    tot = d.leads_total(per)
    c, l, r = [], [], []
    evs = _evs(ctx, tot, [(d.leads_total(p), ctx.et(p)) for _, p in ctx.refs])
    c.append(X["g_total"].format(n=t.nb(tot), et=ctx.et(per), ev=evs, nb=len(d.marques)))
    baisses_p = []
    for cle, p in ctx.refs:
        h, b = [], []
        for m in d.marques:
            v = _var(d.leads_total(per, m), d.leads_total(p, m))
            if v is None or abs(v) < SEUIL_ECART:
                continue
            (h if v > 0 else b).append((v, f"{ctx.nom(m)} {t.pct(v, 0, signe=True)}"))
        h.sort(reverse=True); b.sort()
        if h:
            c.append(X["g_hausse"].format(et=ctx.et(p), liste=", ".join(x[1] for x in h[:4])))
        if b:
            c.append(X["g_baisse"].format(et=ctx.et(p), liste=", ".join(x[1] for x in b[:4])))
        if cle == (ctx.refs[0][0] if ctx.refs else None):
            baisses_p, hausses_p, p0 = b, h, p
    if tot >= SEUIL_BASE:
        par = {m: d.leads_total(per, m) for m in d.marques}
        m0 = max(par, key=par.get)
        if par[m0] / tot * 100 >= 50:
            c.append(X["g_conc"].format(m=ctx.nom(m0), pct=t.pct(par[m0] / tot * 100, 0)))
            l.append(X["g_lec_conc"].format(m=ctx.nom(m0)))
    if ctx.refs and baisses_p:
        if len(baisses_p) >= max(2, len(d.marques) // 2):
            l.append(X["g_lec_baisses"].format(nb=len(baisses_p), tot=len(d.marques), et=ctx.et(p0)))
        r.append(X["g_rec_baisse"].format(liste=", ".join(x[1].rsplit(" ", 2)[0] if False else x[1].split(" −")[0].split(" +")[0] for x in baisses_p[:3])))
    if ctx.refs and hausses_p:
        l.append(X["g_lec_hausses"])
        r.append(X["g_rec_hausse"].format(liste=", ".join(x[1].split(" +")[0].split(" −")[0] for x in hausses_p[:3])))
    if not l:
        l.append(X["lec_stable"])
    r.append(X["g_rec_suivi"])
    if ctx.brief.get("commentaire"):
        c.append(ctx.brief["commentaire"][:300])
    return {"constats": c[:6], "lectures": l[:4], "recommandations": r[:4]}
