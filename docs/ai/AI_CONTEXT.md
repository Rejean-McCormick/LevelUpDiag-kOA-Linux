<!-- kOA Doc Server · Docs IA · lot 03 · projet : LevelUpDiag-Koali · proposition dérivée à valider -->
# Contexte IA — LevelUpDiag-Koali

## Identité et périmètre observés

Diagnostic indépendant de la disponibilité Koali et des liaisons entre produits propriétaires.

**Limite d'autorité :** N00 contrôle l’intégrité du diagnostic; N12 examine le produit Koali; N14 l’écart d’intégration; le propriétaire de l’hôte conserve l’admission.

**Provenance :** `SmartDump_20261120_221507.zip` → `LevelUpDiag-Koali_Code_snapshot.zip` (20 novembre 2026). Les sources citées sont celles de cette capture; le propriétaire du dépôt conserve l'autorité sur les révisions présentes et futures.

## Avant toute proposition de modification

1. Déterminer si le travail demandé porte sur **un document, un contrat, une donnée, un exécutable ou un résultat dérivé**.
2. Consulter les fichiers propriétaires, dans cet ordre :
   - [`README.md`](../../README.md)
   - [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md)
   - [`docs/BRANCH08_OBSERVED_READINESS.md`](../../docs/BRANCH08_OBSERVED_READINESS.md)
   - [`docs/SECURITY_MODEL.md`](../../docs/SECURITY_MODEL.md)
   - [`pyproject.toml`](../../pyproject.toml)

3. Vérifier les éventuels `AGENTS.md`, manifests, locks, schémas ou décisions de ce checkout; ne pas traiter cette fiche dérivée comme un substitut.
4. Cartographier producteur, consommateur, format, version et permissions pour chaque frontière franchie.

## Procédure adaptée

**Tâche type :** Épingler le profil de campagne koali-final, examiner les prérequis et les résultats par niveau avant tout verdict d’aptitude.

**Éviter précisément :** Un rapport de qualification locale n’autorise ni release hôte ni activation Koali Spaces.

**Contrôles attendus avant la conclusion :** identifier les tests, validateurs et rapports réellement présents sur le système cible; exécuter uniquement ceux qui sont non destructifs et appropriés; relier chaque résultat à une révision et un environnement précis. En absence de code/test (ou si les sources sont insuffisantes), écrire « non vérifié », jamais « PASS ».

## Utilisation par kOA Doc Server

- **Lecture et export :** n'inclure que les documents explicitement sélectionnés, avec chemins relatifs, empreintes et provenance.
- **RepoSurveyor :** profils mesurés séparément à partir du code local. Ne pas fabriquer `ENGINEERING_PROFILE.md` depuis cette fiche; l'alias français est `PROFIL_INGENIERIE.md` après génération réelle.
- **Diagnostics :** observations datées, preuves historiques et états certifiés restent distincts. Aucune promotion automatique.
- **Wikis et vues :** documents dérivés, jamais propriétaires des contrats ni des permissions.
- **Confidentialité :** filtrer secrets, données personnelles, médias sous droits, caches, backups et rapports privés avant un ZIP de contexte IA.
- **Standard Kristal Framework v11 :** si pertinent, consulter le cadre comme référence possible, sans l'exiger pour naviguer ni forcer une migration du profil historique du dépôt.

## État de cette fiche

`DOCUMENTATION_REDACTIONNELLE_A_REVOIR` : elle facilite le démarrage d'un agent, mais **ne prouve aucun état d'intégration, publication, conformité ni maturité**.
