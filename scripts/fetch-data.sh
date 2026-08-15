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
REPO="https://x-access-token:${DATA_REPO_TOKEN}@github.com/dcs-masterclass-ia/psa-site-factory-data.git"
git clone --depth 1 --branch "$VERCEL_GIT_COMMIT_REF" "$REPO" data \
  || git clone --depth 1 --branch main "$REPO" data
