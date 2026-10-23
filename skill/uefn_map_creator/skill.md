---
name: uefn-map-creator
description: Concoit, construit en 3D, cable et verifie une carte UEFN (Unreal Editor for Fortnite) a partir d'une simple invite, en pilotant l'editeur par le serveur MCP officiel (http://127.0.0.1:8000/mcp). A utiliser des que l'utilisateur demande de creer une map Fortnite (1v1, Box Fight, Zone Wars, Red vs Blue, Tycoon, Deathrun, RPG), de placer ou mesurer des acteurs et devices dans le niveau courant, d'ecrire et compiler du Verse, ou de corriger des distances et collisions d'une scene.
---

# Constructeur de carte UEFN

## Objectif

Transformer une invite en carte UEFN assemblee dans le niveau courant : structure, devices, decors, code Verse compile, avec un rapport de verification qui distingue ce qui a ete **relu dans l'editeur** de ce qui reste **inconnu**.

## Regles non negociables

1. **Un seul appel MCP a la fois**, jamais en parallele, jamais deux agents sur l'editeur.
2. Le serveur MCP est sur `http://127.0.0.1:8000/mcp`, sans authentification : ne jamais l'exposer hors de la machine.
3. **Ne jamais sauvegarder** (`Save`, `SaveAll`), jamais publier, jamais lancer une session, jamais modifier un asset du projet sans demande explicite de l'utilisateur.
4. Ne tenir pour vrai que ce qui a ete relu par un second appel. Une reponse vide (`[]`, `null`, `false`) vaut « inconnu », pas « absent ».
5. Tout etat est sur disque dans le workspace (jamais dans le skill, jamais seulement dans la conversation).
6. Signaler a l'utilisateur, dans le rapport final, ce qui n'a pas ete verifie.

## Pilotage

Tout passe par le CLI `script/uefn_spatial_cli.py` (client MCP `script/mcp_client.py`). Ne pas recoder le protocole.
Python **3.10 ou plus** est requis : en dessous, le CLI s'arrete avec le code 2.
Il n'existe **pas** de Bridge Python, pas de `batch.exec`, pas d'`editor.undo`, pas de `validate_folder` : les mentions de ces commandes dans d'anciennes notes sont caduques.

```bash
python script/uefn_spatial_cli.py <commande> --workspace <chemin_absolu> [--dry-run]
```
Le workspace est le dossier d'etat de la carte, **hors du skill** (chemin absolu conseille) : un
workspace a l'interieur du skill est refuse (`WORKSPACE_INSIDE_SKILL`). `init --template
blank|1v1_arena|boxfight` cree le dossier et ses 5 fichiers de spec ; il n'ecrase jamais un
workspace deja rempli sans `--force` (`WORKSPACE_NOT_EMPTY`).
Codes retour : `0` PASSED, `1` FAILED (**l'appel a ete traite : l'etat peut etre partiel**, relire avant de rejouer), `2` editeur injoignable (rien n'a ete execute), `3` timeout (etat inconnu, relire avant de rejouer).
Chaque appel du CLI spatial est journalise dans `<workspace>/_mcp_calls.jsonl`. Un appel direct via `script/mcp_client.py` ne l'est que si l'on passe `--log <workspace>/_mcp_calls.jsonl` (ou la variable `UEFN_MCP_LOG`).

## Verification sans editeur

```bash
python script/tests/verify.py
```
Demarre un faux serveur MCP local (`script/tests/mock_mcp.py`, 127.0.0.1 uniquement) et rejoue la
chaine complete, y compris les pieges documentes. Attendu : `110/110 OK`. Cela prouve les
**contrats** du skill (codes retour, statuts, refus sans accord, rapports honnetes), pas le
comportement de l'editeur reel. Procedure de premier test complet : `references/first-run.md`.

## Fichiers d'etat (`<workspace>/`)

Specs (etapes 1 a 7) :
- `01_gdd.json` cahier des charges, simulation, `requested_assets`
- `02_palette.json` assets, chemins MCP, `scale`, tailles et pivots **mesures**
- `03_grid.json` matrice 2D par etage, `symmetric` + `symmetry_axis` (`X`, `Y` miroir, ou
  `R180` rotation 180 degres avec echange des equipes : le cas des arenes versus)
- `04_devices.json` devices par ancre (`tile` + `slot`) ou en coordonnees absolues
  (`placement_mode: "WORLD"` + `world_location_cm`, pour les devices non spatiaux de `Zone_Logic`),
  plus `properties` et `bindings`
- `05_props.json` decors par `TILE_ANCHOR` ou `RELATIVE_TO_ACTOR`
- `mirror: false` dans une entree de `04`/`05` la sort de `check-symmetry`. A poser **des deux
  cotes** : un acteur symetrique dont le jumeau est exclu remonte `MIRROR_PARTNER_MISSING`.

Rapports (chacun porte un champ `scope` qui dit ce qu'il ne verifie pas) :
- `06_audit_report.json` chevauchements, gravite, acteurs absents (`audit-scene`)
- `06_navigation_report.json` couloirs trop etroits (`check-navigation`)
- `07_properties_report.json` proprietes ecrites puis relues (`apply-properties`)
- `08_wiring_report.json` cablage relu sur la cible (`wire-devices`)
- `09_verse_report.json` diagnostics et ligne de succes de build (`verse-build`)
- `10_editables.json` table `@editable` -> `actor_label` -> `refPath` (`list-editables`)
- `11_symmetry_report.json` paires miroirs des specs, derive de placement et symetrie de la
  scene posee (`check-symmetry`, `--live`)

Intermediaires calcules : `_compiled_structure.json`, `_compiled_scene.json`, `_placed.json`,
`_verse_files.json`, `_verse_grep.json`, `_verse_written.json`, `_mcp_calls.jsonl`.

## Ressources a charger (au besoin seulement)

- Premier test, ou reprise apres une longue pause : `references/first-run.md` (runbook pas a pas).
- Avant tout appel editeur : `references/mcp-routing.md` (outils prouves, signatures, pieges, protocole timeout).
- Etapes 1, 3, 4 : `references/level-design-patterns.md`.
- Etapes 3 a 7 : `references/spatial-system.md` (grille, ancres, formules, schemas).
- Etapes 5 et 9 : `references/devices-catalog-and-wiring.md`.
- Etapes 6 et 10 : `references/finitions-and-atmosphere.md`.
- Etape 8 : `references/verse-qa-standard.md`.
- Erreur de distance, de collision, de symetrie, ou gros projet : `exemple/map-cases-and-fixes.md`.
- Outil absent de la matrice de routage : `mcp_tools/index.md`, puis `grep` dans le sous-dossier de
  la famille. Ne jamais lire un fichier d'inventaire en entier hors `index.md` et `sommaire.md`.

## Adaptation a la taille du projet

- `<= 8 x 8` tuiles : etapes 3 a 7 en une passe.
- `> 8 x 8` tuiles : decoupage obligatoire en zones de `6 x 6` ou `8 x 8` max, declarees dans `01_gdd.json` (`zones`, `connects_to`, `status`), validees zone par zone. Prefabriques mesures plutot que mur par mur. Pas de PCG ni de duplication dans le MCP : une grande carte = beaucoup d'acteurs poses par lots de 10.

## Pipeline en 10 etapes verrouillees

Interdit de passer a l'etape `N+1` tant que le gatekeeper de l'etape `N` n'est pas vert.

### Etape 0 : Preflight (hors pipeline, a chaque reprise)
- `init --workspace <chemin_absolu> --template blank|1v1_arena|boxfight` : cree le workspace et ses 5 fichiers de spec (`blank` = chaine testable avec des assets moteur seulement).
- `preflight --workspace <...>` : ping, niveau courant, pagination remise a 200, etat de session.
- **Rendre le nom du niveau a l'utilisateur et attendre sa confirmation avant la premiere ecriture.**
- Gatekeeper : `PASSED`, et niveau reconnu par l'utilisateur.

### Etape 1 : Cahier des charges
- Simuler une partie seconde par seconde (spawn, equipement, action, score, victoire). Lister les devices requis (par `actor_label`), les zones, les fichiers Verse.
- Sortie : `01_gdd.json`, avec `requested_assets` (cle, `uefn_path`, `category`, `scale` optionnel).
- `validate-scene` controle la **forme** des 5 fichiers (cles, types, enums, labels uniques, tuiles existantes, references declarees avant usage) : une faute de forme ne doit plus produire un transform faux avec un statut `PASSED`.
- Gatekeeper : chaque mecanique a son device et sa fonction Verse ; `validate-scene` ne remonte plus d'erreur de forme (seul `PALETTE_EMPTY` reste attendu avant l'etape 2).

### Etape 2 : Recherche et mesure des assets
- Chemins : `Asset.find_assets` pour les decors, `Device.ListDeviceAssets` pour les devices. Un chemin invente est une erreur ; un resultat vide ne prouve pas l'absence.
- `measure-palette --dry-run` puis `measure-palette` : chaque asset est pose a `(0, -20000, 5000)`, ses bounds et son `pivot_offset_cm` sont relus, puis il est supprime. Le refus d'un yaw relu non nul evite les mesures faussees.
- Sortie : `02_palette.json` avec `measured` rempli. Tant que la palette est vide, `validate-scene` et `compile-transforms` s'arretent sur `PALETTE_EMPTY`.
- Gatekeeper : 100 % des assets de la palette ont des dimensions strictement positives et `measured`.

### Etape 3 : Plan 2D
- Matrice par etage, `1 case = 512 x 512 x 384 cm`. Legende : `#` sol + murs de perimetre, `.` sol libre, `W` mur interieur, `P` porte, `S1`/`S2` spawns, `O` objectif, `R_*` rampe, `T` tremie, `V` vide.
- Attention : `build-structure` ne pose que les sols et les murs du **perimetre**. Les `W` et `P` interieurs se declarent dans `05_props.json`.
- Sortie : `03_grid.json`.
- Choisir le mode de symetrie : `X` (miroir Nord/Sud), `Y` (miroir Est/Ouest) ou `R180` (rotation
  de 180 degres, les deux moities de la carte s'echangent, avec `S1` <-> `S2`). Le mode doit
  correspondre au plan reel : le gabarit `1v1_arena` (spawns en `[3,1]` et `[4,6]`) n'est
  symetrique qu'en `R180`, le gabarit `boxfight` (S1 au Nord, S2 au Sud) l'est en `X`. En `X`/`Y`,
  `S1` et `S2` sont tenus pour equivalents (une carte peut separer ses equipes sur l'autre axe) :
  verifier a l'oeil que les deux camps sont bien de part et d'autre.
- Gatekeeper : `validate-grid --workspace <...>` (ou `validate-grid <fichier>`) a `0 erreur` (bordure fermee, tremie au-dessus de chaque rampe, symetrie sur le mode declare `X`, `Y` ou `R180`, chemin 2D de `S` a `O`). Un `symmetry_axis` absent ou inconnu avec `symmetric: true` est une erreur (`SYMMETRY_AXIS_UNSUPPORTED`), pas un silence ; une case posee **sur** le plan de symetrie doit etre son propre miroir (`SYMMETRY_ON_AXIS`). `validate-grid` ne controle que la **grille** : la symetrie des devices et des props est verifiee par `check-symmetry` (etape 7), annoncee des cette etape par l'avertissement `SYMMETRY_SCOPE`.

### Etape 4 : Squelette 3D
- `build-structure --dry-run` (le CLI annonce le nombre d'operations), puis `build-structure` : lots de 10 spawns poses par `execute_tool_script`, chaque transform relue.
- `visual-snapshot --workspace <...>` : camera au-dessus de l'arene, PNG ecrit dans `<workspace>/topdown.png` (ou `--output`), puis lecture de l'image.
- Gatekeeper : `PASSED`, `verified` egal au nombre demande, et capture inspectee.
- Limite honnete : la capture n'a pas de grille `A1/B2` dessinee (reperer par X = ligne x 512, Y = colonne x 512) ; le cadrage a pitch -90 n'a jamais ete teste en editeur.

### Etape 5 : Devices de gameplay
- `04_devices.json` : `asset_key` (obligatoire, vers la palette), `actor_label` unique, puis soit `tile` + `slot` (une des 9 ancres) avec `face_towards` et `on_floor`, soit `placement_mode: "WORLD"` + `world_location_cm` pour les devices **non spatiaux** (`Zone_Logic` : granter, score, end_game, HUD) qui ne sont sur aucune tuile de la grille.
- Regles de game design dans `references/level-design-patterns.md`, fiches de devices dans `references/devices-catalog-and-wiring.md`.
- Gatekeeper : chaque device a un chemin issu de `ListDeviceAssets` et une entree mesuree dans la palette.

### Etape 6 : Placement et reglages
- `compile-transforms` (calcul, refuse un asset non mesure et une spec malformee), puis `place-scene` : les devices par `PlaceDevice` avec transform forcee ensuite, les props par lots de 10, chaque transform **relue** (position, yaw et echelle).
- `apply-properties` : `Object.list_properties` -> `set_properties` (`values` en **chaine JSON**) -> `get_properties`. Un nom absent de `list_properties` donne `PROPERTY_NOT_FOUND` avec les noms les plus proches, jamais un nom invente ; une valeur relue differente donne `PROPERTY_MISMATCH`. Rapport : `07_properties_report.json`.
- `wire-devices` : `GetBindingOptions` sur la **source** valide `event` et `function`, `AddEventBinding`, puis relecture par `ListEventBindings` sur la **cible**. Rapport : `08_wiring_report.json`. Sans `bindings` declares : `NO_BINDING_DECLARED`.
- `check-symmetry` : verifie que chaque device a son jumeau dans `03_grid.json` (axe `X`, `Y` ou `R180`), a la meme place dans sa tuile et avec le yaw miroir. Rapport : `11_symmetry_report.json`.
- **Rendu / atmosphere : plafond dur.** Aucun outil d'eclairage dans les 388, aucun materiau par instance posee (`set_material` agit sur l'**asset** : tous ses exemplaires changent), ni feuillage, ni landscape. La seule voie vers de la lumiere est un systeme Niagara emissif, a moitie prouve seulement : pose verifiee, creation jamais appelee. Avant de promettre une ambiance, lire `references/mcp-routing.md` §9 et annoncer ce qui n'est pas atteignable plutot que de le laisser decouvrir a l'utilisateur.
- Gatekeeper : `audit-scene --live` a `0 erreur` (chevauchement <= 5 cm, gravite <= 2 cm, rien d'absent), `check-symmetry` PASSED, `07_properties_report.json` et `08_wiring_report.json` a `PASSED`. Sans `--live`, le rapport porte `gravity_scope` qui dit que la gravite n'est pas controlee : un `PASSED` hors ligne ne prouve ni le pivot ni la hauteur reellement posee.

### Etape 7 : Decors et circulation
- `05_props.json` par `TILE_ANCHOR` ou `RELATIVE_TO_ACTOR` (`reference_actor`, `direction`, `gap_cm`), puis `compile-transforms` et `place-scene` a nouveau.
- `check-navigation` (rapport `06_navigation_report.json`), puis `check-symmetry --live` (rapport `11_symmetry_report.json`, `source: "live"`), puis `visual-snapshot`.
- Gatekeeper : `navigation_errors` vide **et** `check-symmetry --live` a `error_count: 0` avec `source: "live"`. **Dire a l'utilisateur ce que le controle ne couvre pas** : pour la navigation, deux props d'une meme tuile uniquement, sans capsule, sans murs, sans hauteur libre, sans sauts (les seuils 200 cm / 190 cm / 550 cm restent des constantes de conception, pas des mesures). Pour la symetrie, les devices `WORLD` (non spatiaux) ne sont pas compares, et `--live` ne prouve que les transforms relus, pas les materials ni les collisions.

### Etape 8 : Verse
- `verse-scan` (`Verse.ListFiles`) puis `verse-grep --symbols <nom1,nom2>` (`Verse.Grep`) pour chaque signature d'API utilisee, avant d'ecrire. Un resultat vide est un **inconnu**, pas une absence : le rapport le dit.
- Ecrire les fichiers avec les `@editable` nommes comme les `actor_label`. `verse-write` refuse sans `--i-agree-to-modify-project` (`CONSENT_REQUIRED`) : `VerseToolset.WriteFile` est DANGEREUX et n'a jamais ete execute. Avec accord : ecriture puis relecture par `ReadFile` (`read_back_matches`), historique dans `_verse_written.json`.
- `verse-build` : `Session.GetSessionStatus` doit etre `Disconnected` (sinon `SESSION_CONNECTED`), puis `Verse.BuildAll` et recoupement dans `Logs.GetLogEntries {"category": "VerseBuild", ...}`. Rapport : `09_verse_report.json`.
- Gatekeeper : liste de diagnostics sans `Error` **et** ligne de succes recente dans le log.

### Etape 9 : Device Verse et references `@editable`
- Poser le `creative_device` (device Verse : `bIsVerseDevice` dans `ListDeviceAssets`).
- `list-editables` : parse les `@editable` de `<workspace>/verse/*.verse`, distingue les **references d'acteur** (une cible posee est obligatoire) des **parametres** (`logic`, `int`, `float`... : rien a cabler), et produit la table `@editable` -> `actor_label` -> `refPath` dans `10_editables.json`. `--live --device <label>` liste les proprietes du device Verse pose.
- Le cablage automatique des references d'acteurs est **unknown** : l'hypothese `savedActor` n'a jamais pu etre testee (aucun device Verse dans le projet de test).
- Gatekeeper : soit la methode est prouvee sur ce projet avec l'accord de l'utilisateur, soit `10_editables.json` sert au cablage a la main, et le rapport final le dit.

### Etape 10 : Playtest
- `playtest-plan` : imprime l'etat courant, la **demande d'accord** et la sequence, sans rien lancer.
- Ne rien lancer sans accord explicite : `StartSession`, `PushChanges`, `StopSession` sont DANGEREUX et n'ont jamais ete executes ; `GetClientLogEntries` a toujours echoue hors session ; aucune validation d'assets (legalite, publication) n'est accessible par MCP.
- Avec accord : `StartSession` **une fois**, puis `GetSessionStatus` toutes les 10 s jusqu'a un etat stable.
- Gatekeeper : un log client reel contenant les lignes de l'auto-test. Sans lui, ecrire « comportement en jeu non verifie » : une ligne `[STEP]` prouve que le code est arrive jusque la, pas que la barriere ou le timer ont reagi.

## Exemple : d'une phrase a deux JSON

> Dans la tuile `[2, 1, 0]`, placer le spawner de l'Equipe 1 colle au mur Nord. Au centre de la tuile `[2, 2, 0]`, une grande caisse militaire, puis une caisse de munitions a exactement 35 cm devant.

```json
{"devices": [{"actor_label": "Spawner_Team1_01", "asset_key": "player_spawner",
  "tile": [2, 1, 0], "slot": "NORTH_EDGE", "face_towards": "SOUTH", "on_floor": true,
  "properties": {"playerTeam": {"teamType": "TeamIndex", "teamIndex": 1}}}]}
```
```json
{"props": [
  {"actor_label": "Cover_Crate_Main", "asset_key": "prop_military_crate_large",
   "placement_mode": "TILE_ANCHOR", "tile": [2, 2, 0], "slot": "CENTER",
   "face_towards": "SOUTH", "snap_to_floor": true},
  {"actor_label": "Ammo_Box_Front", "asset_key": "prop_ammo_box_small",
   "placement_mode": "RELATIVE_TO_ACTOR", "reference_actor": "Cover_Crate_Main",
   "direction": "IN_FRONT_OF", "gap_cm": 35.0, "face_towards": "SOUTH", "snap_to_floor": true}]}
```

Un rapport d'audit en echec a cette forme (champs reels du CLI, `06_audit_report.json`) :
```json
{"status": "FAILED", "source": "live", "error_count": 1,
 "overlap_errors": [{"type": "OVERLAP_ERROR", "actor_a": "Cover_Crate_Main",
   "actor_b": "Pillar_Decor_01", "penetration_cm": 28.4, "tile": [2, 2, 0],
   "suggestion": "Placer Pillar_Decor_01 en RELATIVE_TO_ACTOR avec gap_cm >= 15."}],
 "gravity_errors": [], "scene_errors": [],
 "other_report": "passages etroits : 06_navigation_report.json (check-navigation)"}
```
Correction : deplacer ou supprimer `Pillar_Decor_01` dans `05_props.json`, puis relancer `compile-transforms`, `place-scene`, `audit-scene --live`, `check-navigation`.

## Proprete du poste de travail

- Tag de la map : `UEFN_MAP_TAG` (defaut `UEFNMAP`). Tous les acteurs poses le portent.
- `cleanup` supprime **tous** les acteurs de ce tag. Le lancer seulement apres avoir demande a l'utilisateur si le niveau courant ne contient pas deja des acteurs a ce tag.
- Rien n'est sauvegarde : fermer le niveau sans enregistrer annule la construction. Le dire a l'utilisateur a la fin.

## Checklist avant d'annoncer la carte terminee

- [ ] `preflight` PASSED et niveau confirme par l'utilisateur.
- [ ] `validate-scene` PASSED (forme et coherence croisee des 5 specs).
- [ ] Les 5 specs et les rapports `06` a `11` existent dans le workspace et sont a jour.
- [ ] 100 % des assets de la palette sont mesures (`measured`, dimensions > 0).
- [ ] Aucune coordonnee brute inventee : tout vient de `compile-transforms`.
- [ ] `audit-scene --live` : 0 `OVERLAP_ERROR`, 0 `GRAVITY_ERROR`, 0 `scene_errors`, et `source: "live"` dans le rapport (`not_live` veut dire qu'aucun bounds n'a ete relu).
- [ ] `check-navigation` : 0 `CORRIDOR_TOO_NARROW`, avec son perimetre annonce.
- [ ] `check-symmetry --live` : 0 `SPEC_ASYMMETRY`, 0 `MIRROR_PARTNER_MISSING`, 0 `TRANSFORM_DRIFT`, 0 `SCENE_ASYMMETRY`, et `source: "live"` (`11_symmetry_report.json`) ; chaque `mirror: false` assume et annonce.
- [ ] `apply-properties` : chaque valeur ecrite relue (`07_properties_report.json` PASSED).
- [ ] `wire-devices` : cablage relu par `ListEventBindings` sur la cible (`08_wiring_report.json` PASSED).
- [ ] `verse-build` : aucun diagnostic d'erreur **et** ligne de succes recente (`09_verse_report.json`).
- [ ] `list-editables` : chaque reference d'acteur a son `refPath`, ou le cablage manuel est annonce.
- [ ] Rapport final qui separe ce qui est prouve, ce qui est inconnu, et ce qui n'a pas ete lance (session, sauvegarde, publication).
