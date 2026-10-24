# Plan d'urgence sécurité — Converge

À suivre dans l'ordre, du moins au plus radical. Aucune adresse, aucun jeton dans ce fichier (dépôt public) : les valeurs sont dans les variables Vercel et les secrets GitHub.

## 0. Savoir ce qui se passe
- Teams (canal sécurité) : cartes « à vérifier » (connexions anormales) et « sonde externe » (liste blanche inefficace, Converge injoignable), bilan chaque matin.
- Vercel > projet `psa-site-factory-dashboard` > Firewall : refus de la liste blanche, limites de débit, challenges (l'API ne remonte pas l'historique : regarder l'onglet).
- Vercel > Observability / Logs : erreurs et pics de requêtes.

## 1. Attaque par volume ou site instable
1. Mode « Attack Challenge » (Vercel > Firewall > Bot Management > Attack Challenge Mode) : tous les visiteurs non autorisés passent un challenge. En ligne de commande : `vercel api /v1/security/attack-mode -X POST -F projectId=<id> -F attackModeEnabled=true -F attackModeActiveUntil=<timestamp ms>` (à tester une première fois en dehors d'une crise).
2. Vérifier que `liste-blanche-ip` est active : `vercel firewall rules list`.
3. Plafond de dépenses : Vercel > Settings > Billing > Spend Management (alerte + coupure), pour qu'une attaque ne devienne pas une facture.

## 2. Compte ou accès suspecté
1. Retirer l'adresse concernée de `ALLOWED_EMAILS` (variable Vercel, `vercel env rm` puis `vercel env add --sensitive`) et redéployer : `vercel deploy --prod` (le middleware revérifie à chaque requête).
2. Désactiver le compte chez Google. Déconnecter le compte du back-office.
3. Restreindre : retirer des adresses de `liste-blanche-ip` (`vercel firewall rules edit` puis `vercel firewall publish`) ET de `ALLOWED_IPS`.

## 3. Coupure totale temporaire
`MAINTENANCE=1` (production) puis redéploiement : la page reste affichée, voilée, et plus aucune donnée ni API n'est servie. Pour lever : supprimer la variable et redéployer.

## 4. Jeton ou clé divulgué
Renouveler chez la source PUIS mettre à jour Vercel / GitHub :
- Jetons GitHub (`GITHUB_TOKEN`, `GH_DISPATCH_TOKEN`, `GITHUB_PR_TOKEN`, `DATA_REPO_TOKEN`, `PIPELINE_PUSH_TOKEN`) : régénérer, en « fine-grained » limité aux deux dépôts, avec expiration.
- `LEADS_EXTRACT_TOKEN`, `PSA_EXTRACT_TOKEN` (back-office), `C1ST_*` (Salesforce), `GA4_SERVICE_ACCOUNT` / `GA4_OEM_SERVICE_ACCOUNT` / `GSC_SERVICE_ACCOUNT` (clés de comptes de service Google), `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `AUTH_COOKIE_SECRET` (changer ce dernier déconnecte tout le monde), webhooks Teams.
- URL de déploiement (`VERCEL_DEPLOY_HOOK`) : la supprimer et la recréer.

## 5. Code suspect en production
La branche `main` est protégée (PR + test e2e obligatoires, y compris pour l'administrateur). Retour arrière immédiat : `vercel rollback` (ou promouvoir le déploiement précédent dans Vercel > Deployments), puis chercher le commit fautif (`git log`).

## 6. Données perdues ou corrompues
Les données vivent dans le dépôt privé `psa-site-factory-data` (historique git complet : retour à un commit antérieur). Prévoir une copie hors ligne (`gh repo clone … --mirror`) régulière.

## 7. Après l'incident
Noter date, heure, ce qui a été vu, ce qui a été fait. Prévenir la hiérarchie / le RSSI. Menaces d'une personne : conserver les messages et dates, ne rien supprimer.
