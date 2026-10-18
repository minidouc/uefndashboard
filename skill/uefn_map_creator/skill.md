---
name: uefn-map-creator
description: Orchestre la conception, la construction 3D, le code Verse, le cablage et la verification complete d'une carte UEFN (Unreal Editor for Fortnite) a partir d'une simple invite. Utiliser ce skill des que l'utilisateur demande de creer une map Fortnite (1v1, Box Fight, Zone Wars, Red vs Blue, Tycoon, Deathrun, RPG, Battle Royale), d'automatiser le level design via Python Bridge et MCP, ou de corriger les distances et collisions d'une scene.
---

# UEFN Autonomous Map Builder (`/uefn-map-builder`)

## Goal
Transformer une simple invite utilisateur en une carte UEFN complete, jouable, sans erreur de distance ni de collision, avec son code Verse compile et ses appareils cables, en executant une boucle autonome stricte en **10 etapes verrouillees**.

## Gestion de l'Etat sur Disque et Ressources du Skill
Ne conserve jamais l'architecture de la carte uniquement dans la memoire de conversation. Cree et mets a jour un dossier `workspace_map/` dans le repertoire de travail avec les 6 fichiers d'etat :
- `workspace_map/01_gdd.json` (Cahier des charges et simulation)
- `workspace_map/02_palette.json` (Catalogue des assets et dimensions 3D mesurees)
- `workspace_map/03_grid.json` (Matrice 2D en tuiles Fortnite par etage)
- `workspace_map/04_devices.json` (Placement des appareils par ancre de tuile)
- `workspace_map/05_props.json` (Placement des decors par distance relative)
- `workspace_map/06_audit_report.json` (Dernier rapport de collision, gravite et circulation)

Charge les ressources auxiliaires du skill uniquement lorsque l'etape l'exige :
- Avant les Etapes 3, 5 et 6 : Lis `./references/spatial-system.md`.
- Avant d'appeler le Bridge ou le MCP : Lis `./references/bridge-vs-mcp-routing.md`.
- Avant les Etapes 8 et 9 : Lis `./references/verse-qa-standard.md`.
- En cas d'erreur de distance, de collision ou pour un gros projet : Consulte `./examples/map-cases-and-fixes.md`.
- Pour tous les calculs 3D et audits : Execute `./scripts/uefn_spatial_cli.py`.

## Adaptation Automatique a la Taille du Projet (Scaling Strategy)

1. **Petits Projets (`<= 8 x 8` tuiles : 1v1, Box Fight, Aim Trainer, Micro-Arena)** :
   - Executer les Etapes 3 a 7 sur l'ensemble de la carte en une seule passe.
2. **Projets Moyens et Gros (`> 8 x 8` tuiles : Red vs Blue, Zone Wars, Tycoon, RPG, Mini-BR)** :
   - **Decoupage en Zones (Chunking obligatoire)** : Dans `01_gdd.json`, diviser la carte en zones independantes de `6 x 6` ou `8 x 8` tuiles maximum (ex. `Zone_A_SpawnTeam1`, `Zone_B_CenterArena`, `Zone_C_Shop`).
   - **Priorite aux Prefabriques** : Pour les batiments complexes, privilegier les Prefabriques Fortnite entiers mesures dans `02_palette.json` plutot que de poser chaque mur individuellement.
   - Executer et valider les Etapes 3 a 7 **zone par zone** (verrouiller la `Zone_A` avec `0 erreur` avant de commencer la `Zone_B`).

   ## Pipeline d'Execution en 10 Etapes Verrouillees

Il est formellement interdit de passer a l'etape `N+1` tant que le **Gatekeeper** de l'etape `N` n'est pas valide avec `0 erreur`.

### Etape 1 : Simulation Papier et Cahier des Charges
- **Entree** : Invite initiale de l'utilisateur.
- **Action** : Simuler une partie complete seconde par seconde (spawn, equipement, action, score, victoire). Rediger la structure des zones, la liste des appareils Creatif requis et l'architecture des fichiers Verse.
- **Sortie** : `workspace_map/01_gdd.json`.
- **Gatekeeper** : Relire `01_gdd.json` et verifier que chaque mecanique de jeu possede son appareil Creatif associe et sa fonction Verse.

### Etape 2 : Selection et Profilage 3D des Assets
- **Entree** : `workspace_map/01_gdd.json`.
- **Action** : Chercher les assets dans UEFN via le Bridge (`assets.search`), puis executer `python ./scripts/uefn_spatial_cli.py measure-palette` pour les instancier temporairement en `(0, 0, 0)`, mesurer leur boite englobante exacte (`get_actor_bounds`) et leur decalage de pivot (`pivot_offset_cm`).
- **Sortie** : `workspace_map/02_palette.json`.
- **Gatekeeper** : Verifier que 100% des assets choisis possedent des dimensions `[X, Y, Z]` strictement positives dans `02_palette.json`.

