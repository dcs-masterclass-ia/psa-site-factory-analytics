#!/bin/sh
# Recupere data/ depuis le repo prive separe dcs-masterclass-ia/psa-site-factory-data
# (12/08/2026 : data/ ne vit plus dans ce repo, pour permettre a celui-ci de
# passer public sans exposer les vraies donnees business). Appele comme
# "Install Command" Vercel -- le champ a une limite de 256 caracteres, d'ou
# ce script plutot que la commande git clone en ligne.
#
# $VERCEL_GIT_COMMIT_REF est fourni automatiquement par Vercel (nom de la
# branche deployee) : on essaie d'abord la meme branche cote donnees (main
# ou staging, les deux existent), avec un repli sur main pour toute autre
# branche (preview sur une feature branch, par ex.) qui n'a pas d'equivalent
# cote donnees.
set -e
# rm -rf prealable : une machine de build Vercel reutilisee entre deux
# deploiements peut laisser un data/ partiel d'un clone precedent
# interrompu (403, timeout...) -- "destination path already exists"
# sinon, constate le 12/08/2026.
rm -rf data
REPO="https://x-access-token:${DATA_REPO_TOKEN}@github.com/dcs-masterclass-ia/psa-site-factory-data.git"
git clone --depth 1 --branch "$VERCEL_GIT_COMMIT_REF" "$REPO" data \
  || git clone --depth 1 --branch main "$REPO" data

# Jamais deployes : l'historique profond (data/history, plusieurs dizaines de
# Mo, lu par Converge directement dans le repo de donnees) et les
# conversations KamIA (data/kamia, lues via l'API GitHub par api/_lib/store.js,
# jamais par fichier statique). Sans ce nettoyage ils seraient servis en
# statique sous /data/ a tout compte connecte.
rm -rf data/history data/kamia data/presentations data/tickets data/events data/objectifs data/alertes data/alertes.json   # jamais servis en statique : lus par les API via api/_lib/store.js

# public/ = outputDirectory reel (vercel.json), construit a chaque build.
# Avant ce changement (09/10/2026, test d'intrusion), outputDirectory="."
# servait TOUT le repo en statique -- middleware.js (logique d'auth
# complete), pipeline/*.py (table des siteId back-office, IDs GA4),
# .github/workflows/*.yml etc. etaient lisibles par un visiteur anonyme,
# sans session. Seuls les fichiers listes ici doivent etre publics ; data/
# est copie en plus (il reste aussi a la racine pour que vercel.json
# "includeFiles":"data/**" puisse le bundler dans les fonctions serverless,
# qui resolvent ce chemin depuis la racine du projet, pas depuis
# outputDirectory). middleware.js et api/ restent a la racine : Vercel ne
# les detecte qu'a cet emplacement precis, jamais dans outputDirectory.
rm -rf public
mkdir -p public
cp index.html support.js style.css script.js hermes-agui.js \
   favicon.png favicon-preprod.png logo-blanc.png logo-noir.png public/
cp -R data public/data
