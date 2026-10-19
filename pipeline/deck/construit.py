"""Construction de la présentation : diapositives, graphiques natifs, textes calculés.

Cœur du générateur : couverture, sommaire, vue d'ensemble, projets d'achat, détail par marque (trafic, leads, sources),
points ouverts, prochaines étapes, contacts. Module « cta » : non généré pour l'instant (signalé dans les avertissements).
"""

from datetime import date
from pathlib import Path

from pptx import Presentation
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from . import analyse as an
from . import graphiques as g
from .donnees import GROUPES_MARQUES, NOMS_MARQUES, ORDRE_SOURCES, PROJETS, Donnees
from .periodes import MOIS_COURTS, Periode, depuis_brief
from .textes import MOINS, T

GABARIT = Path(__file__).with_name("gabarit_autobiz.pptx")
X0, X1 = 0.45, 12.9        # marges horizontales du contenu
Y0, Y1 = 1.45, 6.85        # zone de contenu


class Ctx:
    def __init__(self, brief, donnees, gabarit=GABARIT):
        self.brief, self.d = brief, donnees
        self.t = T(brief.get("langue", "fr"))
        self.langue = self.t.l
        self.prs = Presentation(str(gabarit))
        self.lay = {l.name: l for l in self.prs.slide_layouts}
        self.per = depuis_brief(brief["periode"])
        comp = brief.get("comparaisons") or {}
        self.refs = []                     # [(clé, Periode, libellé court)]
        if comp.get("precedente") and self.per.type != "annee":
            self.refs.append(("prec", self.per.precedente()))
        if comp.get("n1"):
            self.refs.append(("n1", self.per.n1()))
        self.n = 0                         # numéro de diapositive
        self.comm_utilises = set()         # clés de commentaires déjà affichées
        self.aujourdhui = date.today()     # date de référence (maturité des commandes C1ST : 90 jours)
        self.avertissements = []
        from .faits import Faits
        self.faits = Faits()                # chiffres affichés, pour le contrôle qualité (qa.py)
        self.modules = set(brief.get("modules") or [])
        pays = [p.upper() for p in brief["perimetre"]["pays"]]
        self.perimetre = "BELUX" if sorted(pays) == ["BE", "LU"] else " + ".join(pays)
        self.client = brief.get("client") or ""

    def et(self, p):
        return p.etiquette(self.langue)

    @property
    def periodes(self):
        """Périodes à afficher dans l'ordre chronologique : références puis période courante."""
        return sorted([p for _, p in self.refs], key=lambda p: (p.annee, p.mois_debut)) + [self.per]

    def nom(self, marque):
        return NOMS_MARQUES.get(marque, marque.title())


# ------------------------------------------------------------------ squelette de diapositive
def _style_titre(forme, taille):
    """Titre / sous-titre au format des decks de référence : Calibri gras, bleu 043882 (28 pt le titre, 18 pt le sous-titre)."""
    for para in forme.text_frame.paragraphs:
        for r in para.runs:
            r.font.name = "Calibri"; r.font.bold = True; r.font.size = Pt(taille); r.font.color.rgb = g.rgb(g.TITRE_REF)


def nouvelle(ctx, titre, sous_titre=None, source=None, layout="Title and Subtitle", notes=None, cle=None, message=None):
    """Nouvelle diapositive. `message` = phrase-clé affichée en sous-titre, sur toute la largeur (format des decks de référence) ;
    sinon `sous_titre` (périmètre / périodes) comme avant."""
    s = ctx.prs.slides.add_slide(ctx.lay[layout])
    ctx.n += 1
    s.shapes.title.text = titre
    _style_titre(s.shapes.title, 28)
    if message:
        sous_titre = message
    for ph in s.placeholders:
        if ph.placeholder_format.idx == 12:
            ph.text = sous_titre or ""
            _style_titre(ph, 18 if not message or len(message) <= 82 else 16 if len(message) <= 100 else 14)      # une phrase-clé longue réduit la taille plutôt que de passer sous le filet
            if message:
                ph.left, ph.top, ph.width, ph.height = Inches(0.28), Inches(0.67), Inches(9.9), Inches(0.75)
    if sous_titre is None and layout == "Title and Subtitle":
        for ph in list(s.placeholders):
            if ph.placeholder_format.idx == 12:
                ph._element.getparent().remove(ph._element)
    g.texte(s, 0.3, 7.1, 6.5, 0.3, source or "", taille=9, couleur=g.GRIS)
    g.texte(s, 4.4, 7.1, 4.5, 0.3, ctx.t["confidentiel"], taille=9, couleur=g.GRIS, align=PP_ALIGN.CENTER)
    g.texte(s, 12.2, 7.1, 0.8, 0.3, str(ctx.n), taille=9, couleur=g.GRIS, align=PP_ALIGN.RIGHT)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    if cle:
        commentaire_diapo(ctx, s, cle)
    return s


def nouvelle_ref(ctx, titre, message, source=None, puces=None, notes=None, cle=None):
    """Diapositive au design des decks de référence (reporting pays) : grand titre, phrase-clé en sous-titre, drapeau du marché à côté du logo,
    graphiques à gauche (zone X0_REF..X1_REF) et encadré bleu pointillé de commentaires à droite (`puces`, 5 au plus)."""
    s = nouvelle(ctx, titre, source=source, notes=notes, cle=cle, message=message)
    pays = [p.upper() for p in ctx.brief["perimetre"]["pays"]]
    if len(pays) == 1:
        g.drapeau(s, pays[0])
    elif sorted(pays) == ["BE", "LU"]:
        g.drapeau(s, "BE", x=9.55, w=0.8, h=0.54, y=0.3); g.drapeau(s, "LU", x=10.45, w=0.8, h=0.54, y=0.3)
    if puces:
        g.boite_pointillee(s, 10.84, 1.44, 2.29, 5.55, [l[:150] for l in puces[:5]], taille=12)
    return s


X0_REF, X1_REF = 0.44, 10.07     # zone des graphiques (à gauche de l'encadré de commentaires)


def commentaire_diapo(ctx, s, cle):
    """Commentaire du DKAM saisi dans le questionnaire (brief["commentaires"][clé]), affiché sous le titre à droite ; une clé n'est affichée qu'une fois
    (la clé « marque:X » apparaît donc sur la première diapositive de la marque)."""
    txt = ((ctx.brief.get("commentaires") or {}).get(cle) or "").strip()
    if not txt or cle in ctx.comm_utilises:
        return
    ctx.comm_utilises.add(cle)
    g.encadre(s, 4.5, 0.62, 8.4, 0.6, None, [txt[:240]], taille=11.5, couleur=g.ORANGE)


def source_bo(ctx):
    return ctx.t["source_bo"]


def source_ga4(ctx):
    return ctx.t["source_ga4"]


def source_les_deux(ctx):
    return ctx.t["source_bo_ga4"]


def note_definitions(ctx, extra=""):
    return (f"{ctx.t['perimetre']} : {ctx.perimetre}. Leads : back-office autobiz, leads valides (production, hors doublons, tests et tests internes). "
            f"Trafic : sites de reprise (GA4). Définitions : docs/presentations-definitions.md. {extra}").strip()


# ------------------------------------------------------------------ commentaires calculés
def commentaire_evolutions(ctx, etiquettes, courant, ref, nom_ref, max_lignes=4):
    """Hausses / baisses par élément (marque…), pourcentage seulement si la base de référence >= 100."""
    t = ctx.t
    hausses, baisses, petites = [], [], []
    for e, c, r in zip(etiquettes, courant, ref):
        txt, signe, v = t.evol(c, r)
        if v is None:
            if (c or 0) + (r or 0) > 0 and c != r:
                petites.append(f"{e} : {t.nb(c)} (vs {t.nb(r)})")
            continue
        if signe > 0:
            hausses.append((v, f"{e} {txt}"))
        elif signe < 0:
            baisses.append((v, f"{e} {txt}"))
    hausses.sort(reverse=True); baisses.sort()
    lignes = []
    if hausses:
        lignes.append((("En hausse " if ctx.langue == "fr" else "Up ") + nom_ref + " :", True))
        lignes.append(", ".join(x[1] for x in hausses[:max_lignes]))
    if baisses:
        lignes.append((("En baisse " if ctx.langue == "fr" else "Down ") + nom_ref + " :", True))
        lignes.append(", ".join(x[1] for x in baisses[:max_lignes]))
    if petites:
        lignes.append((("Petits volumes (pas de %) :" if ctx.langue == "fr" else "Small volumes (no %):"), True))
        lignes.append(", ".join(petites[:max_lignes]))
    if not lignes:
        lignes.append("Pas d'évolution significative." if ctx.langue == "fr" else "No significant change.")
    return lignes


def libelle_ref(ctx, cle):
    return ctx.t["vs_prec"] if cle == "prec" else ctx.t["vs_n1"]


# ------------------------------------------------------------------ pièces
def couverture(ctx):
    s = ctx.prs.slides.add_slide(ctx.lay["Title Slide"])
    ctx.n += 1
    titre = ctx.brief.get("titre") or f"{ctx.client} — {ctx.perimetre} {ctx.et(ctx.per)}"
    g.texte(s, 1.0, 2.5, 8.5, 1.0, ctx.client.upper(), taille=34, gras=True, couleur="FFFFFF")
    g.texte(s, 1.0, 3.55, 11.0, 1.2, titre, taille=22, gras=True, couleur="FFFFFF")
    g.texte(s, 1.0, 5.2, 11.0, 0.5, f"{ctx.perimetre} · {ctx.et(ctx.per)} · {date.today().strftime('%d/%m/%Y')}", taille=16, couleur="FFFFFF")
    return s


def sommaire(ctx, sections, actif=None):
    s = nouvelle(ctx, ctx.t["agenda"])
    y = 1.9
    for i, (cle, libelle) in enumerate(sections):
        on = cle == actif
        box = s.shapes.add_shape(1, Inches(1.2), Inches(y), Inches(10.4), Inches(0.5))
        box.fill.solid(); box.fill.fore_color.rgb = g.rgb(g.BLEU if on else "F1F4F9")
        box.line.fill.background(); box.shadow.inherit = False
        g.texte(s, 1.35, y + 0.05, 10.0, 0.4, libelle.upper(), taille=15, gras=on, couleur="FFFFFF" if on else g.BLEU, ancre=MSO_ANCHOR.MIDDLE)
        y += 0.68
    return s


def synthese(ctx):
    t, d, per = ctx.t, ctx.d, ctx.per
    s = nouvelle(ctx, f"{t['synthese']} — {ctx.et(per)}", f"{ctx.perimetre}", source_les_deux(ctx), notes=note_definitions(ctx), cle="synthese")
    leads = d.leads(per); tot = sum(leads.values()); nc = leads["VN"]
    sess_cur = sum(sum(d.canaux(per, m).values()) for m in d.marques)
    # tuiles
    def detail_evol(v_cur, f_ref):
        parties = []
        for cle, p in ctx.refs:
            txt, signe, _ = t.evol(v_cur, f_ref(p))
            parties.append(f"{txt} {libelle_ref(ctx, cle)}")
        return "  ·  ".join(parties) if parties else None
    x, w, gap = X0, 3.0, 0.15
    g.tuile(s, x, 1.55, w, 1.35, t["leads"], t.nb(tot), detail_evol(tot, d.leads_total))
    taux_cur = t.taux(nc, tot)
    det = []
    for cle, p in ctx.refs:
        r = d.leads(p); tr = t.taux(r["VN"], sum(r.values()))
        det.append(f"{t.pts(taux_cur - tr) if (taux_cur is not None and tr is not None and sum(r.values()) >= 100) else t['n_s']} {libelle_ref(ctx, cle)}")
    g.tuile(s, x + (w + gap), 1.55, w, 1.35, t["taux_nc"], t.pct(taux_cur, 0) if taux_cur is not None else t["non_dispo"], "  ·  ".join(det) or None)
    g.tuile(s, x + 2 * (w + gap), 1.55, w, 1.35, t["sessions"], t.nb(sess_cur),
            detail_evol(sess_cur, lambda p: sum(sum(d.canaux(p, m).values()) for m in d.marques)))
    ga = {m: d.utilisateurs(per, m) for m in d.marques}
    mesurees = [m for m, v in ga.items() if v is not None]
    if mesurees:
        hot = sum(ga[m]["hot_leads"] for m in mesurees)
        det_h = []
        for cle, p in ctx.refs:
            rr = [d.utilisateurs(p, m) for m in mesurees]
            if all(v is not None for v in rr):       # comparaison sur les mêmes marques uniquement
                det_h.append(f"{t.evol(hot, sum(v['hot_leads'] for v in rr))[0]} {libelle_ref(ctx, cle)}")
        if len(mesurees) < len(d.marques):
            det_h.append((f"{len(mesurees)} marques sur {len(d.marques)} mesurées" if ctx.langue == "fr" else f"{len(mesurees)} of {len(d.marques)} brands measured"))
        g.tuile(s, x + 3 * (w + gap), 1.55, w, 1.35, t["hot_leads"], t.nb(hot), "  ·  ".join(det_h) or None)
    else:
        g.tuile(s, x + 3 * (w + gap), 1.55, w, 1.35, t["hot_leads"], t["non_dispo"], t["ga4_indispo"])
    # commentaires : marques
    lignes = []
    for cle, p in ctx.refs:
        etiq = [ctx.nom(m) for m in d.marques]
        lignes += commentaire_evolutions(ctx, etiq, [d.leads_total(per, m) for m in d.marques], [d.leads_total(p, m) for m in d.marques],
                                         f"{libelle_ref(ctx, cle)} ({ctx.et(p)})", max_lignes=5)
    g.encadre(s, X0, 3.2, 8.3, 3.5, ("Leads par marque" if ctx.langue == "fr" else "Leads by brand"), lignes, taille=11.5)
    g.texte(s, 9.0, 3.2, 3.9, 3.5, [(t["base_faible"], {"taille": 10, "couleur": g.GRIS, "italique": True})])
    return s


def groupes_de_marques(ctx):
    """{nom du groupe: [marques]} limité aux marques du périmètre : XP, XF, Spoticar, autres."""
    ms = ctx.d.marques
    g_ = {"XP": [m for m in GROUPES_MARQUES["XP"] if m in ms], "XF": [m for m in GROUPES_MARQUES["XF"] if m in ms], "Spoticar": [m for m in ms if m == "SPOTICAR"]}
    g_["Autres" if ctx.langue == "fr" else "Other"] = [m for m in ms if m not in sum(g_.values(), [])]
    return {k: v for k, v in g_.items() if v}