### Etape 3 : Dessin du Plan 2D en Tuiles
- **Entree** : `01_gdd.json`, `02_palette.json` et `./references/spatial-system.md`.
- **Action** : Dessiner la topologie etage par etage sous forme de matrice 2D ou `1 case = 1 tuile (512 x 512 x 384 cm)` avec la legende (`#` Mur, `.` Sol, `P` Porte, `S1`/`S2` Spawns, `O` Objectif, `T` Tremie d'escalier).
- **Sortie** : `workspace_map/03_grid.json`.
- **Gatekeeper** : Executer `python ./scripts/uefn_spatial_cli.py validate-grid workspace_map/03_grid.json` (controle de fermeture des murs, symetrie, tremies d'escaliers et chemin 2D entre `S` et `O`). Doit retourner `0 erreur`.

### Etape 4 : Construction du Squelette 3D
- **Entree** : `workspace_map/03_grid.json` et `workspace_map/02_palette.json`.
- **Action** : Executer `python ./scripts/uefn_spatial_cli.py build-structure` pour placer les sols, murs et escaliers en un seul appel `batch.exec` via le Bridge (avec conversion `XYZ <-> LUF` et masquage temporaire du plafond).
- **Sortie** : Capture orthographique de dessus (`Pitch = -90`) avec grille `A1, B2...` via `python ./scripts/uefn_spatial_cli.py visual-snapshot`.
- **Gatekeeper** : Inspecter visuellement la capture 2D quadrillee pour confirmer qu'aucun mur, porte ou escalier n'est tourne a l'envers.

### Etape 5 : Placement des Appareils de Gameplay (Devices)
- **Entree** : `01_gdd.json`, `03_grid.json` et `./references/spatial-system.md`.
- **Action** : Definir la position de chaque appareil uniquement par indice de tuile `[TileX, TileY, TileZ]` et ancre (`CENTER`, `NORTH_EDGE`, `CORNER_NE`, etc.) avec `"on_floor": true` et un `actor_label` explicite (ex. `Spawner_Team1_01`). Instancier via `ValkyrieToolset.DeviceToolset` ou le Bridge.
- **Sortie** : `workspace_map/04_devices.json`.
- **Gatekeeper** : Executer `python ./scripts/uefn_spatial_cli.py audit-scene` et verifier qu'aucun appareil ne flotte ni ne chevauche un mur (`0 erreur`).

### Etape 6 : Habillage et Decoration par Distance Relative (Props)
- **Entree** : `02_palette.json`, `03_grid.json`, `04_devices.json` et `./examples/map-cases-and-fixes.md`.
- **Action** : Definir les decors et couvertures dans `05_props.json` uniquement par placement relatif (`reference_actor`, `direction`, `gap_cm`, `face_towards`, `snap_to_floor`). Executer `python ./scripts/uefn_spatial_cli.py compile-transforms` pour calculer les positions par boite englobante et les placer en batch.
- **Sortie** : `workspace_map/05_props.json` et `workspace_map/06_audit_report.json`.
- **Gatekeeper** : Executer `python ./scripts/uefn_spatial_cli.py audit-scene`. Tant que `06_audit_report.json` contient un `OVERLAP_ERROR` (`> 5 cm`) ou un `GRAVITY_ERROR` (`> 2 cm`), ajuster `gap_cm` ou supprimer l'objet fautif et relancer jusqu'a obtenir `0 erreur`.

### Etape 7 : Test du Fil d'Ariane (Jouabilite et Circulation)
- **Entree** : Scene 3D complete et `workspace_map/06_audit_report.json`.
- **Action** : Executer `python ./scripts/uefn_spatial_cli.py check-navigation` pour simuler le passage d'une capsule joueur (`rayon = 42 cm`, `hauteur = 192 cm`) depuis chaque `Player Spawner` vers toutes les portes `P` et objectifs `O`.
- **Sortie** : Mise a jour de `workspace_map/06_audit_report.json`.
- **Gatekeeper** : Aucun passage libre ne doit etre inferieur a `100 cm` de large (`200 cm` de haut) et aucun saut ne doit depasser `190 cm` de haut (`550 cm` de long). Si bloque, corriger `05_props.json` a l'Etape 6.

### Etape 8 : Ecriture et Compilation du Code Verse
- **Entree** : `01_gdd.json`, `04_devices.json` et `./references/verse-qa-standard.md`.
- **Action** : Rediger les fichiers `.verse` du projet avec les proprietes `@editable` portant le meme nom que les `actor_label` de `04_devices.json`. Integrer la methode `RunSelfTest()` dans `OnBegin()` qui imprime `[ASSERT_OK]` ou `[ASSERT_FAIL]`.
- **Sortie** : Fichiers `.verse` compiles via `ValkyrieToolset.VerseToolset` (*Build Verse Code*).
- **Gatekeeper** : Le compilateur Verse doit retourner exactement `0 Error`.

### Etape 9 : Placement du Device Verse et Cablage `@editable`
- **Entree** : Device Verse compile et `workspace_map/04_devices.json`.
- **Action** : Instancier le `creative_device` Verse dans la scene et cabler automatiquement chaque reference `@editable` vers les `actor_label` correspondants via `DeviceToolset` ou l'injection `.t3d` du Bridge (`verse.set_property` avec `is_object_ref=True`).
- **Sortie** : Appareil Verse cable dans le niveau.
- **Gatekeeper** : Verifier par inspection que 100% des proprietes `@editable` obligatoires sont assignees (aucune reference a `None`).

### Etape 10 : Playtest en Session Fortnite (PIC) et Validation Finale
- **Entree** : Niveau complet assemble et cable.
- **Action** : Reafficher le plafond via le Bridge. Lancer la session *Play-in-Client* (ou *Push Verse Changes*) via `ValkyrieToolset.SessionToolset`, lire les logs du client Fortnite, puis executer `validate_folder` via le Bridge Python.
- **Sortie** : Rapport de validation finale UEFN.
- **Gatekeeper** : Les logs client doivent contenir `[ASSERT_OK]` sans aucun `[ASSERT_FAIL]`, et `validate_folder` doit confirmer `0 Asset Error`.

## Exemples Concrets (Few-Shot Input / Output)

### Exemple 1 : Traduction d'une demande en Placement par Ancre et Distance Relative
**Entree (Extrait du GDD) :**
> Dans la tuile `[2, 1, 0]`, placer le spawner de l'Equipe 1 colle au mur Nord. Placer une grande caisse militaire au centre de la tuile `[2, 2, 0]`, puis poser une boite de munitions par terre a exactement 35 cm devant cette caisse.

**Sortie JSON attendue dans `04_devices.json` et `05_props.json` :**
```json
{
  "devices": [
    {
      "actor_label": "Spawner_Team1_01",
      "device_class": "player_spawner_device",
      "tile": [2, 1, 0],
      "slot": "NORTH_EDGE",
      "face_towards": "SOUTH",
      "on_floor": true
    }
  ],
  "props": [
    {
      "actor_label": "Cover_Crate_Main",
      "asset_key": "prop_military_crate_large",
      "placement_mode": "TILE_ANCHOR",
      "tile": [2, 2, 0],
      "slot": "CENTER",
      "face_towards": "SOUTH",
      "snap_to_floor": true
    },
    {
      "actor_label": "Ammo_Box_Front",
      "asset_key": "prop_ammo_box_small",
      "placement_mode": "RELATIVE_TO_ACTOR",
      "reference_actor": "Cover_Crate_Main",
      "direction": "IN_FRONT_OF",
      "gap_cm": 35.0,
      "face_towards": "SOUTH",
      "snap_to_floor": true
    }
  ]
}

{
  "status": "FAILED",
  "error_count": 2,
  "errors": [
    {
      "type": "OVERLAP_ERROR",
      "actor_a": "Cover_Crate_Main",
      "actor_b": "Pillar_Decor_01",
      "penetration_cm": 28.4,
      "tile": [2, 2, 0]
    },
    {
      "type": "NAV_BLOCKED",
      "from": "Spawner_Team1_01",
      "to": "Arena_Center",
      "free_width_cm": 68.0,
      "required_width_cm": 100.0,
      "blocking_actor": "Pillar_Decor_01"
    }
  ]
}

Sortie (Action corrective immediate de l'Agent) :

Dans workspace_map/05_props.json, deplacer Pillar_Decor_01 sur l'ancre "slot": "CORNER_NW" de la tuile [2, 2, 0] (ou le supprimer s'il est purement decoratif) afin d'eliminer le chevauchement de 28.4 cm et de liberer plus de 100 cm de passage pour le joueur.

Re-executer python ./scripts/uefn_spatial_cli.py compile-transforms puis audit-scene et check-navigation jusqu'a obtenir "error_count": 0.

Verification Checklist Finale
Avant d'annoncer a l'utilisateur que la carte est terminee, verifie que chaque point est valide :

[ ] Les 6 fichiers JSON dans workspace_map/ sont crees et a jour.

[ ] Aucune coordonnee brute (X, Y, Z) n'a ete ecrite manuellement par le LLM.

[ ] audit-scene confirme 0 OVERLAP_ERROR et 0 GRAVITY_ERROR.

[ ] check-navigation confirme un couloir libre >= 100 cm depuis chaque spawner.

[ ] Le code Verse compile avec 0 Error et toutes les proprietes @editable sont cablees.

[ ] Les logs de la session Play-in-Client affichent [ASSERT_OK] et validate_folder retourne 0 Asset Error.
