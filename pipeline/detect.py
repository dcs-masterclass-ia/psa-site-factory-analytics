"""Detection automatique de trafic automatise sur le site de reprise.

Remplace la liste de dates ecrite a la main. La signature relevee sur le parc
portugais en juin-juillet 2026 etait la suivante :

  - journees isolees a 15 fois le volume habituel
  - un seul triplet pays / navigateur / appareil concentrant presque tout
  - pays different de celui du site
  - jusqu'a 14 sessions par utilisateur, contre 1,1 en temps normal
  - aucun lead supplementaire, aucune progression dans le parcours

Trois criteres suffisent a la reconnaitre sans risque de confondre avec une
campagne : une campagne fait monter plusieurs journees consecutives, avec des
profils varies, et depuis le pays du site.
"""

import statistics

# GA4 renvoie soit un code ISO (dimension countryId), soit un nom en clair
# (dimension country). On accepte les deux : comparer "Portugal" a "PT" en
# tronquant a deux lettres donnait "Po" != "PT" et faussait toute la detection.
ISO = {
    "france": "FR", "portugal": "PT", "spain": "ES", "espagne": "ES",
    "italy": "IT", "italie": "IT", "germany": "DE", "allemagne": "DE",
    "austria": "AT", "autriche": "AT", "belgium": "BE", "belgique": "BE",
    "poland": "PL", "pologne": "PL", "luxembourg": "LU",
    "united kingdom": "GB", "royaume-uni": "GB",
}
# le back-office et GA4 ne s'accordent pas sur le Royaume-Uni
EQUIVALENTS = {"UK": "GB", "GB": "GB"}


def code_pays(valeur):
    """Normalise un pays en code ISO a deux lettres, quel que soit le format."""
    if not valeur:
        return ""
    v = str(valeur).strip()
    if len(v) == 2 and v.isalpha():
        c = v.upper()
        return EQUIVALENTS.get(c, c)
    c = ISO.get(v.lower())
    if c:
        return EQUIVALENTS.get(c, c)
    return v.upper()[:2]        # dernier recours


def meme_pays(a, b):
    return bool(a) and bool(b) and code_pays(a) == code_pays(b)


FACTEUR_PIC = 3.0          # journee au-dela de N fois la mediane
PART_PROFIL_MIN = 0.50     # un seul profil pese plus de la moitie de la journee
RATIO_SESS_USER = 3.0      # sessions par utilisateur au-dela duquel c'est un automate


def detecte(par_jour, profils_par_jour, pays_site, sessions=None, utilisateurs=None):
    """Identifie les journees de trafic automatise.

    par_jour          : {'AAAAMMJJ': sessions}
    profils_par_jour  : {'AAAAMMJJ': {(pays, navigateur, appareil): sessions}}
    pays_site         : 'FR', 'PT'... pour reperer l'origine etrangere
    sessions/utilisateurs : totaux de la periode, pour le ratio

    Retourne un dict decrivant l'anomalie, ou None si rien de detecte.
    """
    if len(par_jour) < 7:
        return None

    valeurs = sorted(par_jour.values())
    mediane = statistics.median(valeurs)
    if mediane <= 0:
        return None

    marquees, detail = [], []
    for jour in sorted(par_jour):
        volume = par_jour[jour]
        if volume < mediane * FACTEUR_PIC:
            continue

        profils = profils_par_jour.get(jour, {})
        if not profils:
            continue
        (pays, nav, app), part_max = max(profils.items(), key=lambda x: x[1])
        if part_max / volume < PART_PROFIL_MIN:
            continue                      # trafic varie : plutot une campagne
        if meme_pays(pays, pays_site):
            continue                      # origine locale : on ne conclut pas

        # part du volume attribuable a l'automate : l'excedent sur le niveau normal
        excedent = max(0, volume - mediane)
        marquees.append(jour)
        detail.append({
            "jour": f"{jour[4:6]}-{jour[6:]}",
            "sessions": volume,
            "attribue": excedent,
            "facteur": round(volume / mediane, 1),
            "profil": f"{pays} / {nav} / {app}",
            "part_profil_pct": round(part_max / volume * 100, 1),
        })

    if not marquees:
        return None

    total_attribue = sum(d["attribue"] for d in detail)
    ratio = (sessions / utilisateurs) if (sessions and utilisateurs) else None

    return {
        "sessions": total_attribue,
        "jours": [d["jour"] for d in detail],
        "mediane_quotidienne": round(mediane, 1),
        "ratio_sessions_utilisateurs": round(ratio, 1) if ratio else None,
        "detail": detail,
        "methode": ("journees au-dela de 3x la mediane, dominees a plus de 50 % "
                    "par un seul profil pays/navigateur/appareil d'origine etrangere"),
    }


def part_etranger(profils, pays_site):
    """Part du trafic venant d'un autre pays que celui du site, en %."""
    total = sum(profils.values())
    if not total:
        return 0.0
    etranger = sum(s for (pays, _, _), s in profils.items()
                   if not meme_pays(pays, pays_site))
    return round(etranger / total * 100, 1)
