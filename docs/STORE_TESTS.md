# N13 — Store et applications tierces (2.6)

N13 cible **koa-linux**, où se trouve `host/store/`. Ce n'est pas un dépôt de
store supplémentaire. Il accompagne N12 dans `koali-system` et
`koali-system-debug`, avec une campagne `store` indépendante et un bouton STORE.

## Trois preuves différentes

| Couverture | Exécution | Ce que cela prouve |
|---|---|---|
| Sources | Windows ou Linux | Catalogue exact, syntaxe Python, raccourcis, politiques, paquets requis et projection dans l'image |
| Session Linux | Dans la session graphique cible | Outils présents, greffon Flatpak détecté, bus/portail, raccourcis installés correspondant au script source, dépôt et inventaire Flatpak |
| Fonctionnement réel | Essai explicite dans une VM jetable | Ouverture des fenêtres, installation, utilisation et reprise après panne |

Les tests de sources n'importent ni n'exécutent le code du dépôt cible.
La présence du fichier de tests est un contrôle distinct de leur exécution.
N13 ne télécharge rien, ne configure pas de dépôt et n'installe aucun logiciel.
Il ne certifie ni les signatures du dépôt, ni le fonctionnement du greffon à
partir de sa seule présence, ni le fonctionnement des applications installées.

## Lancer depuis le dépôt LevelUpDiag-Koali

```sh
python levelupdiag.py run store
```

Le chemin par défaut est `../koa-linux`. Pour le modifier, fusionner dans
`levelupdiag.config.local.json` (sans remplacer ses autres paramètres) :

```json
{
  "store": {
    "root": "../koa-linux",
    "runtime_checks": false
  }
}
```

Sous Linux, mettre `runtime_checks` à `true` et lancer le diagnostic **dans la
session utilisateur graphique de la VM**, sans sudo. Le bouton Windows reste
sur Python natif ; il ne valide pas implicitement une VM ni une session WSL.
Si des contrôles Linux sont demandés sous Windows, N13 rapporte `BLOCKED`.

Le module autonome permet de tester cette mise à jour même sans le dépôt complet
de LevelUpDiag (se placer dans `overlays/LevelUpDiag-Koali` pour cette archive) :

```sh
python -m levels.store_support --root /chemin/koa-linux
python -m levels.store_support --root /chemin/koa-linux --runtime
```

Il imprime un rapport JSON. Son code de sortie vaut 1 en présence de FAIL,
BLOCKED ou erreur de configuration ; 0 indique seulement l'absence de ces erreurs,
pas une qualification de bout en bout. Les points non exécutés restent PARTIAL.
Le moteur historique agrège les verdicts selon le mode de campagne.

## Tests du code de l'installateur

Depuis le dépôt **koa-linux** corrigé, exécuter explicitement :

```sh
python tests/system/test_third_party_store.py
```

Cette suite utilise des simulations et couvre annulation, sélection fermée,
dépôt inattendu, applications déjà présentes, échecs partiels et portée utilisateur.
Elle ne prouve pas qu'une installation réelle aboutit. N13 ne l'exécute pas
implicitement pendant une inspection en lecture seule.

## Scénario d'acceptation dans une VM jetable

Préparer un instantané et un compte utilisateur graphique ; installer les prérequis
système via l'adaptateur de distribution. Utiliser un dépôt koa-linux contenant
la livraison du store. Consigner la version de l'image, le commit, la date,
l'architecture et les versions des logiciels. Ne pas utiliser le compte principal.

1. Exécuter N13 avec `--runtime`, conserver le JSON. Un dépôt absent avant le
   premier lancement est un WARN attendu ; une URL différente est un FAIL.
2. Ouvrir « Installer les essentiels », annuler, puis comparer `flatpak remotes
   --user` et `flatpak list --user --app` à l'état initial : aucun ajout.
3. Ouvrir « Store — applications tierces », accepter la configuration. Vérifier
   la fenêtre GNOME Logiciels, le catalogue Flathub et la recherche de Firefox.
4. Sélectionner une seule application manquante (par exemple PeaZip), installer,
   vérifier son apparition dans `flatpak list --user --app`, son ouverture et
   l'accès à un fichier via le portail. Les autres applications restent absentes.
5. Relancer la même sélection : application déjà présente, aucune réinstallation.
6. Installer le reste de la présélection ; vérifier une page web Firefox, un média
   VLC avec audio, le démarrage de Thunderbird, une archive PeaZip, un fichier
   Notepad Next, un document LibreOffice et une base de test KeePassXC.
   Ne pas ajouter de vrais comptes ni de mots de passe personnels.
7. Sur un second instantané, couper le réseau pendant un téléchargement : échec
   visible, journal utile, pas de faux succès. Rétablir le réseau et relancer :
   les applications installées sont ignorées, les manquantes sont réessayées.
8. Lancer deux raccourcis d'installation simultanément : une seule opération.
9. Relancer N13. Conserver le rapport, le journal et les résultats par application.
   Restaurer l'instantané pour nettoyer l'essai.

Cette version n'ingère pas de déclaration manuelle de réussite pour transformer
le verdict en PASS : `end_to_end_validated` reste false. Le procès-verbal de VM
constitue une preuve séparée. Cela évite un faux PASS global.
