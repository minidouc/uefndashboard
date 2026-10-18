# Systeme Spatial UEFN : Grille, Ancres, Relations et Schemas JSON

## 1. Constantes Physiques et Metriques Fortnite

- `TILE_SIZE_XY` : `512.0 cm` (Largeur X et Profondeur Y d'une tuile standard)
- `TILE_SIZE_Z` : `384.0 cm` (Hauteur Z d'un etage standard)
- `PLAYER_CAPSULE_RADIUS` : `42.0 cm` (Diametre total = `84.0 cm`)
- `PLAYER_CAPSULE_HEIGHT` : `192.0 cm`
- `MIN_CORRIDOR_WIDTH` : `100.0 cm` (Largeur libre minimale obligatoire entre deux boites de collision)
- `MIN_CORRIDOR_HEIGHT` : `200.0 cm` (Hauteur libre minimale obligatoire sous plafond ou arche)
- `MAX_JUMP_HEIGHT` : `190.0 cm` (Hauteur maximale d'un saut sans accessoire)
- `MAX_SPRINT_JUMP_LENGTH` : `550.0 cm` (Distance horizontale maximale d'un saut en sprint)
- `MAX_OVERLAP_TOLERANCE` : `5.0 cm` (Au-dela de 5 cm de penetration, erreur critique `OVERLAP_ERROR`)
- `MAX_GRAVITY_TOLERANCE` : `2.0 cm` (Tout objet avec `snap_to_floor: true` doit etre a `[-2.0 cm, +2.0 cm]` du sol)

## 2. Repere Cartesien XYZ vs Scene Graph LUF

- **API Python `unreal.*` (XYZ)** :
  - `+X` = Nord (`NORTH` / `FORWARD`)
  - `-X` = Sud (`SOUTH` / `BACKWARD`)
  - `+Y` = Est (`EAST` / `RIGHT`)
  - `-Y` = Ouest (`WEST` / `LEFT`)
  - `+Z` = Haut (`UP`)
  - `-Z` = Bas (`DOWN`)
- **Scene Graph UEFN / SpatialMath Verse (LUF)** :
  - Axe 1 = `Left` (`-Y` en XYZ)
  - Axe 2 = `Up` (`+Z` en XYZ)
  - Axe 3 = `Forward` (`+X` en XYZ)
- **Regle stricte** : Dans les fichiers JSON (`03_grid.json`, `04_devices.json`, `05_props.json`), utiliser uniquement les directions cardinales (`NORTH`, `SOUTH`, `EAST`, `WEST`) et les relations (`IN_FRONT_OF`, `BEHIND`, `LEFT_OF`, `RIGHT_OF`, `ON_TOP_OF`). Le script `uefn_spatial_cli.py` effectue la conversion mathematique.

## 3. Les 9 Ancres de Tuile (`slot`)

Pour une tuile d'indice `[tx, ty, tz]` dont l'origine Sud-Ouest est `(Bx = tx * 512.0, By = ty * 512.0, Bz = tz * 384.0)` et un acteur de demi-taille `(hx = size_x / 2.0, hy = size_y / 2.0)` :

- `CENTER` : `(Bx + 256.0, By + 256.0, Bz)`
- `NORTH_EDGE` : `(Bx + 512.0 - hx, By + 256.0, Bz)`
- `SOUTH_EDGE` : `(Bx + hx, By + 256.0, Bz)`
- `EAST_EDGE` : `(Bx + 256.0, By + 512.0 - hy, Bz)`
- `WEST_EDGE` : `(Bx + 256.0, By + hy, Bz)`
- `CORNER_NE` : `(Bx + 512.0 - hx, By + 512.0 - hy, Bz)`
- `CORNER_NW` : `(Bx + 512.0 - hx, By + hy, Bz)`
- `CORNER_SE` : `(Bx + hx, By + 512.0 - hy, Bz)`
- `CORNER_SW` : `(Bx + hx, By + hy, Bz)`

## 4. Orientations Autorisees (`face_towards`)

- `NORTH` : `Yaw = 0.0` (Regarde vers `+X`)
- `EAST` : `Yaw = 90.0` (Regarde vers `+Y`)
- `SOUTH` : `Yaw = 180.0` (Regarde vers `-X`)
- `WEST` : `Yaw = 270.0` (Regarde vers `-Y`)
- `CENTER` : Calcule automatiquement l'angle `atan2` vers le centre de la tuile ou de l'arene.
- `<actor_label>` : Calcule automatiquement l'angle `atan2` pour regarder vers l'acteur cible nomme.

## 5. Formule de Placement Relatif (`RELATIVE_TO_ACTOR`)

Lorsqu'un acteur enfant `B` (demi-taille `Half_B`) est place par rapport a un acteur parent `A` (centre `Center_A`, demi-taille `Half_A`, orientation `Yaw_A`) avec un ecart `gap_cm` :

1. Calculer le vecteur unitaire local `U` selon `direction` :
   - `IN_FRONT_OF` : Vecteur avant de `A` selon son `Yaw_A`
   - `BEHIND` : Vecteur arriere de `A` selon son `Yaw_A`
   - `RIGHT_OF` : Vecteur droit de `A` selon son `Yaw_A`
   - `LEFT_OF` : Vecteur gauche de `A` selon son `Yaw_A`
   - `ON_TOP_OF` : Vecteur vertical `(0, 0, +1)`
2. Calculer la distance centre-a-centre sur l'axe `U` :
   - `Distance = Half_A(U) + gap_cm + Half_B(U)`
3. Calculer la position finale en soustrayant le decalage du point de pivot `PivotOffset_B` :
   - `SpawnLocation_B = Center_A + (Distance * U) - PivotOffset_B`

## 6. Regle des Escaliers et Tremies (`OPEN_STAIRWELL`)

- Un escalier ou une rampe place dans la tuile `[tx, ty, tz]` monte de `tz * 384.0` vers `(tz + 1) * 384.0`.
- La cellule située exactement au-dessus en `[tx, ty, tz + 1]` dans `03_grid.json` doit obligatoirement porter le code `T` (`OPEN_STAIRWELL`).
- Le générateur de structure ne pose jamais de dalle de sol sur une case `T`, garantissant `384.0 cm` de hauteur libre pour la tete du joueur.

## 7. Schemas JSON Officiels (`workspace_map/`)

### Schema `01_gdd.json`
```json
{
  "project_name": "string",
  "game_mode": "1v1 | box_fight | zone_wars | rvb | tycoon | deathrun | rpg | mini_br",
  "scale_category": "SMALL | MEDIUM | LARGE",
  "grid_dimensions_tiles": [6, 6, 2],
  "zones": [
    {
      "zone_id": "Zone_Main",
      "bounds_tiles": {"min": [0, 0, 0], "max": [5, 5, 1]},
      "purpose": "Combat Arena"
    }
  ],
  "gameplay_timeline_sec": [
    {"time": 0, "event": "Player spawns on Spawner_Team1_01"},
    {"time": 1, "event": "Granter_Loadout_01 grants weapons"},
    {"time": 5, "event": "Barrier_Start_01 disables"}
  ],
  "required_devices": [
    {"actor_label": "Spawner_Team1_01", "device_class": "player_spawner_device"},
    {"actor_label": "Granter_Loadout_01", "device_class": "item_granter_device"},
    {"actor_label": "Barrier_Start_01", "device_class": "barrier_device"}
  ],
  "verse_modules": [
    {
      "file_name": "game_manager_device.verse",
      "class_name": "game_manager_device",
      "responsibilities": ["Handle round start", "Grant loadout", "Run self test"]
    }
  ]
}
```

### Schema `02_palette.json`
```json
{
  "assets": {
    "floor_basic": {
      "uefn_path": "/Game/Athena/Environments/Blueprints/Floors/BP_Floor.BP_Floor",
      "category": "STRUCTURE_FLOOR",
      "size_cm": [512.0, 512.0, 16.0],
      "pivot_offset_cm": [0.0, 0.0, 0.0]
    },
    "wall_basic": {
      "uefn_path": "/Game/Athena/Environments/Blueprints/Walls/BP_Wall.BP_Wall",
      "category": "STRUCTURE_WALL",
      "size_cm": [16.0, 512.0, 384.0],
      "pivot_offset_cm": [0.0, 256.0, -192.0]
    },
    "prop_crate_military": {
      "uefn_path": "/Game/Athena/Props/Crates/SM_MilitaryCrate.SM_MilitaryCrate",
      "category": "PROP",
      "size_cm": [120.0, 120.0, 130.0],
      "pivot_offset_cm": [0.0, 0.0, -65.0]
    }
  }
}
```

### Schema `03_grid.json`
 Legende des cellules :
- `#` : Sol avec murs sur les bords exterieurs de la carte
- `.` : Sol libre
- `W` : Mur interieur plein
- `P` : Mur avec ouverture de porte (`largeur >= 120 cm`, `hauteur >= 220 cm`)
- `S1`, `S2` : Sol contenant un Player Spawner (Equipe 1, Equipe 2)
- `O` : Sol contenant un Objectif principal
- `R_N`, `R_S`, `R_E`, `R_W` : Escalier / Rampe montant vers le Nord, Sud, Est, Ouest
- `T` : Tremie ouverte (`OPEN_STAIRWELL`, aucun sol pose a cet etage)
- `V` : Vide (aucun sol ni mur)

```json
{
  "tile_size_cm": [512.0, 512.0, 384.0],
  "symmetric": true,
  "symmetry_axis": "X",
  "floors": [
    {
      "z_index": 0,
      "matrix": [
        ["#", "#", "#", "#"],
        ["#", "S1", "S1", "#"],
        ["#", ".", ".", "#"],
        ["#", "O", "O", "#"],
        ["#", ".", ".", "#"],
        ["#", "S2", "S2", "#"],
        ["#", "#", "#", "#"]
      ]
    }
  ]
}
```

### Schema `04_devices.json`
```json
{
  "devices": [
    {
      "actor_label": "Spawner_Team1_01",
      "device_class": "player_spawner_device",
      "tile": [1, 1, 0],
      "slot": "NORTH_EDGE",
      "face_towards": "SOUTH",
      "on_floor": true,
      "properties": {
        "TeamIndex": 1,
        "EnabledDuringPhase": "Always"
      }
    }
  ]
}
```

### Schema `05_props.json`
```json
{
  "props": [
    {
      "actor_label": "Cover_Crate_01",
      "asset_key": "prop_crate_military",
      "placement_mode": "TILE_ANCHOR",
      "tile": [2, 1, 0],
      "slot": "CENTER",
      "face_towards": "SOUTH",
      "snap_to_floor": true
    },
    {
      "actor_label": "Cover_Crate_02",
      "asset_key": "prop_crate_military",
      "placement_mode": "RELATIVE_TO_ACTOR",
      "reference_actor": "Cover_Crate_01",
      "direction": "RIGHT_OF",
      "gap_cm": 15.0,
      "face_towards": "SOUTH",
      "snap_to_floor": true
    }
  ]
}
```

### Schema `06_audit_report.json`
```json
{
  "timestamp": "2026-10-16T01:00:00Z",
  "status": "PASSED",
  "error_count": 0,
  "overlap_errors": [],
  "gravity_errors": [],
  "navigation_errors": []
}
```