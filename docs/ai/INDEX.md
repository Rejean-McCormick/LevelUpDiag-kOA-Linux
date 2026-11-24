<!-- kOA Doc Server · Docs IA · lot 03 · projet : LevelUpDiag-Koali · proposition dérivée à valider -->
# Navigation IA — LevelUpDiag-Koali

**Objet constaté :** Diagnostic indépendant de la disponibilité Koali et des liaisons entre produits propriétaires.

**Frontière de responsabilité :** N00 contrôle l’intégrité du diagnostic; N12 examine le produit Koali; N14 l’écart d’intégration; le propriétaire de l’hôte conserve l’admission.

**Source :** `SmartDump_20261120_221507.zip` → `LevelUpDiag-Koali_Code_snapshot.zip` (20 novembre 2026). Le chemin Windows est une déclaration de snapshot, pas une vérification de l'état actuel.

**Statut :** Documentation de navigation dérivée de sources propriétaires, à revoir. Ce document ne vaut ni profil d'ingénierie mesuré, ni certification, ni permission d'exécution.

## Ordre de lecture — fichiers réellement présents dans la capture

1. [`README.md`](../../README.md) — SHA-256 `6b47cd347067cd00…` dans la capture.
2. [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) — SHA-256 `112fea3900b83380…` dans la capture.
3. [`docs/BRANCH08_OBSERVED_READINESS.md`](../../docs/BRANCH08_OBSERVED_READINESS.md) — SHA-256 `b576f3ad05c46956…` dans la capture.
4. [`docs/SECURITY_MODEL.md`](../../docs/SECURITY_MODEL.md) — SHA-256 `b8cf498f59c45110…` dans la capture.
5. [`pyproject.toml`](../../pyproject.toml) — SHA-256 `2eeea074ae95bed0…` dans la capture.

## Parcours recommandé pour une intervention assistée par IA

1. Identifier la question, le sous-système concerné et les responsabilités du propriétaire.
2. Lire les documents ci-dessus **dans cet ordre**; consulter les contrats et consignes propriétaires plus récents si le checkout a évolué.
3. Épingler le profil de campagne koali-final, examiner les prérequis et les résultats par niveau avant tout verdict d’aptitude.
4. Établir les vérifications effectivement disponibles dans la révision locale, consigner les résultats et ne conclure qu'à l'intérieur du périmètre couvert.
5. Proposer les changements; demander une décision explicite avant toute écriture à effet, déploiement, publication ou promotion de preuves.

## Risque propre à ce dépôt

Un rapport de qualification locale n’autorise ni release hôte ni activation Koali Spaces.

## Compléments

- [`AI_CONTEXT.md`](AI_CONTEXT.md) : règles de travail et frontières de confiance.
- `AGENTS.md` : s'il existe déjà chez le propriétaire, ses consignes priment sur ces propositions; sinon l'overlay peut en ajouter un sans remplacement.
- `PROFIL_INGENIERIE.md` : optionnel, uniquement après exécution réelle de RepoSurveyor sur un dépôt local et accord explicite pour sa copie.
- Le Framework Kristal v11 est un standard documentaire **facultatif** : lire le profil réellement verrouillé, sans imposer de migration.
