"""Avant / apres V2 : meme funnel quotidien, meme definition que tout le dashboard.

Conversion = estimations / visiteurs de l'accueil du funnel, jours exacts,
a partir de funnelDaily (pipeline/funnel_daily.py). Pas de requete GA4 ici.

  - AVANT = les AVANT_JOURS (28) jours qui precedent la bascule : 4 semaines
    pleines (pas d'effet jour de semaine), l'etat reel juste avant le
    changement -- pas toute l'histoire du site, qui melange campagnes et
    saisons differentes.
  - APRES = tous les jours depuis la bascule.
  - Publie seulement avec au moins SEUIL_JOURS_SIGNIFICATIF jours d'apres et
    REFERENCE_MIN_JOURS jours de reference reellement mesures.
Les volumes se comparent PAR JOUR (les deux fenetres n'ont pas la meme duree).
"""


from datetime import date, timedelta

from pipeline import funnel_daily

MAX_SEMAINES = 26  # ~6 mois de recul, largement au-dessus du besoin actuel

MOIS_ABREGES = ["janv.", "févr.", "mars", "avril", "mai", "juin", "juil.",
                "août", "sept.", "oct.", "nov.", "déc."]


def _lundi(d):
    return d - timedelta(days=d.weekday())


def _semaines(v2_date, borne_haute):
    """Une entree (debut, fin) par semaine calendaire, du lundi de la
    semaine de bascule (tronque a v2_date) jusqu'a borne_haute inclus."""
    if v2_date > borne_haute:
        return []
    cur = _lundi(v2_date)
    out = []
    while cur <= borne_haute and len(out) < MAX_SEMAINES:
        fin_semaine = min(cur + timedelta(days=6), borne_haute)
        deb_effectif = max(cur, v2_date)
        out.append((deb_effectif, fin_semaine))
        cur += timedelta(days=7)
    return out


def _agrege_jours(jours_iso, valeurs, debut, fin):
    """jours_iso : dates completes "YYYY-MM-DD" -- daily["d"] melange deux
    annees des que la fenetre depasse 12 mois (voir build.py), un simple
    "MM-DD" + une annee unique pour tout le tableau serait faux la moitie
    du temps."""
    total = 0
    for j, v in zip(jours_iso, valeurs):
        if v is None:
            continue
        try:
            dj = date.fromisoformat(j)
        except ValueError:
            continue
        if debut <= dj <= fin:
            total += v
    return total


def _agrege_leads(leads_par_mois, debut, fin):
    total = 0
    for mois, bloc in (leads_par_mois or {}).items():
        if mois == "total":
            continue
        try:
            an, m = int(mois[:4]), int(mois[5:7])
        except (ValueError, IndexError):
            continue
        for i, v in enumerate(bloc.get("daily") or []):
            if v is None:
                continue
            try:
                dj = date(an, m, i + 1)
            except ValueError:
                continue
            if debut <= dj <= fin:
                total += v
    return total


def _agrege_leads_par_device(leads_par_mois, debut, fin):
    """Meme principe que _agrege_leads, mais une somme par valeur brute de
    la colonne DEVICE (mobile/desktop/tablette...) — le regroupement/libelle
    final se fait cote dashboard, generique, pas ici."""
    out = {}
    for mois, bloc in (leads_par_mois or {}).items():
        if mois == "total":
            continue
        try:
            an, m = int(mois[:4]), int(mois[5:7])
        except (ValueError, IndexError):
            continue
        for valeur, serie in (bloc.get("dailyDevice") or {}).items():
            for i, v in enumerate(serie):
                if v is None:
                    continue
                try:
                    dj = date(an, m, i + 1)
                except ValueError:
                    continue
                if debut <= dj <= fin:
                    out[valeur] = out.get(valeur, 0) + v
    return out


def label_plage(debut_iso, fin_iso):
    """Format compact 'JJ–JJ/MM' (ou 'JJ/MM–JJ/MM' si les mois different),
    meme convention que les pre_label/post_label saisis a la main sur les
    premiers sites V2 (ex. PEUGEOT PT : "01–21/07" / "22–31/07")."""
    d, f = date.fromisoformat(debut_iso), date.fromisoformat(fin_iso)
    if d.month == f.month and d.year == f.year:
        return f"{d.day:02d}–{f.day:02d}/{f.month:02d}"
    return f"{d.day:02d}/{d.month:02d}–{f.day:02d}/{f.month:02d}"


AVANT_JOURS = 28
REFERENCE_MIN_JOURS = 21   # jours avec donnee dans la fenetre "avant" pour publier
SEUIL_JOURS_SIGNIFICATIF = 7  # en dessous, une cesure avant/apres est trop bruitee

NOTE_AUTO = ("Avant = les 28 jours précédant la bascule, après = depuis la bascule ; "
             "même funnel quotidien et même définition de la conversion que le reste du dashboard.")


def avant_apres_depuis_quotidien(d, v2_date_iso, jour_fiable_iso, nom):
    """(v2steps, v2) ou None si pas assez de recul / de reference.

    v2steps : [{"step", "a" (avant, somme des jours), "b" (apres)}] -- meme forme
    que l'ancien v2steps, lue telle quelle par le dashboard. v2 : metadonnees
    (nombre de jours reels de chaque fenetre, libelles, conversion) ; les
    volumes se lisent par jour via pre_days / post_days.
    """
    quotidien = d.get("funnelDaily") or {}
    if not quotidien or not v2_date_iso:
        return None
    v2_date = date.fromisoformat(v2_date_iso)
    avant_debut, avant_fin = v2_date - timedelta(days=AVANT_JOURS), v2_date - timedelta(days=1)
    apres_fin = min(date.fromisoformat(jour_fiable_iso), max(date.fromisoformat(j) for j in quotidien))

    def somme(debut, fin):
        total, jours = [0] * len(funnel_daily.ETAPES), 0
        for j, v in quotidien.items():
            if debut.isoformat() <= j <= fin.isoformat() and len(v) >= len(total):
                jours += 1
                for i in range(len(total)):
                    total[i] += v[i]
        return total, jours

    avant, n_avant = somme(avant_debut, avant_fin)
    apres, n_apres = somme(v2_date, apres_fin)
    if n_apres < SEUIL_JOURS_SIGNIFICATIF or n_avant < REFERENCE_MIN_JOURS or not avant[0] or not apres[0]:
        return None

    steps = [{"step": nom_etape, "a": avant[i], "b": apres[i]}
             for i, nom_etape in enumerate(funnel_daily.ETAPES)]
    conv_avant, conv_apres = 100 * avant[-1] / avant[0], 100 * apres[-1] / apres[0]
    par_jour_avant, par_jour_apres = avant[0] / n_avant, apres[0] / n_apres
    meta = {
        "site": nom, "is_v2_split": True, "note": NOTE_AUTO,
        "pre_days": n_avant, "post_days": n_apres,
        "pre_label": label_plage(avant_debut.isoformat(), avant_fin.isoformat()),
        "post_label": label_plage(v2_date.isoformat(), apres_fin.isoformat()),
        "pre_step1_total": avant[0], "post_step1_total": apres[0],
        "pre_users_per_day": round(par_jour_avant, 1), "post_users_per_day": round(par_jour_apres, 1),
        "delta_users_per_day_pct": round((par_jour_apres - par_jour_avant) / par_jour_avant * 100, 1),
        "pre_final_users": avant[-1], "post_final_users": apres[-1],
        "pre_conversion_pct": round(conv_avant, 1), "post_conversion_pct": round(conv_apres, 1),
        "delta_conversion_pts": round(conv_apres - conv_avant, 1),
    }
    return steps, meta
