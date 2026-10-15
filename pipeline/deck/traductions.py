"""Traduction des textes anglais des diapositives récentes (italien, espagnol, allemand), appliquée au deck terminé.

Les textes du générateur n'existent qu'en français et en anglais ; pour it / es / de, ce module remplace, paragraphe par paragraphe, les libellés et
phrases anglais connus par leur traduction (les chiffres, marques et périodes, déjà dans la langue du deck, sont conservés). Il traduit aussi
les noms d'étapes du tunnel (qui viennent des données, en français) vers l'anglais et les trois autres langues.

Ajouter un texte anglais dans le générateur sans l'ajouter ici est détecté par tests/py/test_deck.py (test de couverture).
"""

import re

LANGUES = ("it", "es", "de")

# ------------------------------------------------------------------ libellés exacts : anglais -> (it, es, de)
LIBELLES = {
    "Source: C1ST (CRM Analytics)": ("Fonte: C1ST (CRM Analytics)", "Fuente: C1ST (CRM Analytics)", "Quelle: C1ST (CRM Analytics)"),
    "Scope: VN leads sent as seen by C1ST (type 1, VN activity, Autobiz campaign); C1ST's own scope, not comparable with the back-office.": (
        "Perimetro: lead VN inviati visti da C1ST (tipo 1, attività VN, campagna Autobiz); perimetro proprio di C1ST, non confrontabile con il back-office.",
        "Perímetro: leads VN enviados vistos por C1ST (tipo 1, actividad VN, campaña Autobiz); perímetro propio de C1ST, no comparable con el back-office.",
        "Perimeter: von C1ST erfasste gesendete VN-Leads (Typ 1, Aktivität VN, Autobiz-Kampagne); eigener C1ST-Perimeter, nicht mit dem Back-Office vergleichbar."),
    "Lead trend & NC share": ("Andamento dei lead e quota auto nuove", "Evolución de leads y cuota de coches nuevos", "Lead-Entwicklung & Neuwagenanteil"),
    "Drivers of increase / decrease": ("Fattori di aumento / calo", "Factores de aumento / descenso", "Treiber von Anstieg / Rückgang"),
    "Recommended actions": ("Azioni raccomandate", "Acciones recomendadas", "Empfohlene Maßnahmen"),
    "Reading": ("Lettura", "Lectura", "Einordnung"),
    "Placement": ("Posizione", "Ubicación", "Platzierung"),
    "Customer origin": ("Origine dei clienti", "Origen de los clientes", "Herkunft der Kunden"),
    "Top trade-in brands": ("Principali marchi permutati", "Principales marcas entregadas", "Wichtigste Inzahlungnahme-Marken"),
    "Rank": ("Pos.", "Puesto", "Rang"),
    "Market": ("Mercato", "Mercado", "Markt"),
    "YTD share": ("Quota cumulata", "Cuota acumulada", "Anteil kumuliert"),
    "With plate": ("Con targa", "Con matrícula", "Mit Kennzeichen"),
    "Make / model": ("Marca / modello", "Marca / modelo", "Marke / Modell"),
    "Plate share": ("Quota con targa", "Cuota con matrícula", "Anteil mit Kennzeichen"),
    "Step": ("Fase", "Etapa", "Schritt"),
    "Before": ("Prima", "Antes", "Vorher"),
    "After": ("Dopo", "Después", "Nachher"),
    "% of homepage": ("% homepage", "% de la página de inicio", "% der Startseite"),
    "Change": ("Variazione", "Variación", "Veränderung"),
    "End-to-end completion": ("Completamento end-to-end", "Finalización de extremo a extremo", "End-to-End-Abschluss"),
    "End-of-month projection": ("Proiezione fine mese", "Proyección fin de mes", "Prognose Monatsende"),
    "Customers sent": ("Clienti inviati", "Clientes enviados", "Gesendete Kunden"),
    "Contacted": ("Contattati", "Contactados", "Kontaktiert"),
    "Contacted on time": ("Contattati nei tempi", "Contactados a tiempo", "Fristgerecht kontaktiert"),
    "1st call on time": ("1ª chiamata nei tempi", "1.ª llamada a tiempo", "Erstanruf fristgerecht"),
    "Treated": ("Trattati", "Tratados", "Bearbeitet"),
    "Not treated": ("Non trattati", "No tratados", "Nicht bearbeitet"),
    "Unique customers": ("Clienti unici", "Clientes únicos", "Eindeutige Kunden"),
    "With opportunity": ("Con opportunità", "Con oportunidad", "Mit Opportunity"),
    "With quote": ("Con preventivo", "Con presupuesto", "Mit Angebot"),
    "NSC orders": ("Ordini NSC", "Pedidos NSC", "NSC-Bestellungen"),
    "Orders": ("Ordini", "Pedidos", "Bestellungen"),
    "Order rate": ("Tasso di ordine", "Tasa de pedido", "Bestellquote"),
    "Low lead volume: no reliable reading.": ("Volume di lead basso: nessuna lettura affidabile.", "Volumen de leads bajo: lectura no fiable.", "Geringes Lead-Volumen: keine verlässliche Aussage möglich."),
    "Increase visibility (display / search).": ("Aumentare la visibilità (display / search).", "Aumentar la visibilidad (display / search).", "Sichtbarkeit erhöhen (Display / Search)."),
    "Target New cars more (dedicated display campaigns)": ("Puntare di più sulle auto nuove (campagne display dedicate)", "Orientarse más a coches nuevos (campañas display específicas)", "Neuwagen stärker adressieren (dedizierte Display-Kampagnen)"),
    "No notable change in channels or New cars share.": ("Nessuna variazione rilevante nei canali o nella quota di auto nuove.", "Sin cambios relevantes en los canales ni en la cuota de coches nuevos.", "Keine nennenswerte Veränderung bei Kanälen oder Neuwagenanteil."),
    "Maintain acquisition efforts.": ("Mantenere gli sforzi di acquisizione.", "Mantener los esfuerzos de adquisición.", "Akquisitionsaktivitäten beibehalten."),
    "Strengthen display": ("Rafforzare il display", "Reforzar el display", "Display verstärken"),
    "Strengthen search (SEA)": ("Rafforzare il search (SEA)", "Reforzar el search (SEA)", "Search (SEA) verstärken"),
    "Relaunch an emailing campaign": ("Rilanciare una campagna di emailing", "Relanzar una campaña de emailing", "E-Mailing-Kampagne neu starten"),
    "Review the brand-website CTAs (pop-in, showroom, homepage) and their UTM tagging": (
        "Rivedere i CTA del sito del marchio (pop-in, showroom, homepage) e il relativo tagging UTM",
        "Revisar los CTA del sitio de la marca (pop-in, showroom, página de inicio) y su etiquetado UTM",
        "CTAs der Markenwebsite (Pop-in, Showroom, Startseite) und deren UTM-Tagging überprüfen"),
    "These rates reflect the statuses entered by dealers in C1ST: the follow-up is being rolled out gradually by market and brand, so they cannot be compared from one period to another.": (
        "Questi tassi riflettono gli stati inseriti dai concessionari in C1ST: il monitoraggio viene attivato gradualmente per mercato e marchio, quindi non sono confrontabili da un periodo all'altro.",
        "Estas tasas reflejan los estados introducidos por los concesionarios en C1ST: el seguimiento se despliega de forma progresiva por mercado y marca, por lo que no son comparables de un período a otro.",
        "Diese Quoten spiegeln die von den Händlern in C1ST erfassten Status wider: Das Follow-up wird nach Markt und Marke schrittweise ausgerollt und ist daher von Periode zu Periode nicht vergleichbar."),
    "Recent period: orders keep being linked to the leads for 90 days, so the rates are provisional and no change is calculated.": (
        "Periodo recente: gli ordini continuano a essere associati ai lead per 90 giorni, quindi i tassi sono provvisori e non viene calcolata alcuna evoluzione.",
        "Período reciente: los pedidos se siguen asociando a los leads durante 90 días, por lo que las tasas son provisionales y no se calcula ninguna evolución.",
        "Aktueller Zeitraum: Bestellungen werden Leads noch 90 Tage lang zugeordnet; die Quoten sind daher vorläufig und es wird keine Veränderung berechnet."),
    "Spoticar: C1ST does not track contact or treatment of these buyback leads (n/a); the brand is excluded from the total.": (
        "Spoticar: C1ST non monitora il contatto né il trattamento di questi lead di riacquisto (n.d.); il marchio è escluso dal totale.",
        "Spoticar: C1ST no registra el contacto ni el tratamiento de estos leads de recompra (n.d.); la marca se excluye del total.",
        "Spoticar: C1ST erfasst weder Kontakt noch Bearbeitung dieser Ankauf-Leads (k. A.); die Marke ist im Gesamt nicht enthalten."),
    "Spoticar: no orders in C1ST for these buyback leads (n/a); the brand is excluded from the total.": (
        "Spoticar: nessun ordine in C1ST per questi lead di riacquisto (n.d.); il marchio è escluso dal totale.",
        "Spoticar: sin pedidos en C1ST para estos leads de recompra (n.d.); la marca se excluye del total.",
        "Spoticar: keine Bestellungen in C1ST für diese Ankauf-Leads (k. A.); die Marke ist im Gesamt nicht enthalten."),
    "Additional sales": ("Vendite aggiuntive", "Ventas adicionales", "Zusätzliche Verkäufe"),
    "Additional sales (YTD)": ("Vendite aggiuntive cumulate", "Ventas adicionales acumuladas", "Zusätzliche Verkäufe kumuliert"),
    "Additional sales = NSC orders of the period − NSC orders of the same period last year (orders linked to the lead up to 90 days after its creation).": (
        "Vendite aggiuntive = ordini NSC del periodo − ordini NSC dello stesso periodo dell'anno precedente (ordini associati al lead fino a 90 giorni dopo la sua creazione).",
        "Ventas adicionales = pedidos NSC del período − pedidos NSC del mismo período del año anterior (pedidos asociados al lead hasta 90 días después de su creación).",
        "Zusätzliche Verkäufe = NSC-Bestellungen des Zeitraums − NSC-Bestellungen desselben Zeitraums im Vorjahr (Bestellungen, die dem Lead bis zu 90 Tage nach dessen Erstellung zugeordnet werden)."),
    "Recent period: orders keep being linked to the leads for 90 days, so the additional sales shown are provisional.": (
        "Periodo recente: gli ordini continuano a essere associati ai lead per 90 giorni, quindi le vendite aggiuntive mostrate sono provvisorie.",
        "Período reciente: los pedidos se siguen asociando a los leads durante 90 días, por lo que las ventas adicionales mostradas son provisionales.",
        "Aktueller Zeitraum: Bestellungen werden Leads noch 90 Tage lang zugeordnet; die angezeigten zusätzlichen Verkäufe sind daher vorläufig."),
    "Orders are counted up to 90 days after the lead.": ("Gli ordini sono conteggiati fino a 90 giorni dopo il lead.", "Los pedidos se cuentan hasta 90 días después del lead.", "Bestellungen werden bis zu 90 Tage nach dem Lead gezählt."),
    "1 V2 site in scope. Before: the 28 days before the switch; after: since the switch.": (
        "1 sito V2 nel perimetro. Prima: i 28 giorni precedenti il passaggio; dopo: dal passaggio.",
        "1 sitio V2 en el perímetro. Antes: los 28 días anteriores al cambio; después: desde el cambio.",
        "1 V2-Website im Perimeter. Vorher: die 28 Tage vor der Umstellung; nachher: seit der Umstellung."),
}