def vue_groupes(ctx):
    """Leads par groupe de marques (XP / XF / Spoticar / autres), avec la vue « hors Spoticar »."""
    t, d, per = ctx.t, ctx.d, ctx.per
    grp = groupes_de_marques(ctx)
    if len(grp) < 2:
        return None
    periodes = ctx.periodes
    L = lambda p, ms: sum(d.leads_total(p, m) for m in ms)
    s = nouvelle(ctx, f"{t['groupes']} — {ctx.et(per)}", ctx.perimetre, source_bo(ctx), notes=note_definitions(ctx), cle="groupes")
    couleurs = ["1F3F7A", "F58A1F", "7FB7B0", "9AA3B2"]
    series = [(k, [L(p, ms) for p in periodes], couleurs[i % 4]) for i, (k, ms) in enumerate(grp.items())]
    g.colonnes(s, X0, Y0, 5.6, 4.2, [ctx.et(p) for p in periodes], series, empile=True, taille=10, fmt=t.nb)
    ent = [t["groupe"], f"{t['leads']} {ctx.et(per)}", t["part_total"], f"{t['part_total']} ({t['hors_spoticar'].lower()})"] + [libelle_ref(ctx, c) for c, _ in ctx.refs]
    tot = L(per, d.marques)
    tot_hs = sum(L(per, ms) for k, ms in grp.items() if k != "Spoticar")
    lignes = [ent]
    for k, ms in grp.items():
        v = L(per, ms)
        row = [k, t.nb(v), t.pct(v / tot * 100, 0) if tot else "–", "–" if k == "Spoticar" or not tot_hs else t.pct(v / tot_hs * 100, 0)]
        row += [t.evol(v, L(p, ms))[0] for _, p in ctx.refs]
        lignes.append(row)
    lignes.append([t["total"], t.nb(tot), "100 %", "–"] + [t.evol(tot, L(p, d.marques))[0] for _, p in ctx.refs])
    if "Spoticar" in grp:
        lignes.append([t["hors_spoticar"], t.nb(tot_hs), t.pct(tot_hs / tot * 100, 0) if tot else "–", "100 %"] + [t.evol(tot_hs, sum(L(p, ms) for k, ms in grp.items() if k != "Spoticar"))[0] for _, p in ctx.refs])
    nc = len(ent)
    g.tableau(s, 6.3, Y0 + 0.3, 6.6, lignes, largeurs=[1.5] + [(6.6 - 1.5) / (nc - 1)] * (nc - 1), taille=10, hauteur_ligne=0.4, gras_derniere=True)
    bandeau(ctx, s, an.s_groupes(ctx, grp))
    return s


def blocs_fixes(ctx, nom):
    """Diapositives fixes réutilisables : NPS autobiz (2), modèle d'URL avec balisage UTM (1)."""
    fr = ctx.langue == "fr"
    if nom == "nps":
        s = nouvelle(ctx, "NPS autobiz — pourquoi ?" if fr else "NPS at autobiz — why?", None)
        g.texte(s, X0, 1.6, 12.4, 0.5, ("Quel que soit le point de départ, l'objectif est d'améliorer le taux de réponse et le score NPS." if fr else "Whatever the starting point, the target is to improve the answer rate and the NPS score."), taille=16, gras=True, couleur=g.BLEU)
        g.puces(s, X0, 2.4, 12.4, 3.8, [
            ("Partager à l'avance les évolutions produit et les nouvelles fonctionnalités" if fr else "Share product evolutions and new features in advance"),
            ("Suivi régulier et rencontres physiques" if fr else "Regular follow-up and physical meetings"),
            ("Mise en place d'enquêtes qualitatives" if fr else "Qualitative surveys setup"),
            ("Plus de communication en amont" if fr else "More communication in advance")], taille=16)
        s = nouvelle(ctx, "NPS autobiz — comment ?" if fr else "NPS at autobiz — how?", None)
        g.puces(s, X0, 1.8, 12.4, 4.0, [("Prochaine enquête NPS : dates à renseigner (envoi par e-mail)." if fr else "Next NPS survey: dates to be filled in (sent by email).")], taille=16)
        return s
    if nom == "utm":
        s = nouvelle(ctx, "Modèle d'URL avec balisage UTM" if fr else "Template to generate URL with UTM tracking", None)
        ent = ["URL du site trade-in", "utm_source", "utm_medium", "utm_campaign", "URL à poser sur le bouton"] if fr else ["Trade-in site URL", "utm_source", "utm_medium", "utm_campaign", "URL to add to the CTA"]
        ex = ["https://reprise.marque.xx/", "Main-Website", "Showroom", "e-C3", "…?utm_source=Main-Website&utm_medium=Showroom&utm_campaign=e-C3"]
        g.tableau(s, X0, 1.8, 12.4, [ent, ex], largeurs=[2.4, 1.6, 1.6, 1.6, 5.2], taille=11, hauteur_ligne=0.5, alignements=None)
        g.puces(s, X0, 3.3, 12.4, 3.0, [
            ("Source et medium : à laisser tels quels (ils identifient les boutons du site de la marque)." if fr else "Source and medium: leave as is (they identify the brand-website CTAs)."),
            ("Pour les pages showroom uniquement : renseigner la campagne avec le modèle de la page (ex. « e-C3 »)." if fr else "For showroom pages only: set the campaign to the page's model (e.g. “e-C3”)."),
            ("L'URL finale se construit automatiquement à partir de ces colonnes ; c'est elle qu'il faut poser sur le bouton pour le suivre." if fr else "The final URL is built from these columns; it is the one to place on the button to track it.")], taille=14)
        return s


def leads_par_marque(ctx, cle, ref):
    t, d, per = ctx.t, ctx.d, ctx.per
    marques = [m for m in d.marques if d.leads_total(per, m) + d.leads_total(ref, m) > 0]
    cur = [d.leads_total(per, m) for m in marques]
    rf = [d.leads_total(ref, m) for m in marques]
    s = nouvelle(ctx, f"{t['leads']} — {ctx.et(per)} {libelle_ref(ctx, cle)}", f"{ctx.perimetre} · {ctx.et(per)} / {ctx.et(ref)}", source_bo(ctx),
                 notes=note_definitions(ctx), cle="leads_marques")
    perso = [None] + [[f"{t.nb(c)}\n{t.evol(c, r)[0]}" if t.evol(c, r)[2] is not None else t.nb(c) for c, r in zip(cur, rf)]]
    g.colonnes(s, X0, Y0, 8.9, 4.2, [ctx.nom(m) for m in marques],
               [(ctx.et(ref), rf, g.COULEURS_PERIODES[1]), (ctx.et(per), cur, g.COULEURS_PERIODES[2])],
               libelles_perso={1: perso[1]}, taille=10, fmt=t.nb)
    g.encadre(s, 9.55, Y0 + 0.1, 3.4, 4.0, None, commentaire_evolutions(ctx, [ctx.nom(m) for m in marques], cur, rf, f"({ctx.et(ref)})"), taille=10.5)
    bandeau(ctx, s, an.s_leads_marques(ctx, cle, ref))
    return s


def leads_mensuels(ctx, projet=None):
    t, d, per = ctx.t, ctx.d, ctx.per
    dernier = d.dernier_jour_leads()
    def complets(a, vals):
        """Seuls les mois entièrement écoulés sont tracés : le mois en cours (partiel) et les mois futurs restent vides."""
        out = []
        for k, v in enumerate(vals):
            fin_mois = Periode("mois", a, k + 1).fin.isoformat()
            out.append(v if (v and dernier and fin_mois <= dernier) else None)
        return out
    annees = [a for a in (per.annee - 2, per.annee - 1, per.annee) if sum(d.leads_mensuels(a, projet=projet)) > 0]
    if not annees:
        return None
    titre = (t["leads_nc"] if projet else t["leads"]) + f" {t['par_mois']}"
    s = nouvelle(ctx, titre, ctx.perimetre, source_bo(ctx), notes=note_definitions(ctx), cle=("leads_nc_mensuels" if projet else "leads_mensuels"))
    g.texte(s, X1 - 5.5, 1.12, 5.5, 0.3, ("Mois complets uniquement" if ctx.langue == "fr" else "Complete months only"), taille=9.5, couleur=g.GRIS, align=PP_ALIGN.RIGHT, italique=True)
    series = []
    for i, a in enumerate(annees):
        couleur = g.COULEURS_PERIODES[3 - len(annees) + i]
        vals = d.leads_mensuels(a, projet=projet)
        series.append((str(a), complets(a, vals), couleur))
    cats = MOIS_COURTS[ctx.langue]
    g.colonnes(s, X0, Y0, 12.4, 4.2, cats, series, taille=10, largeur_barre=40, fmt=t.nb)
    bandeau(ctx, s, an.s_mensuel(ctx, projet))
    return s


