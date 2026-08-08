"""Rapport hebdomadaire de performance de la V2 du site de reprise.

Compare chaque semaine depuis la bascule vers la V2 a la reference V1 :
tout l'historique disponible avant la bascule. Trois familles de mesures :

  - sessions site parent et sessions site de reprise : recalculees a
    partir des series quotidiennes deja assemblees par build.py, aucun
    appel GA4 supplementaire.
  - leads : idem, a partir du back-office deja extrait.
  - funnel (6 etapes, taux de completion) : necessite une requete GA4 par
    semaine (funnel.bloc_funnel accepte une plage de dates arbitraire,
    pas seulement des mois pleins).

Ne bloque jamais l'assemblage d'un site : toute erreur degrade vers une
semaine partielle (sans funnel) ou vers l'absence de rapport, jamais vers
une exception qui remonterait a build.py.
"""

from datetime import date, timedelta

from pipeline import funnel

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


def _label_semaine(debut, fin):
    if debut.month == fin.month:
        return f"{debut.day}–{fin.day} {MOIS_ABREGES[debut.month - 1]}"
    return f"{debut.day} {MOIS_ABREGES[debut.month - 1]} – {fin.day} {MOIS_ABREGES[fin.month - 1]}"


def _funnel_periode(cli, pid, hote, debut, fin):
    """Renvoie (steps, conversion_pct) ou (None, None) sans jamais lever."""
    try:
        jours = (fin - debut).days + 1
        bloc, _methode = funnel.bloc_funnel(cli, pid, hote, debut.isoformat(), fin.isoformat(), jours)
        if bloc:
            return bloc["steps"], bloc["conversion_pct"]
    except Exception:
        pass
    return None, None


def rapport_hebdo(cli, s, d, jour_fiable_iso, hote_reprise):
    """Construit le rapport V2 hebdomadaire d'un site, ou None si pas de
    bascule connue ou pas assez de recul avant bascule pour comparer.
    hote_reprise est passe explicitement plutot que lu dans d['_hotes'],
    qui n'est renseigne qu'a la toute fin de assemble()."""
    v2_date_iso = d.get("v2_date")
    if not v2_date_iso:
        return None

    daily = d.get("daily") or {}
    jours_iso = daily.get("d") or []
    if not jours_iso:
        return None

    v2_date = date.fromisoformat(v2_date_iso)
    jour_fiable = date.fromisoformat(jour_fiable_iso)

    # dates completes ("YYYY-MM-DD") depuis le 08/08/2026 : une seule
    # "annee" appliquee a tout le tableau etait fausse des que la reference
    # V1 remontait sur l'annee civile precedente (bascule en debut d'annee).
    dates_disponibles = [date.fromisoformat(j) for j in jours_iso]
    premiere_donnee, derniere_donnee = min(dates_disponibles), max(dates_disponibles)
    borne_haute = min(jour_fiable, derniere_donnee)

    if not hote_reprise:
        return None

    # ---- reference V1 : tout l'historique disponible avant la bascule ----
    avant_debut, avant_fin = premiere_donnee, v2_date - timedelta(days=1)
    if avant_fin < avant_debut:
        return None  # aucune donnee avant bascule : rien a comparer

    jours_avant = (avant_fin - avant_debut).days + 1
    sp_avant = _agrege_jours(jours_iso, daily.get("u") or [], avant_debut, avant_fin)
    sr_avant = _agrege_jours(jours_iso, daily.get("rep") or [], avant_debut, avant_fin)
    lv_avant = _agrege_leads(d.get("leads"), avant_debut, avant_fin)
    dv_avant = _agrege_leads_par_device(d.get("leads"), avant_debut, avant_fin)
    steps_avant, conv_avant = _funnel_periode(cli, s.propriete, hote_reprise, avant_debut, avant_fin)

    baseline = {
        "debut": avant_debut.isoformat(), "fin": avant_fin.isoformat(), "jours": jours_avant,
        "sessionsParent": sp_avant, "sessionsReprise": sr_avant, "leads": lv_avant,
        "sessionsReprisePerDay": round(sr_avant / jours_avant, 1) if jours_avant else 0,
        "leadsPerDay": round(lv_avant / jours_avant, 2) if jours_avant else 0,
        "funnel": steps_avant, "conversionPct": conv_avant, "leadsParDevice": dv_avant,
    }

    # ---- une entree par semaine ecoulee depuis la bascule ----
    semaines = []
    for deb, fin in _semaines(v2_date, borne_haute):
        jours_semaine = (fin - deb).days + 1
        sp = _agrege_jours(jours_iso, daily.get("u") or [], deb, fin)
        sr = _agrege_jours(jours_iso, daily.get("rep") or [], deb, fin)
        lv = _agrege_leads(d.get("leads"), deb, fin)
        dv = _agrege_leads_par_device(d.get("leads"), deb, fin)
        steps, conv = _funnel_periode(cli, s.propriete, hote_reprise, deb, fin)
        semaines.append({
            "debut": deb.isoformat(), "fin": fin.isoformat(), "jours": jours_semaine,
            "label": _label_semaine(deb, fin),
            "sessionsParent": sp, "sessionsReprise": sr, "leads": lv,
            "sessionsReprisePerDay": round(sr / jours_semaine, 1) if jours_semaine else 0,
            "leadsPerDay": round(lv / jours_semaine, 2) if jours_semaine else 0,
            "funnel": steps, "conversionPct": conv, "leadsParDevice": dv,
        })

    return {"v2Date": v2_date_iso, "baseline": baseline, "weeks": semaines}