# ------------------------------------------------------------------ phrases à gabarit : {nom} = partie variable, conservée telle quelle
PHRASES = [
    ("“{top}” is the placement generating the most leads: {n} ({p} of the site's CTA leads).",
     "“{top}” è la posizione che genera più lead: {n} ({p} dei lead CTA del sito).",
     "“{top}” es la ubicación que genera más leads: {n} ({p} de los leads CTA del sitio).",
     "„{top}“ ist die Platzierung mit den meisten Leads: {n} ({p} der CTA-Leads der Website)."),
    ("{n} active placements over the period.", "{n} posizioni attive nel periodo.", "{n} ubicaciones activas en el período.", "{n} aktive Platzierungen im Zeitraum."),
    ("{p} of the site's customers trade in a {b} (loyalty), {q} another Stellantis brand and {r} a competitor brand, out of {n} leads.",
     "{p} dei clienti del sito permuta un veicolo {b} (fedeltà), {q} un altro marchio Stellantis e {r} un marchio concorrente, su {n} lead.",
     "{p} de los clientes del sitio entrega un {b} (fidelidad), {q} otra marca Stellantis y {r} una marca competidora, sobre {n} leads.",
     "{p} der Kunden der Website geben einen {b} in Zahlung (Treue), {q} eine andere Stellantis-Marke und {r} eine Wettbewerbsmarke, bei {n} Leads."),
    ("Most traded-in Stellantis models: {a}. Most traded-in competitor models: {b}.",
     "Modelli Stellantis più permutati: {a}. Modelli concorrenti più permutati: {b}.",
     "Modelos Stellantis más entregados: {a}. Modelos de la competencia más entregados: {b}.",
     "Am häufigsten in Zahlung gegebene Stellantis-Modelle: {a}. Am häufigsten in Zahlung gegebene Wettbewerbsmodelle: {b}."),
    ("Most frequent trade-in → purchase: {x}", "Permuta → acquisto più frequenti: {x}", "Entrega → compra más frecuentes: {x}", "Häufigste Inzahlunggabe → Kauf: {x}"),
    ("{m} ranks #{r} of {k} markets, with {p} of autobiz New cars leads over the period ({n} leads).",
     "{m} è al {r}° posto su {k} mercati, con il {p} dei lead auto nuove autobiz nel periodo ({n} lead).",
     "{m} ocupa el puesto {r} de {k} mercados, con el {p} de los leads de coches nuevos de autobiz en el período ({n} leads).",
     "{m} liegt auf Platz {r} von {k} Märkten mit {p} der autobiz-Neuwagen-Leads im Zeitraum ({n} Leads)."),
    ("Change: {x}.", "Evoluzione: {x}.", "Evolución: {x}.", "Veränderung: {x}."),
    ("{p} of the period's leads are entered with the licence plate; the completion rate by entry mode is not measured in the back-office data.",
     "{p} dei lead del periodo è inserito con la targa; il tasso di completamento per modalità di inserimento non è misurato nei dati del back-office.",
     "{p} de los leads del período se introduce con la matrícula; la tasa de finalización por modo de introducción no se mide en los datos del back-office.",
     "{p} der Leads im Zeitraum werden mit dem Kennzeichen erfasst; die Abschlussquote je Erfassungsart wird in den Back-Office-Daten nicht gemessen."),
    ("{n} V2 sites in scope. Before: the 28 days before the switch; after: since the switch.",
     "{n} siti V2 nel perimetro. Prima: i 28 giorni precedenti il passaggio; dopo: dal passaggio.",
     "{n} sitios V2 en el perímetro. Antes: los 28 días anteriores al cambio; después: desde el cambio.",
     "{n} V2-Websites im Perimeter. Vorher: die 28 Tage vor der Umstellung; nachher: seit der Umstellung."),
    ("Users reaching the estimate: {a} → {b} (different observation windows).",
     "Utenti che raggiungono la stima: {a} → {b} (finestre di osservazione diverse).",
     "Usuarios que llegan a la valoración: {a} → {b} (ventanas de observación distintas).",
     "Nutzer, die die Bewertung erreichen: {a} → {b} (unterschiedliche Beobachtungszeiträume)."),
    ("Data from {m} 1 to {d}: the projection extends the average daily rate over the {n} days of the month (indicative).",
     "Dati dall'1 al {d} {m}: la proiezione estende il ritmo medio giornaliero ai {n} giorni del mese (indicativo).",
     "Datos del 1 al {d} de {m}: la proyección prolonga el ritmo medio diario sobre los {n} días del mes (indicativo).",
     "Daten vom 1. bis {d}. {m}: die Prognose schreibt die durchschnittliche Tagesrate auf die {n} Tage des Monats fort (indikativ)."),
    ("{p} of the leads sent have no treatment status in C1ST over the period.",
     "{p} dei lead inviati non ha uno stato di trattamento in C1ST nel periodo.",
     "{p} de los leads enviados no tiene estado de tratamiento en C1ST en el período.",
     "{p} der gesendeten Leads haben im Zeitraum keinen Bearbeitungsstatus in C1ST."),
    ("{n} NSC orders linked to the period's leads, i.e. {p} of unique customers.",
     "{n} ordini associati ai lead del periodo, ovvero il {p} dei clienti unici.",
     "{n} pedidos asociados a los leads del período, es decir, el {p} de los clientes únicos.",
     "{n} Bestellungen zu den Leads des Zeitraums, d. h. {p} der eindeutigen Kunden."),
    ("NSC orders {p}", "Ordini NSC {p}", "Pedidos NSC {p}", "NSC-Bestellungen {p}"),
    ("YTD NSC orders {y}", "Ordini NSC cumulati {y}", "Pedidos NSC acumulados {y}", "NSC-Bestellungen kumuliert {y}"),
    ("Additional sales vs the same period last year: {x} ({a} NSC orders vs {b}).",
     "Vendite aggiuntive rispetto allo stesso periodo dell'anno precedente: {x} ({a} ordini NSC contro {b}).",
     "Ventas adicionales frente al mismo período del año anterior: {x} ({a} pedidos NSC frente a {b}).",
     "Zusätzliche Verkäufe gegenüber demselben Zeitraum im Vorjahr: {x} ({a} NSC-Bestellungen gegenüber {b})."),
    ("Additional sales — {p}", "Vendite aggiuntive — {p}", "Ventas adicionales — {p}", "Zusätzliche Verkäufe — {p}"),
    ("Order rate: {x} {r}.", "Tasso di ordine: {x} {r}.", "Tasa de pedido: {x} {r}.", "Bestellquote: {x} {r}."),
    ("New cars share {x} {r}", "Quota auto nuove {x} {r}", "Cuota de coches nuevos {x} {r}", "Neuwagenanteil {x} {r}"),
    ("Traffic {x} {r}", "Traffico {x} {r}", "Tráfico {x} {r}", "Traffic {x} {r}"),
    ("Complete UTM tagging ({p} of leads without an identified source)", "Completare il tagging UTM ({p} dei lead senza fonte identificata)",
     "Completar el etiquetado UTM ({p} de los leads sin fuente identificada)", "UTM-Tagging vervollständigen ({p} der Leads ohne identifizierte Quelle)"),
    ("Decrease: {x}", "Calo: {x}", "Descenso: {x}", "Rückgang: {x}"),
    ("Increase: {x}", "Aumento: {x}", "Aumento: {x}", "Anstieg: {x}"),
    # titres
    ("Market ranking — New cars leads", "Classifica dei mercati — lead auto nuove", "Clasificación de mercados — leads de coches nuevos", "Marktranking — Neuwagen-Leads"),
    ("Vehicle entry: licence plate or make / model", "Inserimento del veicolo: targa o marca / modello", "Introducción del vehículo: matrícula o marca / modelo", "Fahrzeugerfassung: Kennzeichen oder Marke / Modell"),
    ("{p} projection — New cars leads", "Proiezione {p} — lead auto nuove", "Proyección {p} — leads de coches nuevos", "Prognose {p} — Neuwagen-Leads"),
    ("Leads overview — {p}", "Panoramica dei lead — {p}", "Visión general de los leads — {p}", "Lead-Überblick — {p}"),
    ("Follow-up of leads sent to dealers — {p}", "Lead inviati ai concessionari — {p}", "Leads enviados a concesionarios — {p}", "An Händler gesendete Leads — {p}"),
    ("From lead to order — {p}", "Dal lead all'ordine — {p}", "Del lead al pedido — {p}", "Vom Lead zur Bestellung — {p}"),
    ("{b} — CTA on the brand website {p}", "{b} — CTA sul sito del marchio {p}", "{b} — CTA en el sitio de la marca {p}", "{b} — CTA auf der Markenwebsite {p}"),
    ("{b} — Conquest vs loyalty {p}", "{b} — Conquista vs fedeltà {p}", "{b} — Conquista vs fidelidad {p}", "{b} — Eroberung vs. Treue {p}"),
    ("{b} — Journey before / after V2", "{b} — Percorso prima / dopo la V2", "{b} — Recorrido antes / después de la V2", "{b} — Customer Journey vor / nach V2"),
    ("YTD {y}", "Cumulato {y}", "Acumulado {y}", "Kumuliert {y}"),
]