def apercu_marques(ctx):
    """Vue « Leads overview » : une ligne par marque (tendance et part New cars, moteurs de hausse ou de baisse, actions recommandées),
    xP puis xF, 6 marques par diapositive. Les actions sont des suggestions calculées ; `actionsMarques` du brief les remplace."""
    t, d, fr = ctx.t, ctx.d, ctx.langue == "fr"
    grp = groupes_de_marques(ctx)
    lots = [("XP", [m for k in ("XP", "Spoticar") for m in grp.get(k, [])] + [m for k in grp if k not in ("XP", "XF", "Spoticar") for m in grp[k]]), ("XF", grp.get("XF", []))]
    perso = ctx.brief.get("actionsMarques") or {}
    for nom_lot, marques in lots:
        marques = [m for m in marques if d.leads_total(ctx.per, m) + sum(d.leads_total(p, m) for _, p in ctx.refs) > 0]
        nb_diapos = -(-len(marques) // 6)
        taille_lot = -(-len(marques) // nb_diapos) if nb_diapos else 6      # lots équilibrés : 7 marques -> 4 + 3, jamais 6 + 1
        for i in range(0, len(marques), taille_lot or 6):
            morceau = marques[i:i + taille_lot]
            suite = "" if nb_diapos <= 1 else f" ({i // taille_lot + 1}/{nb_diapos})"
            s = nouvelle(ctx, f"Leads overview — {ctx.et(ctx.per)}{suite}" if not fr else f"Vue d'ensemble des leads — {ctx.et(ctx.per)}{suite}",
                         f"{ctx.perimetre} · {nom_lot}", source_bo(ctx),
                         notes=note_definitions(ctx, "Moteurs : écarts de leads par canal d'acquisition (back-office), part New cars et trafic GA4, vs la première période de comparaison. "
                                                     "Actions : suggestions calculées, à relire ; le champ « actionsMarques » du brief les remplace."), cle="apercu")
            ent = [t["marque"], ("Tendance & part New cars" if fr else "Lead trend & NC share"), ("Moteurs de la variation" if fr else "Drivers of increase / decrease"),
                   ("Actions recommandées" if fr else "Recommended actions")]
            lignes = [ent]
            for m in morceau:
                a = an.apercu_marque(ctx, m)
                tend = " | ".join(f"{e} {libelle_ref(ctx, c)}" for c, e in a["evols"]) or "–"
                if a["nc"]:
                    tend += f"\n{a['nc'][0]}"
                acts = perso.get(m) or a["actions"]
                lignes.append([ctx.nom(m), tend, "\n".join("• " + x for x in a["moteurs"]), "\n".join("• " + x for x in acts)])
            g.tableau(s, X0, Y0 + 0.05, 12.4, lignes, largeurs=[1.5, 2.6, 4.1, 4.2], taille=9, hauteur_ligne=0.68,
                      alignements=[PP_ALIGN.LEFT] * 4, colonnes_gras=(0,))
            g.texte(s, X0, 6.75, 12.4, 0.3, t["base_faible"], taille=8.5, couleur=g.GRIS, italique=True)


def cta_marque(ctx, m):
    """Leads issus des boutons trade-in du site de la marque (source Main-Website, campagne « CTA »), par emplacement et par projet d'achat."""
    t, d, per = ctx.t, ctx.d, ctx.per
    fr = ctx.langue == "fr"
    cur = d.cta(per, m)
    if not cur or not d.acquisition_disponible(per):
        return None
    ref = d.cta(ctx.refs[0][1], m) if ctx.refs else {}
    tot = lambda v: sum(v.values())
    supports = sorted(cur, key=lambda k: -tot(cur[k]))
    s = nouvelle(ctx, f"{ctx.nom(m)} — {'CTA du site de la marque' if fr else 'CTA on the brand website'} {ctx.et(per)}", ctx.perimetre, source_bo(ctx),
                 notes=note_definitions(ctx, "CTA : leads valides de la source Main-Website, campagne « CTA », par SUPPORT (emplacement du bouton) ; la colonne de comparaison est la première période de comparaison."), cle=f"marque:{m}")
    ent = [("Emplacement" if fr else "Placement")] + [t[pj] for pj in PROJETS] + [t["total"]]
    if ctx.refs:
        ent += [f"{t['total']} {ctx.et(ctx.refs[0][1])}", libelle_ref(ctx, ctx.refs[0][0])]
    lignes = [ent]
    for sup in supports:
        row = [sup] + [t.nb(cur[sup][pj]) for pj in PROJETS] + [t.nb(tot(cur[sup]))]
        if ctx.refs:
            r = tot(ref.get(sup, {}))
            row += [t.nb(r), t.evol(tot(cur[sup]), r)[0]]
        lignes.append(row)
    total = [t["total"]] + [t.nb(sum(cur[k][pj] for k in cur)) for pj in PROJETS] + [t.nb(sum(tot(v) for v in cur.values()))]
    if ctx.refs:
        tr = sum(tot(v) for v in ref.values())
        total += [t.nb(tr), t.evol(sum(tot(v) for v in cur.values()), tr)[0]]
    lignes.append(total)
    nc = len(ent)
    g.tableau(s, X0, Y0 + 0.1, 12.4, lignes, largeurs=[2.6] + [(12.4 - 2.6) / (nc - 1)] * (nc - 1), taille=10.5, hauteur_ligne=0.4, gras_derniere=True)
    gtot = sum(tot(v) for v in cur.values())
    top = supports[0]
    g.encadre(s, X0, Y0 + 0.4 * len(lignes) + 0.4, 12.4, 1.2, ("Lecture" if fr else "Reading"), [
        (f"« {top} » est l'emplacement qui génère le plus de leads : {t.nb(tot(cur[top]))} ({t.pct(tot(cur[top]) / gtot * 100, 0)} des leads CTA du site)."
         if fr else f"“{top}” is the placement generating the most leads: {t.nb(tot(cur[top]))} ({t.pct(tot(cur[top]) / gtot * 100, 0)} of the site's CTA leads)."),
        (f"{len(supports)} emplacements actifs sur la période." if fr else f"{len(supports)} active placements over the period.")], taille=11, couleur=g.BLEU)
    return s


def conquete_marque(ctx, m):
    """Conquête vs fidélité : origine des clients (marque du véhicule repris), top marques reprises, et top modèles repris / lien repris -> acheté si l'historique des modèles est collecté."""
    from .donnees import MARQUES_STELLANTIS, norme_marque
    t, d, per = ctx.t, ctx.d, ctx.per
    fr = ctx.langue == "fr"
    rep = d.reprises(per, m)
    total = sum(rep.values())
    if total < 100:
        return None
    nm = norme_marque(m)
    fideles = rep.get(nm, 0)
    autres = sum(n for k, n in rep.items() if k != nm and k in MARQUES_STELLANTIS)
    conq = total - fideles - autres
    s = nouvelle(ctx, f"{ctx.nom(m)} — {'Conquête vs fidélité' if fr else 'Conquest vs loyalty'} {ctx.et(per)}", ctx.perimetre, source_bo(ctx),
                 notes=note_definitions(ctx, "Marque du véhicule repris (TRADE-IN BRAND) comparée à la marque du site : fidèles = même marque ; autres Stellantis ; concurrents = toutes les autres marques."), cle=f"marque:{m}")
    lab = (f"Fidèles ({ctx.nom(m)})", "Autres Stellantis", "Concurrents") if fr else (f"Loyalty ({ctx.nom(m)})", "Other Stellantis", "Competitors")
    g.texte(s, X0, Y0 - 0.05, 5.5, 0.3, "Origine des clients" if fr else "Customer origin", taille=12, gras=True, couleur=g.BLEU)
    g.anneau(s, X0, Y0 + 0.25, 5.6, 2.6, list(lab), [fideles, autres, conq], couleurs=["4E79A7", "76B7B2", "F28E2B"], taille=10.5)
    top = sorted(((k, n) for k, n in rep.items()), key=lambda kv: -kv[1])[:8]
    g.texte(s, 6.4, Y0 - 0.05, 6.4, 0.3, ("Top marques reprises" if fr else "Top trade-in brands"), taille=12, gras=True, couleur=g.BLEU)
    g.colonnes(s, 6.4, Y0 + 0.25, 6.5, 2.6, [(k if len(k) <= 3 else k.title()) for k, _ in top], [("n", [n for _, n in top], "4E79A7")], legende=False, taille=9, fmt=t.nb, largeur_barre=40)
    lignes = [(f"{t.pct(fideles / total * 100, 0)} des clients du site reprennent un véhicule {ctx.nom(m)} (fidèles), {t.pct(autres / total * 100, 0)} une autre marque Stellantis "
               f"et {t.pct(conq / total * 100, 0)} une marque concurrente, sur {t.nb(total)} leads." if fr else
               f"{t.pct(fideles / total * 100, 0)} of the site's customers trade in a {ctx.nom(m)} (loyalty), {t.pct(autres / total * 100, 0)} another Stellantis brand and "
               f"{t.pct(conq / total * 100, 0)} a competitor brand, out of {t.nb(total)} leads.")]
    mods = d.modeles(per, m)
    if mods:
        stla = {}
        hors = {}
        for mr, mo, ma, mo_a, n in mods:
            if mo:
                (stla if mr in MARQUES_STELLANTIS else hors)[f"{mr.title()} {mo.title()}"] = (stla if mr in MARQUES_STELLANTIS else hors).get(f"{mr.title()} {mo.title()}", 0) + n
        paires = {}
        for mr, mo, ma, mo_a, n in mods:
            if mo and mo_a:
                paires[(f"{mr.title()} {mo.title()}", mo_a.title())] = paires.get((f"{mr.title()} {mo.title()}", mo_a.title()), 0) + n
        if stla and hors:
            ts, th = sorted(stla.items(), key=lambda kv: -kv[1])[:5], sorted(hors.items(), key=lambda kv: -kv[1])[:5]
            lignes.append((f"Modèles Stellantis les plus repris : {', '.join(k for k, _ in ts)}. Modèles concurrents les plus repris : {', '.join(k for k, _ in th)}." if fr else
                           f"Most traded-in Stellantis models: {', '.join(k for k, _ in ts)}. Most traded-in competitor models: {', '.join(k for k, _ in th)}."))
        if paires:
            tp = sorted(paires.items(), key=lambda kv: -kv[1])[:4]
            lignes.append(("Reprise → achat les plus fréquents : " if fr else "Most frequent trade-in → purchase: ") + " ; ".join(f"{a} → {b} ({t.nb(n)})" for (a, b), n in tp))
    g.encadre(s, X0, Y0 + 3.05, 12.4, 1.9, ("Lecture" if fr else "Reading"), lignes, taille=11, couleur=g.BLEU)
    return s


NOMS_PAYS = {
    "it": {"FR": "Francia", "BE": "BELUX", "LU": "BELUX", "ES": "Spagna", "PT": "Portogallo", "IT": "Italia", "DE": "Germania", "PL": "Polonia", "GB": "Regno Unito", "UK": "Regno Unito", "AT": "Austria"},
    "es": {"FR": "Francia", "BE": "BELUX", "LU": "BELUX", "ES": "España", "PT": "Portugal", "IT": "Italia", "DE": "Alemania", "PL": "Polonia", "GB": "Reino Unido", "UK": "Reino Unido", "AT": "Austria"},
    "de": {"FR": "Frankreich", "BE": "BELUX", "LU": "BELUX", "ES": "Spanien", "PT": "Portugal", "IT": "Italien", "DE": "Deutschland", "PL": "Polen", "GB": "Vereinigtes Königreich", "UK": "Vereinigtes Königreich", "AT": "Österreich"},
    "fr": {"FR": "France", "BE": "BELUX", "LU": "BELUX", "ES": "Espagne", "PT": "Portugal", "IT": "Italie", "DE": "Allemagne", "PL": "Pologne", "GB": "Royaume-Uni", "UK": "Royaume-Uni", "AT": "Autriche"},
    "en": {"FR": "France", "BE": "BELUX", "LU": "BELUX", "ES": "Spain", "PT": "Portugal", "IT": "Italy", "DE": "Germany", "PL": "Poland", "GB": "United Kingdom", "UK": "United Kingdom", "AT": "Austria"},
}


def classement_marches(ctx):
    """Leads New cars (VN) par marché autobiz sur la période : rang, part du total, évolution vs N-1 et cumul de l'année. Belgique et Luxembourg sont regroupés (BELUX)."""
    from datetime import date as _d
    from pipeline.leads_extract import SITE_EXTRACT
    t, per = ctx.t, ctx.per
    fr = ctx.langue == "fr"
    tous = sorted({nom.rsplit(" ", 1)[1] for nom in SITE_EXTRACT})
    if len(tous) < 3:
        return None
    noms = NOMS_PAYS.get(ctx.langue, NOMS_PAYS["en"])
    dall = Donnees(tous, None, hist=ctx.d.hist)
    dernier = dall.dernier_jour_leads()
    if not dernier:
        return None
    fin_ytd = min(per.fin, _d.fromisoformat(dernier))
    class _Ytd:
        debut, fin = _d(per.annee, 1, 1), fin_ytd
    n1 = per.n1()
    from .donnees import PROJET_BO, _lignes, slug
    par_pays = {}
    for nom, marque, pays in dall.sites:
        k = noms.get(pays, pays)
        a = par_pays.setdefault(k, {"cur": 0, "n1": 0, "ytd": 0})
        for r in _lignes(dall.hist / "leads" / f"{slug(nom)}.csv.gz"):
            if r["statut"] != "valide" or PROJET_BO.get(r["projet_achat"], "SANS") != "VN":
                continue
            j, n = r["date"], int(r["n"])
            if per.debut.isoformat() <= j <= per.fin.isoformat():
                a["cur"] += n
            if n1.debut.isoformat() <= j <= n1.fin.isoformat():
                a["n1"] += n
            if _Ytd.debut.isoformat() <= j <= _Ytd.fin.isoformat():
                a["ytd"] += n
    total = sum(a["cur"] for a in par_pays.values())
    total_ytd = sum(a["ytd"] for a in par_pays.values())
    if total < 100:
        return None
    classe = sorted(par_pays.items(), key=lambda kv: -kv[1]["cur"])
    mon = noms.get(ctx.brief["perimetre"]["pays"][0].upper(), ctx.perimetre)
    s = nouvelle(ctx, ("Classement des marchés — leads New cars" if fr else "Market ranking — New cars leads"), ctx.perimetre, source_bo(ctx),
                 notes=note_definitions(ctx, "Leads New cars (projet VN, leads valides) de tous les marchés autobiz ; Belgique et Luxembourg regroupés. Cumul = du 1er janvier à la fin de la période (ou au dernier jour connu)."), cle="marches")
    ent = [("Rang" if fr else "Rank"), ("Marché" if fr else "Market"), f"{t['leads_nc']} {ctx.et(per)}", t["part_total"], libelle_ref(ctx, "n1"),
           (f"Cumul {per.annee}" if fr else f"YTD {per.annee}"), (f"Part du cumul" if fr else "YTD share")]
    lignes = [ent]
    for i, (k, a) in enumerate(classe, 1):
        lignes.append([str(i), k, t.nb(a["cur"]), t.pct(a["cur"] / total * 100, 0), t.evol(a["cur"], a["n1"])[0], t.nb(a["ytd"]),
                       t.pct(a["ytd"] / total_ytd * 100, 0) if total_ytd else "–"])
    lignes.append(["", t["total"], t.nb(total), "100 %", t.evol(total, sum(a["n1"] for a in par_pays.values()))[0], t.nb(total_ytd), "100 %"])
    g.tableau(s, X0, Y0 + 0.1, 8.2, lignes, largeurs=[0.7, 1.9, 1.5, 1.1, 1.0, 1.2, 0.8], taille=10, hauteur_ligne=0.36, gras_derniere=True,
              alignements=[PP_ALIGN.CENTER, PP_ALIGN.LEFT] + [PP_ALIGN.RIGHT] * 5)
    rang = next((i for i, (k, _) in enumerate(classe, 1) if k == mon), None)
    if rang:
        a = par_pays[mon]
        txt = [(f"{mon} se classe n°{rang} sur {len(classe)} marchés, avec {t.pct(a['cur'] / total * 100, 0)} des leads New cars autobiz sur la période ({t.nb(a['cur'])} leads)."
                if fr else f"{mon} ranks #{rang} of {len(classe)} markets, with {t.pct(a['cur'] / total * 100, 0)} of autobiz New cars leads over the period ({t.nb(a['cur'])} leads)."),
               (f"Évolution : {t.evol(a['cur'], a['n1'])[0]} {libelle_ref(ctx, 'n1')}." if fr else f"Change: {t.evol(a['cur'], a['n1'])[0]} {libelle_ref(ctx, 'n1')}.")]
        g.encadre(s, 9.0, Y0 + 0.1, 3.9, 3.2, ("Lecture" if fr else "Reading"), txt, taille=11, couleur=g.BLEU)
    return s


def entree_vehicule(ctx):
    """Mode de saisie du véhicule dans les leads : avec immatriculation (plaque) ou marque / modèle, par marque, vs période précédente et N-1 (en points)."""
    t, d, per = ctx.t, ctx.d, ctx.per
    fr = ctx.langue == "fr"
    lignes_marque = []
    for m in d.marques:
        e = d.entree_leads(per, m)
        if not e or e["plaque"] + e["marque_modele"] < 100:
            continue
        lignes_marque.append((m, e))
    if not lignes_marque:
        return None
    part = lambda e: e["plaque"] / (e["plaque"] + e["marque_modele"]) * 100
    def delta(m, e, p):
        r = d.entree_leads(p, m)
        return t.pts(part(e) - part(r)) if r and r["plaque"] + r["marque_modele"] >= 100 else t["n_s"]
    ent = [t["marque"], ("Avec plaque" if fr else "With plate"), ("Marque / modèle" if fr else "Make / model"), ("Part avec plaque" if fr else "Plate share")] + \
          [libelle_ref(ctx, c) for c, _ in ctx.refs]
    lignes = [ent]
    tp = tm = 0
    for m, e in lignes_marque:
        lignes.append([ctx.nom(m), t.nb(e["plaque"]), t.nb(e["marque_modele"]), t.pct(part(e), 0)] + [delta(m, e, p) for _, p in ctx.refs])
        tp += e["plaque"]; tm += e["marque_modele"]
    tot = {"plaque": tp, "marque_modele": tm}
    row = [t["total"], t.nb(tp), t.nb(tm), t.pct(part(tot), 0)]
    for _, p in ctx.refs:
        rp = rm = 0
        for m, _e in lignes_marque:
            r = d.entree_leads(p, m)
            if r:
                rp += r["plaque"]; rm += r["marque_modele"]
        row.append(t.pts(part(tot) - part({"plaque": rp, "marque_modele": rm})) if rp + rm >= 100 else t["n_s"])
    lignes.append(row)
    s = nouvelle(ctx, ("Mode de saisie du véhicule : plaque ou marque / modèle" if fr else "Vehicle entry: licence plate or make / model"), ctx.perimetre, source_bo(ctx),
                 notes=note_definitions(ctx, "Part des leads dont le client a saisi son immatriculation (colonne REGISTRATION-PLATE du back-office) plutôt que la marque et le modèle de son véhicule ; évolution en points de pourcentage."),
                 cle="entree_vehicule")
    nc = len(ent)
    g.tableau(s, X0, Y0 + 0.1, 12.4, lignes, largeurs=[2.4] + [(12.4 - 2.4) / (nc - 1)] * (nc - 1), taille=10.5, hauteur_ligne=0.38, gras_derniere=True)
    g.texte(s, X0, 6.55, 12.4, 0.5,
            (f"{t.pct(part(tot), 0)} des leads de la période sont saisis avec la plaque d'immatriculation ; le taux de complétion par mode de saisie n'est pas mesuré dans les données du back-office."
             if fr else f"{t.pct(part(tot), 0)} of the period's leads are entered with the licence plate; the completion rate by entry mode is not measured in the back-office data."),
            taille=9, couleur=g.GRIS, italique=True)
    return s


def v2_marque(ctx, m):
    """Parcours avant / après la bascule en V2 : utilisateurs par étape du tunnel (part de l'accueil) et complétion de bout en bout, pour les sites V2 de la marque."""
    t, d = ctx.t, ctx.d
    fr = ctx.langue == "fr"
    v = d.v2(m)
    if not v or len(v["etapes"]) < 2 or v["etapes"][0][1] < 100 or v["etapes"][0][2] < 100:
        return None
    et = v["etapes"]
    a0, b0 = et[0][1], et[0][2]
    s = nouvelle(ctx, f"{ctx.nom(m)} — {'Parcours avant / après la V2' if fr else 'Journey before / after V2'}", ctx.perimetre, source_ga4(ctx),
                 notes=note_definitions(ctx, "Utilisateurs distincts par étape du tunnel (GA4), part de la page d'accueil ; avant = 28 jours précédant la bascule, après = depuis la bascule (fenêtres propres à chaque site). "
                                             + " ; ".join(f"{n} : {pre} → {post}" for n, pre, post in v["fenetres"])),
                 cle=f"marque:{m}")
    ent = [("Étape" if fr else "Step"), ("Avant" if fr else "Before"), ("% accueil" if fr else "% of homepage"), ("Après" if fr else "After"), ("% accueil" if fr else "% of homepage"), ("Écart" if fr else "Change")]
    lignes = [ent]
    for nom, a, b in et:
        pa, pb = a / a0 * 100, b / b0 * 100
        lignes.append([nom, t.nb(a), t.pct(pa, 1), t.nb(b), t.pct(pb, 1), t.pts(pb - pa) if abs(pb - pa) >= 0.5 else (t["n_s"] if False else "=")])
    g.tableau(s, X0, Y0 + 0.1, 8.0, lignes, largeurs=[2.6, 1.1, 1.1, 1.1, 1.1, 1.0], taille=10.5, hauteur_ligne=0.4)
    ca, cb = et[-1][1] / a0 * 100, et[-1][2] / b0 * 100
    g.tuile(s, 8.9, Y0 + 0.1, 4.0, 1.4, ("Complétion de bout en bout" if fr else "End-to-end completion"), f"{t.pct(ca, 1)} → {t.pct(cb, 1)}", t.pts(cb - ca) if abs(cb - ca) >= 0.5 else "=", taille_valeur=24)
    g.encadre(s, 8.9, Y0 + 1.75, 4.0, 2.0, ("Lecture" if fr else "Reading"), [
        (f"{v['sites']} site{'s' if v['sites'] > 1 else ''} V2 dans le périmètre. Avant : les 28 jours précédant la bascule ; après : depuis la bascule." if fr else
         f"{v['sites']} V2 site{'s' if v['sites'] > 1 else ''} in scope. Before: the 28 days before the switch; after: since the switch."),
        (f"Utilisateurs atteignant l'estimation : {t.nb(et[-1][1])} → {t.nb(et[-1][2])} (période d'observation différente)." if fr else
         f"Users reaching the estimate: {t.nb(et[-1][1])} → {t.nb(et[-1][2])} (different observation windows).")], taille=10.5, couleur=g.BLEU)
    return s


def projection_mois(ctx):
    """Projection de fin de mois des leads New cars par marque, pour une édition mensuelle dont le mois n'est pas terminé :
    leads du 1er au dernier jour connu, ramenés à la durée du mois au rythme moyen constant (indicatif), comparés au même mois de l'an dernier et au mois précédent."""
    import calendar
    t, d, per = ctx.t, ctx.d, ctx.per
    fr = ctx.langue == "fr"
    dernier = d.dernier_jour_leads()
    if per.type != "mois" or not dernier or dernier >= per.fin.isoformat() or dernier < per.debut.isoformat():
        return None
    jours_ecoules = int(dernier[8:10])
    jours_mois = calendar.monthrange(per.annee, per.mois_debut)[1]
    from datetime import date as _d
    class _P:                                        # période « du 1er au dernier jour connu »
        debut, fin = per.debut, _d.fromisoformat(dernier)
    n1, prec = per.n1(), per.precedente()
    lignes = [[t["marque"], f"{t['leads_nc']} 1–{jours_ecoules}", ("Projection fin de mois" if fr else "End-of-month projection"),
               f"{t['leads_nc']} {ctx.et(n1)}", libelle_ref(ctx, "n1"), f"{t['leads_nc']} {ctx.et(prec)}", libelle_ref(ctx, "prec")]]
    tot = [0, 0.0, 0, 0]
    for m in d.marques:
        cur = d.leads(_P, m)["VN"]
        r1, rp = d.leads(n1, m)["VN"], d.leads(prec, m)["VN"]
        if cur + r1 + rp == 0:
            continue
        proj = cur / jours_ecoules * jours_mois
        lignes.append([ctx.nom(m), t.nb(cur), t.nb(proj), t.nb(r1), t.evol(proj, r1)[0], t.nb(rp), t.evol(proj, rp)[0]])
        tot[0] += cur; tot[1] += proj; tot[2] += r1; tot[3] += rp
    if len(lignes) < 2:
        return None
    lignes.append([t["total"], t.nb(tot[0]), t.nb(tot[1]), t.nb(tot[2]), t.evol(tot[1], tot[2])[0], t.nb(tot[3]), t.evol(tot[1], tot[3])[0]])
    s = nouvelle(ctx, (f"Projection {ctx.et(per)} — leads New cars" if fr else f"{ctx.et(per)} projection — New cars leads"), ctx.perimetre, source_bo(ctx),
                 notes=note_definitions(ctx, f"Projection = leads New cars du 1er au {jours_ecoules} ÷ {jours_ecoules} jours × {jours_mois} jours : rythme moyen constant, indicatif (ne tient pas compte de la saisonnalité intra-mois)."), cle="projection")
    g.tableau(s, X0, Y0 + 0.1, 12.4, lignes, largeurs=[2.1, 1.7, 1.9, 1.7, 1.7, 1.7, 1.6], taille=10.5, hauteur_ligne=0.38, gras_derniere=True)
    g.texte(s, X0, 6.55, 12.4, 0.5,
            (f"Données du 1er au {jours_ecoules} {MOIS_COURTS[ctx.langue][per.mois_debut - 1]} : la projection prolonge le rythme moyen quotidien sur les {jours_mois} jours du mois (indicatif)."
             if fr else f"Data from {MOIS_COURTS[ctx.langue][per.mois_debut - 1]} 1 to {jours_ecoules}: the projection extends the average daily rate over the {jours_mois} days of the month (indicative)."),
            taille=9, couleur=g.GRIS, italique=True)
    return s


SOURCE_C1ST = ("Source : C1ST (CRM Analytics)", "Source: C1ST (CRM Analytics)")
PERIMETRE_C1ST = ("Périmètre : leads VN envoyés vus par C1ST (type 1, activité VN, campagne Autobiz) ; périmètre propre à C1ST, non comparable au back-office.",
                  "Scope: VN leads sent as seen by C1ST (type 1, VN activity, Autobiz campaign); C1ST's own scope, not comparable with the back-office.")


SANS_SUIVI_C1ST = ("SPOTICAR",)      # C1ST ne suit ni le contact, ni le traitement, ni les commandes de Spoticar (leads de rachat) : « n.d. », exclu des totaux de taux


def _c1st_lignes(ctx):
    """[(marque, totaux C1ST sur la période, {clé de comparaison: totaux})] des marques du périmètre disposant des données C1ST complètes."""
    out = []
    for m in ctx.d.marques:
        c = ctx.d.c1st(ctx.per, m)
        if c and c["envoyes"] >= 100:
            out.append((m, c, {cle: ctx.d.c1st(p, m) for cle, p in ctx.refs}))
    return out


def c1st_lead_management(ctx):
    """Suivi des leads envoyés aux concessionnaires (C1ST) : contactés, contactés dans les délais, premier appel dans les délais, traités, non gérés."""
    t, per = ctx.t, ctx.per
    fr = ctx.langue == "fr"
    lignes_m = _c1st_lignes(ctx)
    if not lignes_m:
        return None
    ent = [t["marque"], ("Clients envoyés" if fr else "Customers sent"), ("Contactés" if fr else "Contacted"), ("Contactés dans les délais" if fr else "Contacted on time"),
           ("1er appel dans les délais" if fr else "1st call on time"), ("Traités" if fr else "Treated"), ("Non traités" if fr else "Not treated")]
    pct = lambda a, b: t.pct(a / b * 100, 0) if b else "–"
    def ligne(nom, c, suivi=True):
        b = c["clients_envoyes"]
        if not suivi:
            return [nom, t.nb(b)] + [t["non_dispo"]] * 5
        return [nom, t.nb(b), pct(c["contactes"], b), pct(c["contactes_delai"], b), pct(c["premier_appel_delai"], b), pct(c["traites"], b), pct(max(b - c["traites"], 0), b)]
    suivies = [x for x in lignes_m if x[0] not in SANS_SUIVI_C1ST]
    if not suivies:
        return None
    lignes = [ent] + [ligne(ctx.nom(m), c, m not in SANS_SUIVI_C1ST) for m, c, _ in lignes_m]
    tot = {k: sum(c[k] for _, c, _ in suivies) for k in suivies[0][1]}
    lignes.append(ligne(t["total"], tot))
    s = nouvelle(ctx, ("Suivi des leads envoyés aux concessionnaires" if fr else "Follow-up of leads sent to dealers") + f" — {ctx.et(per)}", ctx.perimetre,
                 SOURCE_C1ST[0 if fr else 1], notes=note_definitions(ctx, "Taux calculés sur les clients uniques envoyés aux concessionnaires. Non traités = envoyés − traités (statuts saisis par les concessionnaires dans C1ST ; pas de comparaison dans le temps)."), cle="c1st_lead_management")
    nc = len(ent)
    hl = min(0.38, 3.6 / len(lignes))
    g.tableau(s, X0, Y0 + 0.1, 12.4, lignes, largeurs=[2.2] + [(12.4 - 2.2) / (nc - 1)] * (nc - 1), taille=(10.5 if len(lignes) <= 8 else 9.5), hauteur_ligne=hl, gras_derniere=True)
    nt = pct(max(tot["clients_envoyes"] - tot["traites"], 0), tot["clients_envoyes"])
    g.encadre(s, X0, Y0 + 0.1 + hl * len(lignes) + 0.2, 12.4, 1.5, ("Lecture" if fr else "Reading"), [
        (f"{nt} des leads envoyés n'ont pas de statut de traitement dans C1ST sur la période." if fr else f"{nt} of the leads sent have no treatment status in C1ST over the period."),
        ("Ces taux reflètent les statuts saisis par les concessionnaires dans C1ST : le suivi est déployé progressivement selon les marchés et les marques, ils ne sont donc pas comparables d'une période à l'autre."
         if fr else "These rates reflect the statuses entered by dealers in C1ST: the follow-up is being rolled out gradually by market and brand, so they cannot be compared from one period to another.")]
        + ([("Spoticar : C1ST ne suit pas le contact ni le traitement de ces leads de rachat (n.d.) ; la marque est exclue du total."
             if fr else "Spoticar: C1ST does not track contact or treatment of these buyback leads (n/a); the brand is excluded from the total.")]
           if any(m in SANS_SUIVI_C1ST for m, _, _ in lignes_m) else []),
        taille=10, couleur=g.BLEU)
    g.texte(s, X0, 6.72, 12.4, 0.35, PERIMETRE_C1ST[0 if fr else 1], taille=8.5, couleur=g.GRIS, italique=True)
    return s


def c1st_conversion(ctx):
    """Du lead à la commande (C1ST) : clients uniques, part avec opportunité, avec devis, commandes (jusqu'à 90 jours après le lead)."""
    t, per = ctx.t, ctx.per
    fr = ctx.langue == "fr"
    lignes_m = _c1st_lignes(ctx)
    if not lignes_m:
        return None
    ent = [t["marque"], ("Clients uniques" if fr else "Unique customers"), ("Avec opportunité" if fr else "With opportunity"), ("Avec devis" if fr else "With quote"),
           ("Commandes NSC" if fr else "NSC orders"), ("Taux de commande" if fr else "Order rate")]
    pct = lambda a, b: t.pct(a / b * 100, 1) if b else "–"
    def ligne(nom, c, suivi=True):
        b = c["clients_uniques"]
        if not suivi:
            return [nom, t.nb(b), pct(c["avec_opp"], b), pct(c["avec_devis"], b), t["non_dispo"], t["non_dispo"]]
        return [nom, t.nb(b), pct(c["avec_opp"], b), pct(c["avec_devis"], b), t.nb(c["commandes"]), pct(c["commandes"], b)]
    suivies = [x for x in lignes_m if x[0] not in SANS_SUIVI_C1ST]
    if not suivies:
        return None
    lignes = [ent] + [ligne(ctx.nom(m), c, m not in SANS_SUIVI_C1ST) for m, c, _ in lignes_m]
    tot = {k: sum(c[k] for _, c, _ in suivies) for k in suivies[0][1]}
    lignes.append(ligne(t["total"], tot))
    s = nouvelle(ctx, ("Du lead à la commande" if fr else "From lead to order") + f" — {ctx.et(per)}", ctx.perimetre, SOURCE_C1ST[0 if fr else 1],
                 notes=note_definitions(ctx, "Taux calculés sur les clients uniques. Commandes NSC : commandes (jeu « SUB » de C1ST) rattachées au lead entre 1 et 90 jours après sa création ; taux de commande = commandes NSC ÷ clients uniques ; les périodes récentes continuent d'évoluer."),
                 cle="c1st_conversion")
    nc = len(ent)
    hl = min(0.38, 3.6 / len(lignes))
    g.tableau(s, X0, Y0 + 0.1, 12.4, lignes, largeurs=[2.4] + [(12.4 - 2.4) / (nc - 1)] * (nc - 1), taille=(10.5 if len(lignes) <= 8 else 9.5), hauteur_ligne=hl, gras_derniere=True)
    from datetime import timedelta as _td
    seuil = ctx.aujourdhui - _td(days=90)
    mur = lambda p: p.fin <= seuil
    refs_txt = []
    if not mur(per):
        refs_txt.append("Période récente : les commandes continuent d'être rattachées aux leads pendant 90 jours, les taux sont provisoires et aucune évolution n'est calculée." if fr else
                        "Recent period: orders keep being linked to the leads for 90 days, so the rates are provisional and no change is calculated.")
    else:
        for cle, p in ctx.refs:
            rt = {k: 0 for k in tot}
            ok = mur(p)
            for _, _, refs in suivies:
                r = refs.get(cle)
                if not r:
                    ok = False
                    break
                for k in rt:
                    rt[k] += r[k]
            if ok and rt["clients_uniques"] >= 100:
                d_ = (tot["commandes"] / tot["clients_uniques"] - rt["commandes"] / rt["clients_uniques"]) * 100
                refs_txt.append((f"Taux de commande : {t.pts(d_)} {libelle_ref(ctx, cle)}." if fr else f"Order rate: {t.pts(d_)} {libelle_ref(ctx, cle)}."))
    g.encadre(s, X0, Y0 + 0.1 + hl * len(lignes) + 0.2, 12.4, 1.5, ("Lecture" if fr else "Reading"), [
        (f"{t.nb(tot['commandes'])} commandes NSC rattachées aux leads de la période, soit {pct(tot['commandes'], tot['clients_uniques'])} des clients uniques." if fr else
         f"{t.nb(tot['commandes'])} NSC orders linked to the period's leads, i.e. {pct(tot['commandes'], tot['clients_uniques'])} of unique customers."),
        ("Les commandes sont comptées jusqu'à 90 jours après le lead." if fr else "Orders are counted up to 90 days after the lead.")]
        + ([("Spoticar : pas de commandes dans C1ST pour ces leads de rachat (n.d.) ; la marque est exclue du total."
             if fr else "Spoticar: no orders in C1ST for these buyback leads (n/a); the brand is excluded from the total.")]
           if any(m in SANS_SUIVI_C1ST for m, _, _ in lignes_m) else []) + refs_txt, taille=10, couleur=g.BLEU)
    g.texte(s, X0, 6.72, 12.4, 0.35, PERIMETRE_C1ST[0 if fr else 1], taille=8.5, couleur=g.GRIS, italique=True)
    return s


def c1st_ventes_additionnelles(ctx):
    """Ventes additionnelles (C1ST) = commandes NSC de la période − commandes NSC de la même période l'an dernier, par marque, et cumul de l'année."""
    from datetime import timedelta as _td
    t, per = ctx.t, ctx.per
    fr = ctx.langue == "fr"
    if per.type == "annee" and False:
        return None
    n1 = per.n1()

    class _Cumul:                                        # du 1er janvier à la fin de la période
        def __init__(self, annee, mois_fin):
            self._m = [(annee, m) for m in range(1, mois_fin + 1)]
        def mois(self):
            return self._m
    fin_m = per.mois()[-1][1]
    cumul, cumul_n1 = _Cumul(per.annee, fin_m), _Cumul(per.annee - 1, fin_m)
    avec_cumul = per.mois()[0] != (per.annee, 1)
    lignes_m = []
    for m in ctx.d.marques:
        if m in SANS_SUIVI_C1ST:
            continue
        a, b = ctx.d.c1st_nsc(per, m), ctx.d.c1st_nsc(n1, m)
        if a is None or b is None:
            continue
        ca, cb = (ctx.d.c1st_nsc(cumul, m), ctx.d.c1st_nsc(cumul_n1, m)) if avec_cumul else (None, None)
        lignes_m.append((m, a, b, ca, cb))
    if not lignes_m:
        return None
    sg = lambda v: ("+" if v > 0 else "−" if v < 0 else "") + t.nb(abs(v))
    ent = [t["marque"], f"NSC orders {ctx.et(per)}" if not fr else f"Commandes NSC {ctx.et(per)}", f"NSC orders {ctx.et(n1)}" if not fr else f"Commandes NSC {ctx.et(n1)}",
           ("Ventes additionnelles" if fr else "Additional sales")]
    if avec_cumul:
        ent += [(f"Commandes NSC cumul {per.annee}" if fr else f"YTD NSC orders {per.annee}"), (f"Commandes NSC cumul {per.annee - 1}" if fr else f"YTD NSC orders {per.annee - 1}"),
                ("Ventes additionnelles cumul" if fr else "Additional sales (YTD)")]
    lignes = [ent]
    for m, a, b, ca, cb in lignes_m:
        row = [ctx.nom(m), t.nb(a), t.nb(b), sg(a - b)]
        if avec_cumul:
            row += [t.nb(ca), t.nb(cb), sg(ca - cb)] if ca is not None and cb is not None else [t["non_dispo"]] * 3
        lignes.append(row)
    ta, tb = sum(x[1] for x in lignes_m), sum(x[2] for x in lignes_m)
    tot = [t["total"], t.nb(ta), t.nb(tb), sg(ta - tb)]
    if avec_cumul:
        cc = [x for x in lignes_m if x[3] is not None and x[4] is not None]
        tot += [t.nb(sum(x[3] for x in cc)), t.nb(sum(x[4] for x in cc)), sg(sum(x[3] - x[4] for x in cc))]
    lignes.append(tot)
    s = nouvelle(ctx, (f"Ventes additionnelles — {ctx.et(per)}" if fr else f"Additional sales — {ctx.et(per)}"), ctx.perimetre, SOURCE_C1ST[0 if fr else 1],
                 notes=note_definitions(ctx, "Ventes additionnelles = commandes NSC de la période − commandes NSC de la même période l'an dernier (commandes rattachées au lead entre 1 et 90 jours après sa création)."),
                 cle="c1st_ventes_additionnelles")
    nc = len(ent)
    hl = min(0.38, 3.6 / len(lignes))
    g.tableau(s, X0, Y0 + 0.1, 12.4, lignes, largeurs=[2.0] + [(12.4 - 2.0) / (nc - 1)] * (nc - 1), taille=(10.5 if len(lignes) <= 8 else 9.5), hauteur_ligne=hl, gras_derniere=True)
    mur = per.fin <= ctx.aujourdhui - _td(days=90)
    g.encadre(s, X0, Y0 + 0.1 + hl * len(lignes) + 0.2, 12.4, 1.5, ("Lecture" if fr else "Reading"), [
        (f"Ventes additionnelles vs la même période l'an dernier : {sg(ta - tb)} ({t.nb(ta)} commandes NSC contre {t.nb(tb)})." if fr else
         f"Additional sales vs the same period last year: {sg(ta - tb)} ({t.nb(ta)} NSC orders vs {t.nb(tb)})."),
        ("Ventes additionnelles = commandes NSC de la période − commandes NSC de la même période l'an dernier (commandes rattachées au lead jusqu'à 90 jours après sa création)." if fr else
         "Additional sales = NSC orders of the period − NSC orders of the same period last year (orders linked to the lead up to 90 days after its creation).")]
        + ([] if mur else [("Période récente : les commandes continuent d'être rattachées aux leads pendant 90 jours, les ventes additionnelles affichées sont provisoires." if fr else
                            "Recent period: orders keep being linked to the leads for 90 days, so the additional sales shown are provisional.")]), taille=10, couleur=g.BLEU)
    g.texte(s, X0, 6.72, 12.4, 0.35, PERIMETRE_C1ST[0 if fr else 1], taille=8.5, couleur=g.GRIS, italique=True)
    return s


def vue_ensemble_table(ctx):
    t, d, per = ctx.t, ctx.d, ctx.per
    s = nouvelle(ctx, f"{t['trafic']} & {t['leads'].lower()} — {ctx.et(per)}", ctx.perimetre, source_les_deux(ctx), notes=note_definitions(ctx), cle="vue_trafic_leads")
    ent = [t["marque"], f"{t['sessions_col']} {ctx.et(per)}"] + [f"{libelle_ref(ctx, c)}" for c, _ in ctx.refs] + [f"{t['leads']} {ctx.et(per)}"] + [f"{libelle_ref(ctx, c)}" for c, _ in ctx.refs]
    lignes = [ent]
    tot_s, tot_l = 0, 0
    tot_sr = [0] * len(ctx.refs); tot_lr = [0] * len(ctx.refs)
    for m in d.marques:
        s_cur = sum(d.canaux(per, m).values()); l_cur = d.leads_total(per, m)
        if not (s_cur or l_cur):
            continue
        row = [ctx.nom(m), t.nb(s_cur)]
        for k, (_, p) in enumerate(ctx.refs):
            sr = sum(d.canaux(p, m).values()); tot_sr[k] += sr
            row.append(t.evol(s_cur, sr)[0])
        row.append(t.nb(l_cur))
        for k, (_, p) in enumerate(ctx.refs):
            lr = d.leads_total(p, m); tot_lr[k] += lr
            row.append(t.evol(l_cur, lr)[0])
        tot_s += s_cur; tot_l += l_cur
        lignes.append(row)
    lignes.append([t["total"], t.nb(tot_s)] + [t.evol(tot_s, v)[0] for v in tot_sr] + [t.nb(tot_l)] + [t.evol(tot_l, v)[0] for v in tot_lr])
    nc = len(ent)
    lw = [2.4] + [(12.4 - 2.4) / (nc - 1)] * (nc - 1)
    g.tableau(s, X0, Y0 + 0.1, 12.4, lignes, largeurs=lw, taille=10.5, hauteur_ligne=0.27, gras_derniere=True)
    g.texte(s, X0, 6.85, 12.4, 0.25, t["base_faible"], taille=9, couleur=g.GRIS, italique=True)
    bandeau(ctx, s, an.s_table(ctx))
    return s


def projets_groupe(ctx, nom_groupe, marques):
    t, d, per = ctx.t, ctx.d, ctx.per
    marques = [m for m in marques if m in d.marques and d.leads_total(per, m) > 0]
    if not marques:
        return None
    s = nouvelle(ctx, f"{t['projets']} — {t[nom_groupe]}", f"{ctx.perimetre} · {ctx.et(per)}", source_bo(ctx), notes=note_definitions(ctx), cle="projets")
    ref = ctx.refs[-1][1] if ctx.refs else None            # n1 en priorité (dernier ajouté)
    larg = 6.1 if ref else 8.9
    def graphique(x, p):
        series = [(t[pj], [d.leads(p, m)[pj] for m in marques], g.COULEURS_PROJETS[pj]) for pj in PROJETS]
        g.texte(s, x, Y0, larg, 0.3, ctx.et(p), taille=13, gras=True, couleur=g.BLEU, align=PP_ALIGN.CENTER)
        g.colonnes(s, x, Y0 + 0.3, larg, 3.0, [ctx.nom(m) for m in marques], series, empile=True, taille=10, fmt=t.nb)
    graphique(X0, ref if ref else per)
    if ref:
        graphique(X0 + larg + 0.2, per)
    lignes = []
    for m in marques:
        c = d.leads(per, m); tc = sum(c.values())
        if tc < 100:
            continue
        taux = t.taux(c["VN"], tc)
        ligne = f"{ctx.nom(m)} : {t.pct(taux, 0)} {t['VN']}"
        if ref:
            r = d.leads(ref, m); tr = sum(r.values())
            if tr >= 100:
                ligne += f" ({t.pts(taux - t.taux(r['VN'], tr))} {libelle_ref(ctx, 'n1' if ref == ctx.per.n1() else 'prec')})"
        lignes.append(ligne)
    g.encadre(s, X0, Y0 + 3.45, 12.4, 0.8, ("Part de leads New cars" if ctx.langue == "fr" else "New cars leads share"), [" · ".join(lignes) or "—"], taille=10)
    bandeau(ctx, s, an.s_projets(ctx, marques))
    return s


def trafic_marque(ctx, m):
    t, d, per = ctx.t, ctx.d, ctx.per
    if d.utilisateurs(per, m) is None and not sum(d.canaux(per, m).values()):
        ctx.avertissements.append(f"{ctx.nom(m)} : aucune donnée de trafic sur la période, diapositive non générée.")
        return None
    s = nouvelle(ctx, f"{ctx.nom(m)} — {t['trafic']} {ctx.et(per)}", ctx.perimetre, source_ga4(ctx),
                 notes=note_definitions(ctx, "Chaîne GA4 comme Looker, calculée sur la période entière : sessions (total GA4) ; In Journey = sessions sur une page formulaire ou lead (page_category « form page » / « lead page ») ; hot leads = évènements tradein_request. CVR = hot leads ÷ sessions. Canaux = Stellantis Custom Channel Group. « Via site marque » = sessions de source UTM Main-Website ou referral depuis l'URL de la marque, ÷ sessions totales."), cle=f"marque:{m}")
    ga = d.utilisateurs(per, m)
    y, h, w = 1.55, 1.25, 2.55
    if ga is None:
        g.tuile(s, X0, y, 3 * w + 1.2, h, t["sessions"], t["non_dispo"], t["ga4_indispo"])
    else:
        refs = [(c, d.utilisateurs(p, m)) for c, p in ctx.refs]
        def det(k):
            out = []
            for c, v in refs:
                out.append(f"{t.evol(ga[k], v[k])[0]} {libelle_ref(ctx, c)}" if v else f"{t['non_dispo']}")
            return "  ·  ".join(out) or None
        g.tuile(s, X0, y, w, h, t["sessions"], t.nb(ga["sessions"]), det("sessions"), taille_valeur=24)
        g.fleche(s, X0 + w + 0.05, y + 0.38, 0.5, 0.3, t.pct(t.taux(ga["in_journey"], ga["sessions"]), 0) if ga["sessions"] else None)
        g.tuile(s, X0 + w + 0.6, y, w, h, t["in_journey"], t.nb(ga["in_journey"]), det("in_journey"), taille_valeur=24)
        g.fleche(s, X0 + 2 * w + 0.65, y + 0.38, 0.5, 0.3, t.pct(t.taux(ga["hot_leads"], ga["in_journey"]), 0) if ga["in_journey"] else None)
        g.tuile(s, X0 + 2 * w + 1.2, y, w, h, t["hot_leads"], t.nb(ga["hot_leads"]), det("hot_leads"), taille_valeur=24)
    # CVR global et part du trafic venant du site de la marque (tuiles étroites : pts vs chaque référence, libellés courts)
    court = {"prec": ("vs préc.", "vs prev."), "n1": ("vs N-1", "vs LY")}
    def det_pts(cur, refs):
        out = []
        for cle, v in refs:
            if v is not None and cur is not None:
                out.append(f"{t.pts(cur - v)} {court[cle][0 if ctx.langue == 'fr' else 1]}")
        return "  ".join(out) or None
    if ga is not None and ga["sessions"] >= 100:
        cvr = ga["hot_leads"] / ga["sessions"] * 100
        refs_cvr = []
        for cle, p in ctx.refs:
            u = d.utilisateurs(p, m)
            refs_cvr.append((cle, (u["hot_leads"] / u["sessions"] * 100) if (u and u["sessions"] >= 100) else None))
        g.tuile(s, X0 + 8.95, y, 1.7, h, "CVR", t.pct(cvr, 1), det_pts(cvr, refs_cvr), taille_valeur=22)
    a_site, b_site = d.trafic_site_marque(per, m)
    if b_site >= 100:
        part = a_site / b_site * 100
        refs_site = []
        for cle, p in ctx.refs:
            a2, b2 = d.trafic_site_marque(p, m)
            refs_site.append((cle, (a2 / b2 * 100) if b2 >= 100 else None))
        g.tuile(s, X0 + 10.75, y, 1.7, h, "Via site marque" if ctx.langue == "fr" else "Via brand site", t.pct(part, 0), det_pts(part, refs_site), taille_valeur=22)
    # canaux : anneau + tableau
    canaux = d.canaux(per, m)
    tot = sum(canaux.values())
    ordre = sorted(canaux, key=lambda c: -canaux[c])
    if tot:
        top = ordre[:7]
        reste = sum(canaux[c] for c in ordre[7:])
        cats = top + ([t["autre"]] if reste else [])
        vals = [canaux[c] for c in top] + ([reste] if reste else [])
        g.texte(s, X0, 3.0, 4.6, 0.3, ("Trafic par canal" if ctx.langue == "fr" else "Traffic by channel"), taille=12, gras=True, couleur=g.BLEU)
        g.anneau(s, X0 - 0.1, 3.25, 5.0, 2.4, cats, vals, taille=9)
        ent = [t["canal"], t["sessions_col"]] + [libelle_ref(ctx, c) for c, _ in ctx.refs]
        lignes = [ent]
        for c in ordre[:7]:
            row = [c, t.nb(canaux[c])]
            for _, p in ctx.refs:
                row.append(t.evol(canaux[c], d.canaux(p, m).get(c, 0))[0])
            lignes.append(row)
        lignes.append([t["total"], t.nb(tot)] + [t.evol(tot, sum(d.canaux(p, m).values()))[0] for _, p in ctx.refs])
        nc = len(ent)
        g.tableau(s, 5.5, 3.1, 7.4, lignes, largeurs=[3.0] + [(7.4 - 3.0) / (nc - 1)] * (nc - 1), taille=10, hauteur_ligne=0.25, gras_derniere=True)
        # commentaire calculé sous le tableau
        phrase = [f"{t['sessions']} : {t.nb(tot)} — {ordre[0]} {t.pct(canaux[ordre[0]] / tot * 100, 0)}"
                  + (f", {ordre[1]} {t.pct(canaux[ordre[1]] / tot * 100, 0)}" if len(ordre) > 1 else "")]
        for cle, p in ctx.refs:
            lc = commentaire_evolutions(ctx, ordre[:6], [canaux[c] for c in ordre[:6]], [d.canaux(p, m).get(c, 0) for c in ordre[:6]], f"({ctx.et(p)})", 2)
            phrase += [x for x in lc if isinstance(x, str)][:2]
        if "analyse" not in ctx.modules:
            g.encadre(s, 5.5, 6.0, 7.4, 0.9, None, phrase[:3], taille=10)
    else:
        g.texte(s, X0, 3.2, 12, 0.5, "Aucun trafic mesuré sur cette période." if ctx.langue == "fr" else "No traffic measured over this period.", taille=13, couleur=g.GRIS)
    bandeau(ctx, s, an.s_trafic(ctx, m))
    return s


def leads_marque(ctx, m):
    t, d, per = ctx.t, ctx.d, ctx.per
    periodes = ctx.periodes
    s = nouvelle(ctx, f"{ctx.nom(m)} — {t['leads']} {ctx.et(per)}", ctx.perimetre, source_bo(ctx), notes=note_definitions(ctx), cle=f"marque:{m}")
    series = [(t[pj], [d.leads(p, m)[pj] for p in periodes], g.COULEURS_PROJETS[pj]) for pj in PROJETS]
    g.colonnes(s, X0, Y0, 6.2, 4.2, [ctx.et(p) for p in periodes], series, empile=True, taille=11, fmt=t.nb)
    tots = [d.leads_total(p, m) for p in periodes]
    lignes = [(f"{t['leads']} {ctx.et(per)} : {t.nb(tots[-1])}", True)]
    for (cle, p), tr in zip(ctx.refs, [d.leads_total(p, m) for _, p in ctx.refs]):
        lignes.append(f"{t.evol(tots[-1], tr)[0]} {libelle_ref(ctx, cle)} ({ctx.et(p)} : {t.nb(tr)})")
    c = d.leads(per, m)
    taux = t.taux(c["VN"], tots[-1])
    if taux is not None:
        l2 = f"{t['taux_nc']} : {t.pct(taux, 0)}"
        for cle, p in ctx.refs:
            r = d.leads(p, m); tr = sum(r.values())
            if tr >= 100 and tots[-1] >= 100:
                l2 += f" ({t.pts(taux - t.taux(r['VN'], tr))} {libelle_ref(ctx, cle)})"
        lignes.append(l2)
    g.encadre(s, 7.0, Y0 + 0.1, 5.9, 4.0, None, lignes, taille=12)
    bandeau(ctx, s, an.s_leads_marque(ctx, m))
    return s


def composition_sources(ctx):
    """Phrase qui détaille ce que contient chaque groupe de sources (les valeurs brutes du back-office regroupées)."""
    from .donnees import GROUPES_SOURCES
    parts = [f"{g} = {', '.join(v)}" for g, v in GROUPES_SOURCES.items()]
    tete = "Regroupement des sources (valeurs brutes du back-office) : " if ctx.langue == "fr" else "Source grouping (raw back-office values): "
    autre = " ; autres valeurs → Autre." if ctx.langue == "fr" else "; any other value → Other."
    return tete + " ; ".join(parts) + autre


def sources_marque(ctx, m):
    t, d, per = ctx.t, ctx.d, ctx.per
    periodes = ctx.periodes
    s = nouvelle(ctx, f"{ctx.nom(m)} — {'Sources d\'acquisition' if ctx.langue == 'fr' else 'Acquisition sources'} {ctx.et(per)}", ctx.perimetre,
                 source_bo(ctx), notes=note_definitions(ctx, "Sources d'acquisition : SOURCE_ACQUISITION du back-office regroupée (voir pipeline/deck/donnees.py)."), cle=f"marque:{m}")
    if not ctx.d.acquisition_disponible(periodes[0]):
        g.texte(s, X0, 2.0, 12, 0.6, t["acq_indispo"], taille=14, couleur=g.GRIS)
        return s
    src = [d.sources(p, m) for p in periodes]
    ent1 = [t["source"]]
    for pj in PROJETS:
        ent1 += [f"{t[pj]}\n{ctx.et(p)}" for p in periodes]
    lignes = [ent1]
    tot_pj = [[sum(sp[sg][pj] for sg in ORDRE_SOURCES) for pj in PROJETS] for sp in src]
    tot_src = lambda sp, sg: sum(sp[sg][pj] for pj in PROJETS)
    for sg in ORDRE_SOURCES:
        row = [sg if sg != "Autre" else t["autre"]]
        if sum(src[-1][sg][pj] for pj in PROJETS) + sum(sum(sp[sg][pj] for pj in PROJETS) for sp in src[:-1]) == 0:
            continue
        for k, pj in enumerate(PROJETS):
            for i, sp in enumerate(src):
                v = sp[sg][pj]; ts = tot_src(sp, sg)       # % = part du projet dans les leads de cette source
                row.append(f"{t.nb(v)} ({t.pct(v / ts * 100, 0)})" if ts else "–")
        lignes.append(row)
    row = [t["total"]]
    for k in range(len(PROJETS)):
        for i in range(len(src)):
            row.append(t.nb(tot_pj[i][k]))
    lignes.append(row)
    nc = len(ent1)
    g.tableau(s, X0, Y0 + 0.1, 12.4, lignes, largeurs=[1.9] + [(12.4 - 1.9) / (nc - 1)] * (nc - 1), taille=9.5, hauteur_ligne=0.34, gras_derniere=True)
    note = ("(%) = part de chaque projet dans les leads de la source. " if ctx.langue == "fr" else "(%) = share of each project in the source's leads. ") + composition_sources(ctx)
    g.texte(s, X0, 6.62, 12.4, 0.5, note, taille=8.5, couleur=g.GRIS, italique=True)
    bandeau(ctx, s, an.s_sources(ctx, m), y=5.35, h=1.2)
    return s


def points_ouverts(ctx):
    for p in ctx.brief.get("pointsOuverts") or []:
        s = nouvelle(ctx, ctx.t["points_ouverts"], p.get("titre") or None)
        if p.get("texte"):
            g.puces(s, X0, Y0, 12.2, 5.0, [l for l in p["texte"].split("\n") if l.strip()], taille=16)


def prochaines_etapes(ctx):
    t = ctx.t
    et = ctx.brief.get("prochainesEtapes") or []
    if not et:
        return None
    s = nouvelle(ctx, t["prochaines_etapes"])
    lignes = [["Item" if ctx.langue == "en" else "Action", t["responsable"], t["statut"], t["echeance"]]]
    for e in et:
        lignes.append([e.get("item", ""), e.get("responsable", ""), t[e.get("statut", "a_faire")], e.get("echeance", "")])
    g.tableau(s, X0, Y0 + 0.1, 12.4, lignes, largeurs=[6.6, 2.4, 1.8, 1.6], taille=12, hauteur_ligne=0.42,
              alignements=[PP_ALIGN.LEFT] * 4)
    return s


def questions(ctx):
    s = nouvelle(ctx, ctx.t["questions"])
    return s


def contacts(ctx):
    s = ctx.prs.slides.add_slide(ctx.lay["1_Title and Content"])
    ctx.n += 1
    s.shapes.title.text = ctx.t["contacts"]
    for ph in list(s.placeholders):
        if ph.placeholder_format.idx == 12:
            ph._element.getparent().remove(ph._element)
    c = ctx.brief.get("contact") or {}
    lignes = [(c.get("nom") or "", {"taille": 26, "gras": True, "couleur": "FFFFFF"}),
              (c.get("fonction") or "", {"taille": 16, "couleur": "FFFFFF"}),
              (c.get("email") or "", {"taille": 16, "couleur": "FFFFFF"})]
    g.texte(s, 1.2, 3.0, 10, 2.5, [l for l in lignes if l[0]], taille=16, couleur="FFFFFF")
    return s


# ------------------------------------------------------------------ analyse / recommandation sur chaque diapositive de résultats
def bandeau(ctx, s, res, y=5.75, h=1.2):
    """Encadrés « Analyse » (bleu) et « Recommandation » (orange) en bas d'une diapositive qui affiche des résultats ; rien si le module est désactivé."""
    if "analyse" not in ctx.modules or not res:
        return
    a, r = res
    fr = ctx.langue == "fr"
    if a:
        g.encadre(s, X0, y, 6.1, h, "Analyse" if fr else "Analysis", a, taille=10.5, couleur=g.BLEU)
    if r:
        g.encadre(s, X0 + 6.3, y, 6.1, h, "Recommandation" if fr else "Recommendation", r, taille=10.5, couleur=g.ORANGE)


# ------------------------------------------------------------------ analyse globale (calculée par règles)
def diapo_analyse(ctx, titre, r):
    """Une diapositive « Analyse » (constats / lectures / recommandations) à partir du résultat des règles (analyse.py)."""
    if not r:
        return None
    fr = ctx.langue == "fr"
    s = nouvelle(ctx, titre, ctx.perimetre, ctx.t["source_bo_ga4"],
                 notes=("Analyse calculée par règles à partir des seuls chiffres de cette présentation ; les causes sont des hypothèses à confirmer. " + note_definitions(ctx)))
    box = s.shapes.add_shape(1, Inches(X0), Inches(1.55), Inches(X1 - X0), Inches(0.75))
    box.fill.solid(); box.fill.fore_color.rgb = g.rgb("1F3F7A"); box.line.fill.background(); box.shadow.inherit = False
    g.texte(s, X0 + 0.2, 1.58, X1 - X0 - 0.4, 0.7, r.get("message") or "", taille=15, gras=True, couleur="FFFFFF", ancre=MSO_ANCHOR.MIDDLE)
    cols = [("Ce que disent les chiffres" if fr else "What the numbers say", r["constats"]),
            ("Lecture et points d'attention" if fr else "Reading and watch points", r["lectures"])]
    x = X0
    for (tit, lignes), w in zip(cols, (6.4, 6.05)):
        if lignes:
            g.encadre(s, x, 2.5, w - 0.25, 4.5, tit, lignes, taille=12)
        x += w
    if r.get("historique") or r.get("recommandations"):
        s2 = nouvelle(ctx, titre + (" (suite)" if fr else " (continued)"), ctx.perimetre, ctx.t["source_bo_ga4"],
                      notes=("Contexte historique : mêmes périodes des années passées (leads BO depuis 2020, GA4 depuis 2022), 12 mois glissants, Search Console, V2. " + note_definitions(ctx)))
        cols2 = [("Contexte et historique" if fr else "Context and history", r.get("historique") or []),
                 ("Recommandations" if fr else "Recommendations", r["recommandations"])]
        x = X0
        for (tit, lignes), w in zip(cols2, (7.0, 5.45)):
            if lignes:
                g.encadre(s2, x, 1.6, w - 0.25, 5.3, tit, lignes, taille=12.5)
            x += w
    return s


# ------------------------------------------------------------------ slides au design des decks de référence : YTD, SEO, marché, objectifs
def _mois_ecoules(ctx):
    """Nombre de mois écoulés de l'année de la période : jusqu'à la fin de la période, plafonné au dernier jour de leads connu (le mois entamé n'est pas compté)."""
    import calendar
    n = ctx.per.fin.month
    dj = ctx.d.dernier_jour_leads()
    if dj and dj < ctx.per.fin.isoformat():
        a, mo = int(dj[:4]), int(dj[5:7])
        n = (mo if int(dj[8:10]) == calendar.monthrange(a, mo)[1] else mo - 1) if a == ctx.per.annee else (0 if a < ctx.per.annee else n)
    return max(0, n)


def ytd_marque(ctx, m):
    """Tendance annuelle des leads de la marque (« YTD Leads Trends ») : mois de l'année en cours face à l'année précédente, total et New cars."""
    t, d, per = ctx.t, ctx.d, ctx.per
    fr = ctx.langue == "fr"
    an, n = per.annee, _mois_ecoules(ctx)
    cur, prev = d.leads_mensuels(an, m), d.leads_mensuels(an - 1, m)
    cur_vn, prev_vn = d.leads_mensuels(an, m, "VN"), d.leads_mensuels(an - 1, m, "VN")
    if n < 1 or sum(cur[:n]) + sum(prev[:n]) == 0:
        return None
    mois = MOIS_COURTS[ctx.langue]
    ytd, ytd_p, vn, vn_p = sum(cur[:n]), sum(prev[:n]), sum(cur_vn[:n]), sum(prev_vn[:n])
    ev = t.evol(ytd, ytd_p)[0]
    nom = ctx.nom(m)
    pad = lambda v: [x if i < n else None for i, x in enumerate(v)]
    puces = [
        f"{t.nb(ytd)} leads cumulés en {an}, {ev} vs la même période {an - 1} ({t.nb(ytd_p)})." if fr else
        f"{t.nb(ytd)} leads year to date in {an}, {ev} vs the same months of {an - 1} ({t.nb(ytd_p)}).",
        f"New cars : {t.nb(vn)} leads, soit {t.pct(t.taux(vn, ytd) or 0, 0)} du total ({t.evol(vn, vn_p)[0]} vs {an - 1})." if fr else
        f"New cars: {t.nb(vn)} leads, {t.pct(t.taux(vn, ytd) or 0, 0)} of the total ({t.evol(vn, vn_p)[0]} vs {an - 1}).",
    ]
    mx = max(range(n), key=lambda i: cur[i])
    puces.append(f"Meilleur mois {an} : {mois[mx]} ({t.nb(cur[mx])})." if fr else f"Best month of {an}: {mois[mx]} ({t.nb(cur[mx])}).")
    puces.append(f"Dernier mois ({mois[n - 1]}) : {t.evol(cur[n - 1], prev[n - 1])[0]} vs {mois[n - 1]} {an - 1}." if fr else
                 f"Latest month ({mois[n - 1]}): {t.evol(cur[n - 1], prev[n - 1])[0]} vs {mois[n - 1]} {an - 1}.")
    s = nouvelle_ref(ctx, f"{nom} — " + ("Tendance des leads sur l'année" if fr else "YTD leads trends"),
                     f"{nom} : {t.nb(ytd)} leads cumulés en {an}, {ev} vs {an - 1}" if fr else f"{nom}: {t.nb(ytd)} leads year to date in {an}, {ev} vs {an - 1}",
                     source=source_bo(ctx), puces=puces, notes=note_definitions(ctx, "Leads valides par mois ; année en cours limitée aux mois écoulés."), cle=f"marque:{m}")
    g.lignes_chart(s, X0_REF, 1.55, X1_REF - X0_REF, 5.4, mois, [
        (f"{t['leads']} {an}", pad(cur), g.TITRE_REF, True), (f"{t['leads']} {an - 1}", prev, "9DB2D6", False),
        (f"{t['leads_nc']} {an}", pad(cur_vn), "F28E2B", True), (f"{t['leads_nc']} {an - 1}", prev_vn, "F5C88F", False)], taille=10)
    return s


def _ctr(c, i):
    return c / i * 100 if i else 0


def seo_vue(ctx):
    """SEO — vue d'ensemble Search Console par marque : clics, impressions, CTR, position, évolution des clics."""
    t, d, per = ctx.t, ctx.d, ctx.per
    fr = ctx.langue == "fr"
    lignes_m = []
    for m in d.marques:
        cur = d.gsc(per, m)
        if cur:
            lignes_m.append((m, cur, [(cle, d.gsc(p, m)) for cle, p in ctx.refs]))
    if not lignes_m:
        return None
    lignes_m.sort(key=lambda x: -x[1][0])
    tc, ti = sum(x[1][0] for x in lignes_m), sum(x[1][1] for x in lignes_m)
    tp = sum(x[1][2] * x[1][1] for x in lignes_m) / ti if ti else 0
    refs_tot = []
    for j, (cle, p) in enumerate(ctx.refs):
        pr = [r[j][1] for _, _, r in lignes_m if r[j][1]]
        refs_tot.append((cle, sum(x[0] for x in pr) if len(pr) == len(lignes_m) else None))
    ent = [t["marque"], "Clics" if fr else "Clicks", "Impressions", "CTR", "Position moy." if fr else "Avg. position"] + \
          [(f"Clics {libelle_ref(ctx, cle)}" if fr else f"Clicks {libelle_ref(ctx, cle)}") for cle, _ in ctx.refs]
    lignes = [ent]
    for m, (c, i, pos), refs in lignes_m:
        lignes.append([ctx.nom(m), t.nb(c), t.nb(i), t.pct(_ctr(c, i), 1), t.dec(pos, 1)] + [(t.evol(c, r[1][0] if r[1] else None)[0]) for r in refs])
    lignes.append([t["total"], t.nb(tc), t.nb(ti), t.pct(_ctr(tc, ti), 1), t.dec(tp, 1)] + [t.evol(tc, rt)[0] for _, rt in refs_tot])
    ref0 = libelle_ref(ctx, ctx.refs[0][0]) if ctx.refs else ""
    ev0 = t.evol(tc, refs_tot[0][1])[0] if refs_tot else ""
    puces = []
    if refs_tot and len(lignes_m) >= 2:
        mv = [(m, t.evol(c[0], r[0][1][0] if r[0][1] else None)) for m, c, r in lignes_m if c[0] >= 100]
        mv = [(m, e) for m, e in mv if e[2] is not None]
        if mv:
            hi, lo = max(mv, key=lambda x: x[1][2]), min(mv, key=lambda x: x[1][2])
            puces.append(f"{ctx.nom(hi[0])} : {hi[1][0]} de clics {ref0}, la plus forte hausse." if fr else f"{ctx.nom(hi[0])}: {hi[1][0]} clicks {ref0}, the largest increase.")
            if lo[1][2] < 0 and lo[0] != hi[0]:
                puces.append(f"{ctx.nom(lo[0])} : {lo[1][0]} de clics {ref0}, la plus forte baisse." if fr else f"{ctx.nom(lo[0])}: {lo[1][0]} clicks {ref0}, the largest decrease.")
    puces.append(f"CTR moyen : {t.pct(_ctr(tc, ti), 1)} ; position moyenne : {t.dec(tp, 1)}." if fr else f"Average CTR: {t.pct(_ctr(tc, ti), 1)}; average position: {t.dec(tp, 1)}.")
    msg = (f"Recherche naturelle : {t.nb(tc)} clics sur {ctx.et(per)}, {ev0} {ref0} ; position moyenne {t.dec(tp, 1)}." if fr else
           f"Organic search: {t.nb(tc)} clicks in {ctx.et(per)}, {ev0} {ref0}; average position {t.dec(tp, 1)}.") if ref0 else \
          (f"Recherche naturelle : {t.nb(tc)} clics sur {ctx.et(per)} ; position moyenne {t.dec(tp, 1)}." if fr else
           f"Organic search: {t.nb(tc)} clicks in {ctx.et(per)}; average position {t.dec(tp, 1)}.")
    s = nouvelle_ref(ctx, "SEO — vue d'ensemble Search Console" if fr else "SEO — Search Console overview", msg, source="Source : Google Search Console" if fr else "Source: Google Search Console",
                     puces=puces, notes="Clics, impressions et position moyenne (pondérée par les impressions) des sites de reprise, Google Search Console. Les marques sans historique couvrant la période ne sont pas affichées.",
                     cle="seo_vue")
    nc = len(ent)
    g.tableau(s, X0_REF, 1.6, X1_REF - X0_REF, lignes, largeurs=[2.0] + [(X1_REF - X0_REF - 2.0) / (nc - 1)] * (nc - 1), taille=(11 if len(lignes) <= 9 else 10),
              hauteur_ligne=min(0.42, 5.2 / len(lignes)), gras_derniere=True)
    return s


def seo_marque(ctx, m):
    """SEO de la marque : clics mensuels de l'année face à N-1 (Search Console) et principales requêtes de la période."""
    t, d, per = ctx.t, ctx.d, ctx.per
    fr = ctx.langue == "fr"
    cur = d.gsc(per, m)
    requetes = d.gsc_requetes(per, m)
    if not cur and not requetes:
        return None
    an = per.annee
    mois = MOIS_COURTS[ctx.langue]
    serie = lambda a: [(x[0] if x else None) for x in d.gsc_mensuel(a, m)]       # None : mois non couvert par l'historique (pas de barre, pas d'étiquette « 0 »)
    nom = ctx.nom(m)
    puces = []
    if cur:
        c, i, pos = cur
        for cle, p in ctx.refs:
            r = d.gsc(p, m)
            puces.append(f"{t.nb(c)} clics sur {ctx.et(per)} ({t.evol(c, r[0] if r else None)[0]} {libelle_ref(ctx, cle)})." if fr else
                         f"{t.nb(c)} clicks in {ctx.et(per)} ({t.evol(c, r[0] if r else None)[0]} {libelle_ref(ctx, cle)}).")
        puces.append(f"{t.nb(i)} impressions, CTR {t.pct(_ctr(c, i), 1)}." if fr else f"{t.nb(i)} impressions, CTR {t.pct(_ctr(c, i), 1)}.")
        puces.append(f"Position moyenne : {t.dec(pos, 1)}." if fr else f"Average position: {t.dec(pos, 1)}.")
    if requetes:
        puces.append(f"Requête n°1 : « {requetes[0][0]} » ({t.nb(requetes[0][1])} clics)." if fr else f"Top query: “{requetes[0][0]}” ({t.nb(requetes[0][1])} clicks).")
    r0 = d.gsc(ctx.refs[0][1], m) if (cur and ctx.refs) else None
    lib0 = libelle_ref(ctx, ctx.refs[0][0]) if ctx.refs else ""
    if cur and r0 and lib0:
        msg = f"{nom} : {t.nb(cur[0])} clics organiques sur {ctx.et(per)}, {t.evol(cur[0], r0[0])[0]} {lib0}" if fr else \
              f"{nom}: {t.nb(cur[0])} organic clicks in {ctx.et(per)}, {t.evol(cur[0], r0[0])[0]} {lib0}"
    elif cur:
        msg = f"{nom} : {t.nb(cur[0])} clics organiques sur {ctx.et(per)}" if fr else f"{nom}: {t.nb(cur[0])} organic clicks in {ctx.et(per)}"
    else:
        msg = f"{nom} : principales requêtes sur {ctx.et(per)}" if fr else f"{nom}: top queries in {ctx.et(per)}"
    s = nouvelle_ref(ctx, f"{nom} — {'Performance SEO' if fr else 'SEO performance'} {ctx.et(per)}", msg, source="Source : Google Search Console" if fr else "Source: Google Search Console",
                     puces=puces, notes="Clics mensuels (Search Console, historique de 16 mois) et principales requêtes des mois de la période.", cle=f"marque:{m}")
    y = 1.55
    if any(v for v in serie(an)) or any(v for v in serie(an - 1)):
        g.colonnes(s, X0_REF, y, X1_REF - X0_REF, 2.45, mois, [((f"Clics {an - 1}" if fr else f"Clicks {an - 1}"), serie(an - 1), "9DB2D6"),
                   ((f"Clics {an}" if fr else f"Clicks {an}"), serie(an), g.TITRE_REF)], taille=9, fmt=t.nb)
        y += 2.6
    if requetes:
        ent = ["Requête" if fr else "Query", "Clics" if fr else "Clicks", "Impressions", "CTR", "Position"]
        lignes = [ent] + [[q[:46], t.nb(c), t.nb(i), t.pct(_ctr(c, i), 1), t.dec(pos, 1)] for q, c, i, pos in requetes[:7]]
        g.tableau(s, X0_REF, y, X1_REF - X0_REF, lignes, largeurs=[4.3, 1.2, 1.5, 1.2, 1.4], taille=10, hauteur_ligne=0.3)
    return s


def marche_pays(ctx, pays):
    """Leads New cars autobiz face au marché (immatriculations AAA Data / sources officielles) : croissance annuelle et leads pour 1 000 immatriculations."""
    t, per = ctx.t, ctx.per
    fr = ctx.langue == "fr"
    mk = ctx.d.marche_mensuel(pays)
    cles = [(a, mo) for a, mo in per.mois() if f"{a}-{mo:02d}" in mk]
    if not cles:
        return None
    dd = Donnees([pays], ctx.brief["perimetre"].get("marques") or None, hist=ctx.d.hist)
    mois = MOIS_COURTS[ctx.langue]
    lignes = [["Mois" if fr else "Month", "Immatriculations" if fr else "Registrations", "Marché vs N-1" if fr else "Market vs last year", "Leads New cars" if fr else "New-car leads",
               "Leads vs N-1" if fr else "Leads vs last year", "Leads / 1 000 immat." if fr else "Leads / 1,000 reg."]]
    cat, s_mk, s_ld, ratios = [], [], [], []
    for a, mo in cles:
        e = mk[f"{a}-{mo:02d}"]
        ld = dd.leads_mensuels(a, None, "VN")[mo - 1]
        ld_p = dd.leads_mensuels(a - 1, None, "VN")[mo - 1]
        ev_l = t.evol(ld, ld_p)
        ratio = ld / e["total"] * 1000
        ratios.append(ratio)
        yoy = e.get("yoy_pct")
        lignes.append([f"{mois[mo - 1]} {a}", t.nb(e["total"]), t.pct(yoy, 1, signe=True) if yoy is not None else "–", t.nb(ld), ev_l[0], t.dec(ratio, 1)])
        cat.append(f"{mois[mo - 1]} {a}")
        s_mk.append(yoy if yoy is not None else 0)
        s_ld.append(round(ev_l[2], 1) if ev_l[2] is not None else 0)
    a, mo = cles[-1]
    e = mk[f"{a}-{mo:02d}"]
    ld = dd.leads_mensuels(a, None, "VN")[mo - 1]
    ld_p = dd.leads_mensuels(a - 1, None, "VN")[mo - 1]
    ev_l = t.evol(ld, ld_p)
    yoy = e.get("yoy_pct")
    src = (e.get("source_url") or "").split("/")[2] if (e.get("source_url") or "").count("/") >= 2 else ""
    puces = [f"Marché : {t.nb(e['total'])} immatriculations en {mois[mo - 1]} {a}, {t.pct(yoy, 1, signe=True)} vs N-1." if fr else
             f"Market: {t.nb(e['total'])} registrations in {mois[mo - 1]} {a}, {t.pct(yoy, 1, signe=True)} vs last year."] if yoy is not None else []
    puces.append(f"Leads New cars : {t.nb(ld)}, {ev_l[0]} vs N-1." if fr else f"New-car leads: {t.nb(ld)}, {ev_l[0]} vs last year.")
    if yoy is not None and ev_l[2] is not None:
        gain = ev_l[2] - yoy
        if gain >= 0:
            puces.append(f"Les leads New cars progressent plus vite que le marché ({t.pts(gain)})." if fr else f"New-car leads grew faster than the market ({t.pts(gain)}).")
        else:
            puces.append(f"Les leads New cars progressent moins vite que le marché ({t.pts(gain)})." if fr else f"New-car leads grew slower than the market ({t.pts(gain)}).")
    puces.append(f"{t.dec(ratios[-1], 1)} leads pour 1 000 immatriculations." if fr else f"{t.dec(ratios[-1], 1)} leads per 1,000 registrations.")
    if src:
        puces.append(f"Immatriculations : {src}." if fr else f"Registrations: {src}.")
    msg = (f"{pays} : marché {t.pct(yoy, 1, signe=True)} en {mois[mo - 1]} {a}, leads New cars {ev_l[0]}" if fr else
           f"{pays}: market {t.pct(yoy, 1, signe=True)} in {mois[mo - 1]} {a}, New-car leads {ev_l[0]}") if yoy is not None else \
          (f"{pays} : {t.nb(e['total'])} immatriculations en {mois[mo - 1]} {a}" if fr else f"{pays}: {t.nb(e['total'])} registrations in {mois[mo - 1]} {a}")
    s = nouvelle_ref(ctx, f"{pays} — {'Leads vs marché' if fr else 'Leads vs market'}", msg,
                     source=("Sources : back-office autobiz et immatriculations (AAA Data, ACEA, sources officielles)" if fr else "Sources: autobiz back-office and registrations (AAA Data, ACEA, official sources)"),
                     puces=puces, notes="Immatriculations de voitures neuves (market.json, relevés publiés) face aux leads New cars du back-office autobiz sur les mois couverts.", cle="marche")
    g.colonnes(s, X0_REF, 1.55, X1_REF - X0_REF, 2.9, cat, [("Marché (% vs N-1)" if fr else "Market (% vs last year)", s_mk, "9DB2D6"),
               ("Leads New cars (% vs N-1)" if fr else "New-car leads (% vs last year)", s_ld, g.TITRE_REF)], taille=9, format_nombre="0.0")
    g.tableau(s, X0_REF, 4.6, X1_REF - X0_REF, lignes, largeurs=[1.5, 1.8, 1.7, 1.5, 1.6, 1.5], taille=10, hauteur_ligne=min(0.34, 2.3 / len(lignes)))
    return s


def objectifs_vue(ctx):
    """Objectifs de leads de l'année (saisis dans le dashboard) face au réalisé, à l'attendu à date (saisonnalité N-1) et à la projection, par marque."""
    t, d, per = ctx.t, ctx.d, ctx.per
    fr = ctx.langue == "fr"
    an, n = per.annee, _mois_ecoules(ctx)
    cibles = d.objectifs(an)
    cibles = {m: v for m, v in cibles.items() if m in d.marques}
    if not cibles or n < 1:
        return None
    lignes_m, tot = [], [0, 0, 0.0, 0.0]
    for m in sorted(cibles, key=lambda x: -cibles[x]):
        cur, prev = d.leads_mensuels(an, m), d.leads_mensuels(an - 1, m)
        ytd = sum(cur[:n])
        part = sum(prev[:n]) / sum(prev) if sum(prev) else n / 12      # part de l'année N-1 écoulée à la même date
        att = cibles[m] * part
        proj = ytd / part if part else None
        lignes_m.append((m, cibles[m], ytd, att, proj))
        tot = [tot[0] + cibles[m], tot[1] + ytd, tot[2] + att, tot[3] + (proj or 0)]
    ent = [t["marque"], f"Objectif {an}" if fr else f"Target {an}", "Cumul" if fr else "Year to date", "Attendu à date" if fr else "Expected to date", "vs attendu" if fr else "vs expected",
           "Projection" if fr else "Projection", "% de l'objectif" if fr else "% of target"]
    ligne = lambda nom, c, y, a, p: [nom, t.nb(c), t.nb(y), t.nb(a), t.pct((y / a - 1) * 100, 0, signe=True) if a else "–", t.nb(p) if p else "–", t.pct(p / c * 100, 0) if (p and c) else "–"]
    lignes = [ent] + [ligne(ctx.nom(m), c, y, a, p) for m, c, y, a, p in lignes_m] + [ligne(t["total"], *tot)]
    pp = t.pct(tot[3] / tot[0] * 100, 0) if tot[0] else "–"
    puces = [f"Projection de fin d'année : {t.nb(tot[3])} leads ({pp} de l'objectif)." if fr else f"Year-end projection: {t.nb(tot[3])} leads ({pp} of the target)."]
    ecarts = [(m, y / a - 1) for m, c, y, a, p in lignes_m if a >= 100]
    if ecarts:
        hi, lo = max(ecarts, key=lambda x: x[1]), min(ecarts, key=lambda x: x[1])
        puces.append(f"{ctx.nom(hi[0])} : {t.pct(hi[1] * 100, 0, signe=True)} vs l'attendu à date, la plus en avance." if fr else
                     f"{ctx.nom(hi[0])}: {t.pct(hi[1] * 100, 0, signe=True)} vs expected to date, the furthest ahead.")
        if lo[0] != hi[0] and lo[1] < 0:
            puces.append(f"{ctx.nom(lo[0])} : {t.pct(lo[1] * 100, 0, signe=True)} vs l'attendu à date, la plus en retard." if fr else
                         f"{ctx.nom(lo[0])}: {t.pct(lo[1] * 100, 0, signe=True)} vs expected to date, the furthest behind.")
    puces.append("Attendu à date = objectif × saisonnalité de l'année précédente." if fr else "Expected to date = target × last year's seasonality.")
    msg = (f"{t.nb(tot[1])} leads cumulés pour un objectif annuel de {t.nb(tot[0])} : {t.pct(tot[1] / tot[0] * 100, 0)} atteint, projection {t.nb(tot[3])} ({pp})." if fr else
           f"{t.nb(tot[1])} leads year to date against an annual target of {t.nb(tot[0])}: {t.pct(tot[1] / tot[0] * 100, 0)} reached, projection {t.nb(tot[3])} ({pp}).")
    s = nouvelle_ref(ctx, f"Objectifs {an}" if fr else f"Objectives {an}", msg, source=source_bo(ctx), puces=puces, cle="objectifs",
                     notes="Objectifs annuels de leads par site (dashboard, GA4 > Pilotage > Objectifs), additionnés par marque. Attendu à date : objectif x part de l'année N-1 écoulée à la même date ; projection : cumul / cette part.")
    nc = len(ent)
    g.tableau(s, X0_REF, 1.6, X1_REF - X0_REF, lignes, largeurs=[2.2] + [(X1_REF - X0_REF - 2.2) / (nc - 1)] * (nc - 1), taille=(11 if len(lignes) <= 9 else 10),
              hauteur_ligne=min(0.42, 5.2 / len(lignes)), gras_derniere=True)
    return s


# ------------------------------------------------------------------ assemblage
def construit(brief, donnees, sortie, gabarit=GABARIT):
    if brief.get("format") == "revue_fr":          # format « revue mensuelle France » : reproduit le deck de référence (revue_fr.py)
        from .revue_fr import construit_revue
        return construit_revue(brief, donnees, sortie, gabarit)
    if brief.get("format") == "revue_trim":        # format « revue trimestrielle pays » : reproduit le deck de référence BE Q3-2026 (revue_trim.py)
        from .revue_trim import construit_revue_trim
        return construit_revue_trim(brief, donnees, sortie, gabarit)
    ctx = Ctx(brief, donnees, gabarit)
    m = ctx.modules
    avoir_global = "global" in m
    avoir_projets = "projets" in m
    avoir_marques = bool(m & {"trafic_marque", "sources", "cta", "conquete", "ytd"})
    d, per = ctx.d, ctx.per
    # modules à données optionnelles : la section n'est créée que si les données existent (sinon avertissement, jamais de diapositive vide)
    avoir_crm = "crm" in m and bool(d._c1st()) and bool({d.PAYS_C1ST.get(p, p) for p in d.pays} & {"FR", "BE", "ES", "PT", "IT", "DE", "PL", "AT", "GB"})
    if "crm" in m and not avoir_crm:
        ctx.avertissements.append("Module C1ST sélectionné mais aucun marché du périmètre n'est suivi par C1ST (ou fichier c1st/kpi.json absent) : section non générée.")
    avoir_seo = "seo" in m and any(d.gsc(per, mq) or d.gsc_requetes(per, mq, 1) for mq in d.marques)
    if "seo" in m and not avoir_seo:
        ctx.avertissements.append("Module SEO sélectionné mais aucune donnée Search Console ne couvre la période : section non générée.")
    pays_marche = [p for p in dict.fromkeys(x.upper() for x in brief["perimetre"]["pays"]) if "marche" in m and any(f"{a}-{mo:02d}" in d.marche_mensuel(p) for a, mo in per.mois())]
    if "marche" in m and not pays_marche:
        ctx.avertissements.append("Module marché sélectionné mais aucun marché du périmètre n'a d'immatriculations sur la période : section non générée.")
    avoir_obj = "objectifs" in m and bool({k for k in d.objectifs(per.annee) if k in d.marques}) and _mois_ecoules(ctx) > 0
    if "objectifs" in m and not avoir_obj:
        ctx.avertissements.append("Module objectifs sélectionné mais aucun objectif de leads n'est saisi pour cette année (dashboard, GA4 > Pilotage > Objectifs) : section non générée.")
    sections = []
    if avoir_global or avoir_projets:
        sections.append(("global", ctx.t["vue_globale"]))
    if avoir_crm:
        sections.append(("sales", ctx.t["sales_performance"]))
    if avoir_marques:
        sections.append(("marques", ctx.t["detail_marques"]))
    if avoir_seo:
        sections.append(("seo", ctx.t["visibilite_seo"]))
    if pays_marche:
        sections.append(("marche", ctx.t["contexte_marche"]))
    if avoir_obj:
        sections.append(("objectifs", ctx.t["objectifs"]))
    if "points_ouverts" in m and (brief.get("pointsOuverts") or []):
        sections.append(("points", ctx.t["points_ouverts"]))
    if "prochaines_etapes" in m and (brief.get("prochainesEtapes") or []):
        sections.append(("etapes", ctx.t["prochaines_etapes"]))
    if m & {"nps", "utm"}:
        sections.append(("annexes", ctx.t["annexes"]))
    sections.append(("qa", ctx.t["questions"]))

    couverture(ctx)
    sommaire(ctx, sections, sections[0][0])
    if avoir_global:
        synthese(ctx)
        vue_groupes(ctx)
        for cle, ref in ctx.refs:
            leads_par_marque(ctx, cle, ref)
        leads_mensuels(ctx)
        leads_mensuels(ctx, "VN")
        projection_mois(ctx)
        classement_marches(ctx)
        entree_vehicule(ctx)
        vue_ensemble_table(ctx)
        apercu_marques(ctx)
    if avoir_crm:
        sommaire(ctx, sections, "sales")
        c1st = [c1st_lead_management(ctx), c1st_conversion(ctx), c1st_ventes_additionnelles(ctx)]
        if all(x is None for x in c1st):
            ctx.avertissements.append("Données C1ST absentes pour cette période (collecte c1st.yml à vérifier) : diapositives C1ST non générées.")
    if avoir_projets:
        for nom_g, ms in (("xp", GROUPES_MARQUES["XP"]), ("xf", GROUPES_MARQUES["XF"])):
            projets_groupe(ctx, nom_g, ms)
        autres = [x for x in ctx.d.marques if x not in GROUPES_MARQUES["XP"] + GROUPES_MARQUES["XF"]]
        if autres:
            projets_groupe(ctx, "autres", autres)
    if "analyse" in m and (avoir_global or avoir_projets):
        diapo_analyse(ctx, "Analyse — vue d'ensemble" if ctx.langue == "fr" else "Analysis — overview", an.globale(ctx))
    if avoir_marques:
        sommaire(ctx, sections, "marques")
        for marque in ctx.d.marques:
            if ctx.d.leads_total(ctx.per, marque) + sum(ctx.d.canaux(ctx.per, marque).values()) == 0:
                continue
            if "trafic_marque" in m:
                trafic_marque(ctx, marque)
                leads_marque(ctx, marque)
                v2_marque(ctx, marque)
            if "ytd" in m:
                ytd_marque(ctx, marque)
            if "sources" in m:
                sources_marque(ctx, marque)
            if "cta" in m:
                cta_marque(ctx, marque)
            if "conquete" in m and marque not in ("SPOTICAR", "STELLANTIS &YOU"):
                conquete_marque(ctx, marque)
    if avoir_seo:
        sommaire(ctx, sections, "seo")
        seo_vue(ctx)
        for marque in ctx.d.marques:
            seo_marque(ctx, marque)
    if pays_marche:
        sommaire(ctx, sections, "marche")
        for p in pays_marche:
            marche_pays(ctx, p)
    if avoir_obj:
        sommaire(ctx, sections, "objectifs")
        objectifs_vue(ctx)
    if "points_ouverts" in m and (brief.get("pointsOuverts") or []):
        sommaire(ctx, sections, "points")
        points_ouverts(ctx)
    if "prochaines_etapes" in m and (brief.get("prochainesEtapes") or []):
        sommaire(ctx, sections, "etapes")
        prochaines_etapes(ctx)
    if m & {"nps", "utm"}:
        sommaire(ctx, sections, "annexes")
        for nom in ("nps", "utm"):
            if nom in m:
                blocs_fixes(ctx, nom)
    sommaire(ctx, sections, "qa")
    questions(ctx)
    contacts(ctx)
    from .traductions import traduit_deck
    traduit_deck(ctx.prs, ctx.langue)
    Path(sortie).parent.mkdir(parents=True, exist_ok=True)
    g.tient_dans_la_diapo(ctx.prs)
    ctx.prs.save(str(sortie))
    return ctx
