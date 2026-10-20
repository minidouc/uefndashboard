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
5. Tout etat est sur disque dans `workspace_map/`, jamais seulement dans la conversation.
6. Signaler a l'utilisateur, dans le rapport final, ce qui n'a pas ete verifie.

## Pilotage

Tout passe par le CLI `script/uefn_spatial_cli.py` (client MCP `script/mcp_client.py`). Ne pas recoder le protocole.
Il n'existe **pas** de Bridge Python, pas de `batch.exec`, pas d'`editor.undo`, pas de `validate_folder` : les mentions de ces commandes dans d'anciennes notes sont caduques.

```bash
python script/uefn_spatial_cli.py <commande> --workspace workspace_map [--dry-run]
```
Codes retour : `0` PASSED, `1` FAILED, `2` editeur injoignable (rien n'a ete execute), `3` timeout (etat inconnu, relire avant de rejouer).
Chaque appel est journalise dans `workspace_map/_mcp_calls.jsonl`.

## Fichiers d'etat (`workspace_map/`)

- `01_gdd.json` cahier des charges et simulation
- `02_palette.json` assets, chemins MCP, tailles et pivots **mesures**
- `03_grid.json` matrice 2D par etage
- `04_devices.json` devices par tuile et ancre
- `05_props.json` decors par ancre ou par distance relative
- `06_audit_report.json` dernier rapport de collision, gravite et circulation
- `_compiled_structure.json`, `_compiled_scene.json`, `_placed.json` intermediaires calcules

## Ressources a charger (au besoin seulement)

- Avant tout appel editeur : `references/mcp-routing.md` (outils prouves, signatures, pieges, protocole timeout).
- Etapes 1, 3, 4 : `references/level-design-patterns.md`.
- Etapes 3 a 7 : `references/spatial-system.md` (grille, ancres, formules, schemas).
- Etapes 5 et 9 : `references/devices-catalog-and-wiring.md`.
- Etapes 6 et 10 : `references/finitions-and-atmosphere.md`.
- Etape 8 : `references/verse-qa-standard.md`.
- Erreur de distance, de collision, ou gros projet : `exemple/map-cases-and-fixes.md`.
- Outil absent de la matrice de routage : `mcp_tools/index.md`, puis `grep` dans le sous-dossier de
  la famille. Ne jamais lire un fichier d'inventaire en entier hors `index.md` et `sommaire.md`.

## Adaptation a la taille du projet

- `<= 8 x 8` tuiles : etapes 3 a 7 en une passe.
- `> 8 x 8` tuiles : decoupage obligatoire en zones de `6 x 6` ou `8 x 8` max, declarees dans `01_gdd.json` (`zones`, `connects_to`, `status`), validees zone par zone. Prefabriques mesures plutot que mur par mur. Pas de PCG ni de duplication dans le MCP : une grande carte = beaucoup d'acteurs poses par lots de 10.

## Pipeline en 10 etapes verrouillees

Interdit de passer a l'etape `N+1` tant que le gatekeeper de l'etape `N` n'est pas vert.

### Etape 0 : Preflight (hors pipeline, a chaque reprise)
- `python script/uefn_spatial_cli.py preflight` : ping, niveau courant, pagination remise a 200, etat de session.
- **Rendre le nom du niveau a l'utilisateur et attendre sa confirmation avant la premiere ecriture.**
- Gatekeeper : `PASSED`, et niveau reconnu par l'utilisateur.

### Etape 1 : Cahier des charges
- Simuler une partie seconde par seconde (spawn, equipement, action, score, victoire). Lister les devices requis (par `actor_label`), les zones, les fichiers Verse.
- Sortie : `01_gdd.json`, avec `requested_assets` (cle, `uefn_path`, `category`).
- Gatekeeper : chaque mecanique a son device et sa fonction Verse.

### Etape 2 : Recherche et mesure des assets
- Chemins : `Asset.find_assets` pour les decors, `Device.ListDeviceAssets` pour les devices. Un chemin invente est une erreur ; un resultat vide ne prouve pas l'absence.
- `measure-palette --dry-run` puis `measure-palette` : chaque asset est pose a `(0, -20000, 5000)`, ses bounds et son `pivot_offset_cm` sont relus, puis il est supprime. Le refus d'un yaw relu non nul evite les mesures faussees.
- Sortie : `02_palette.json` avec `measured` rempli.
- Gatekeeper : 100 % des assets de la palette ont des dimensions strictement positives et `measured`.

### Etape 3 : Plan 2D
- Matrice par etage, `1 case = 512 x 512 x 384 cm`. Legende : `#` sol + murs de perimetre, `.` sol libre, `W` mur interieur, `P` porte, `S1`/`S2` spawns, `O` objectif, `R_*` rampe, `T` tremie, `V` vide.
- Attention : `build-structure` ne pose que les sols et les murs du **perimetre**. Les `W` et `P` interieurs se declarent dans `05_props.json`.
- Sortie : `03_grid.json`.
- Gatekeeper : `validate-grid workspace_map/03_grid.json` a `0 erreur` (bordure fermee, tremie au-dessus de chaque rampe, symetrie, chemin 2D de `S` a `O`).

### Etape 4 : Squelette 3D
- `build-structure --dry-run` (le CLI annonce le nombre d'operations), puis `build-structure` : lots de 10 spawns poses par `execute_tool_script`, chaque transform relue.
- `visual-snapshot --output workspace_map/topdown.png` : camera au-dessus de l'arene, puis lecture de l'image.
- Gatekeeper : `PASSED`, `verified` egal au nombre demande, et capture inspectee.
- Limite honnete : la capture n'a pas de grille `A1/B2` dessinee (reperer par X = ligne x 512, Y = colonne x 512) ; le cadrage a pitch -90 n'a jamais ete teste en editeur.

### Etape 5 : Devices de gameplay
- `04_devices.json` : `asset_key` (obligatoire, vers la palette), `actor_label` unique, `tile`, `slot` parmi les 9 ancres, `face_towards`, `on_floor`.
- Regles de game design dans `references/level-design-patterns.md`, fiches de devices dans `references/devices-catalog-and-wiring.md`.
- Gatekeeper : chaque device a un chemin issu de `ListDeviceAssets` et une entree mesuree dans la palette.

### Etape 6 : Placement et reglages
- `compile-transforms` (calcul, refuse un asset non mesure), puis `place-scene` : les devices par `PlaceDevice` avec transform forcee ensuite, les props par lots de 10, chaque transform relue.
- Reglages (`teamIndex`, phases, textes) : `Object.list_properties` puis `set_properties` (`values` en **chaine JSON**), toujours suivis de `get_properties`. Le champ `properties` de `04_devices.json` est une liste de travail, pas une application automatique.
- Cablage : `GetBindingOptions`, `AddEventBinding`, relecture par `ListEventBindings` sur la **cible**.
- Gatekeeper : `audit-scene --live` a `0 erreur` (chevauchement <= 5 cm, gravite <= 2 cm, rien d'absent).

### Etape 7 : Decors et circulation
- `05_props.json` par `TILE_ANCHOR` ou `RELATIVE_TO_ACTOR` (`reference_actor`, `direction`, `gap_cm`), puis `compile-transforms` et `place-scene` a nouveau.
- `check-navigation`, puis `visual-snapshot`.
- Gatekeeper : `navigation_errors` vide. **Dire a l'utilisateur ce que le controle ne couvre pas** : deux props d'une meme tuile uniquement, sans capsule, sans murs, sans hauteur libre, sans sauts. Les seuils 200 cm / 190 cm / 550 cm restent des constantes de conception, pas des mesures.

### Etape 8 : Verse
- Verifier chaque signature d'API dans les digests (`Verse.ListFiles`, `Verse.Grep`, `Verse.ReadFile`) avant d'ecrire.
- Ecrire les fichiers avec les `@editable` nommes comme les `actor_label`. `VerseToolset.WriteFile` est dangerous et non teste : proposer le code, ou demander l'accord, puis relire avec `ReadFile`.
- Compiler : `Session.GetSessionStatus` doit etre `Disconnected`, puis `Verse.BuildAll` et recoupement dans `Logs.GetLogEntries {"category": "VerseBuild", ...}`.
- Gatekeeper : liste de diagnostics vide **et** ligne de succes recente dans le log.

### Etape 9 : Device Verse et references `@editable`
- Poser le `creative_device` (device Verse : `bIsVerseDevice` dans `ListDeviceAssets`).
- Le cablage automatique des references d'acteurs est **unknown** : l'hypothese `savedActor` n'a jamais pu etre testee (aucun device Verse dans le projet de test).
- Gatekeeper : soit la methode est prouvee sur ce projet avec l'accord de l'utilisateur, soit produire la liste `@editable` -> `actor_label` pour un cablage a la main, et le dire.

### Etape 10 : Playtest
- Ne rien lancer sans accord explicite : `StartSession`, `PushChanges`, `StopSession` sont dangerous et n'ont jamais ete executes ; `GetClientLogEntries` a toujours echoue hors session ; aucune validation d'assets n'est accessible par MCP.
- Avec accord : `StartSession` **une fois**, puis `GetSessionStatus` toutes les 10 s jusqu'a un etat stable. Procedura detaillee dans `references/finitions-and-atmosphere.md`.
- Gatekeeper : un log client reel contenant les lignes de l'auto-test. Sans lui, ecrire « comportement en jeu non verifie ».

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

Un rapport d'audit en echec a cette forme (champs reels du CLI) :
```json
{"status": "FAILED", "error_count": 1,
 "overlap_errors": [{"type": "OVERLAP_ERROR", "actor_a": "Cover_Crate_Main",
   "actor_b": "Pillar_Decor_01", "penetration_cm": 28.4, "tile": [2, 2, 0],
   "suggestion": "Placer Pillar_Decor_01 en RELATIVE_TO_ACTOR avec gap_cm >= 15."}],
 "gravity_errors": [], "scene_errors": [], "navigation_errors": []}
```
Correction : deplacer ou supprimer `Pillar_Decor_01` dans `05_props.json`, puis relancer `compile-transforms`, `place-scene`, `audit-scene --live`, `check-navigation`.

## Proprete du poste de travail

- Tag de la map : `UEFN_MAP_TAG` (defaut `UEFNMAP`). Tous les acteurs poses le portent.
- `cleanup` supprime **tous** les acteurs de ce tag. Le lancer seulement apres avoir demande a l'utilisateur si le niveau courant ne contient pas deja des acteurs a ce tag.
- Rien n'est sauvegarde : fermer le niveau sans enregistrer annule la construction. Le dire a l'utilisateur a la fin.

## Checklist avant d'annoncer la carte terminee

- [ ] `preflight` PASSED et niveau confirme par l'utilisateur.
- [ ] Les 6 fichiers de `workspace_map/` existent et sont a jour.
- [ ] 100 % des assets de la palette sont mesures (`measured`, dimensions > 0).
- [ ] Aucune coordonnee brute inventee : tout vient de `compile-transforms`.
- [ ] `audit-scene --live` : 0 `OVERLAP_ERROR`, 0 `GRAVITY_ERROR`, 0 `scene_errors`.
- [ ] `check-navigation` : 0 `CORRIDOR_TOO_NARROW`, avec son perimetre annonce.
- [ ] Chaque valeur ecrite par `set_properties` a ete relue par `get_properties`.
- [ ] `BuildAll` sans diagnostic d'erreur, recoupe dans les logs `VerseBuild`.
- [ ] Cablage verifie par `ListEventBindings` sur la device cible.
- [ ] Rapport final qui separe ce qui est prouve, ce qui est inconnu, et ce qui n'a pas ete lance (session, sauvegarde, publication).