# ------------------------------------------------------------------ morceaux de phrase (remplacement partiel, après les phrases)
MORCEAUX = [
    ("vs previous period", "vs periodo precedente", "vs período anterior", "ggü. Vorperiode"),
    ("vs last year", "vs anno precedente", "vs año anterior", "ggü. Vorjahr"),
]

# ------------------------------------------------------------------ noms d'étapes du tunnel (données, en français) -> en, it, es, de
ETAPES = {
    "Page d'accueil": ("Homepage", "Homepage", "Página de inicio", "Startseite"),
    "Version": ("Version", "Versione", "Versión", "Version"),
    "Kilométrage": ("Mileage", "Chilometraggio", "Kilometraje", "Kilometerstand"),
    "Coordonnées": ("Contact details", "Dati di contatto", "Datos de contacto", "Kontaktdaten"),
    "Point de vente": ("Dealer choice", "Punto vendita", "Punto de venta", "Händlerwahl"),
    "Estimation": ("Price estimation", "Stima", "Valoración", "Bewertung"),
}


def _regex(modele):
    parties = re.split(r"(\{[a-z]+\})", modele)
    return re.compile("^" + "".join((f"(?P<{p[1:-1]}>.+?)" if p.startswith("{") else re.escape(p)) for p in parties if p) + "$", re.S)


_COMPILES = [(_regex(p[0]), p[1:]) for p in PHRASES]
_IDX = {"it": 0, "es": 1, "de": 2}


def traduit_texte(texte, langue):
    """Traduit un paragraphe anglais (ou un nom d'étape français) ; renvoie le texte inchangé si rien n'est connu."""
    brut = texte
    puce = ""
    if brut.startswith("• "):
        puce, brut = "• ", brut[2:]
    if brut in ETAPES:
        e = ETAPES[brut]
        return puce + (e[0] if langue == "en" else e[1 + _IDX[langue]] if langue in _IDX else brut)
    if langue not in _IDX:
        return texte
    i = _IDX[langue]
    if brut in LIBELLES:
        return puce + LIBELLES[brut][i]
    for rx, trads in _COMPILES:
        m = rx.match(brut)
        if m:
            res = trads[i].format(**m.groupdict())
            for en, *tr in MORCEAUX:
                res = res.replace(en, tr[i])
            return puce + res
    out = brut
    for en, *trads in MORCEAUX:
        out = out.replace(en, trads[i])
    return (puce + out) if out != brut else texte


def _paragraphes(prs):
    for s in prs.slides:
        for sh in s.shapes:
            if sh.has_text_frame:
                yield from sh.text_frame.paragraphs
            if getattr(sh, "has_table", False) and sh.has_table:
                for r in sh.table.rows:
                    for c in r.cells:
                        yield from c.text_frame.paragraphs


def traduit_deck(prs, langue):
    """Applique les traductions à tous les paragraphes du deck (diapositives et tableaux). Pour le français : rien ; pour l'anglais : noms d'étapes seulement."""
    if langue == "fr":
        return 0
    n = 0
    for p in _paragraphes(prs):
        if not p.runs:
            continue
        t = "".join(r.text for r in p.runs)
        nt = traduit_texte(t, langue)
        if nt != t:
            p.runs[0].text = nt
            for r in p.runs[1:]:
                r.text = ""
            n += 1
    return n
