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

Les transforms MCP sont en XYZ, sous forme d'objet : `{"location": {"x", "y", "z"}, "rotation": {"pitch", "yaw", "roll"}, "scale": {"x", "y", "z"}}`.

- **XYZ (MCP, transforms d'acteurs)** :
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

## 2 bis. Mesure, pivot et rotation (obligatoire)

- `pivot_offset_cm` = centre des bounds moins la position de l'acteur, **mesure a yaw 0** (`Actor.get_actor_bounds` apres `Actor.get_actor_transform`). Pour un Cube moteur, le pivot est le centre des bounds (decalage nul) ; pour un autre asset, ne rien supposer.
- Aucun outil ne donne le pivot d'un asset : il faut le poser, lire, supprimer. C'est le role de `measure-palette`, qui ecrit aussi `measured: true`. `compile-transforms` refuse un asset non mesure.
- Une pose est toujours `position = centre_voulu - rotation(pivot_offset_cm, yaw)`. Oublier la rotation du pivot decale l'objet des qu'il tourne.
- La taille utilisee dans les controles est la boite alignee aux axes apres rotation en yaw : `size_x' = |size_x*cos| + |size_y*sin|`, etc. Un objet tourne occupe plus d'espace en X et Y.
- `measure-palette` verifie le yaw relu : si `PlaceDevice` a ignore le yaw demande, la mesure est rejetee au lieu d'etre fausse.

## 3. Les 9 Ancres de Tuile (`slot`)

Pour une tuile d'indice `[tx, ty, tz]` dont l'origine Sud-Ouest est `(Bx = tx * 512.0, By = ty * 512.0, Bz = tz * 384.0)` et un acteur de demi-taille `(hx = size_x / 2.0, hy = size_y / 2.0)` (tailles **apres rotation**), le centre vise est :

- `CENTER` : `(Bx + 256.0, By + 256.0)`
- `NORTH_EDGE` : `(Bx + 512.0 - hx, By + 256.0)`
- `SOUTH_EDGE` : `(Bx + hx, By + 256.0)`
- `EAST_EDGE` : `(Bx + 256.0, By + 512.0 - hy)`
- `WEST_EDGE` : `(Bx + 256.0, By + hy)`
- `CORNER_NE` : `(Bx + 512.0 - hx, By + 512.0 - hy)`
- `CORNER_NW` : `(Bx + 512.0 - hx, By + hy)`
- `CORNER_SE` : `(Bx + hx, By + 512.0 - hy)`
- `CORNER_SW` : `(Bx + hx, By + hy)`
- Z : `Bz + size_z / 2.0` (l'objet repose sur le sol de l'etage).
- Un objet ancre sur une `EDGE` ou un `CORNER` touche le bord de la tuile : verifier qu'il ne reduit pas un couloir sous `MIN_CORRIDOR_WIDTH` (`check-navigation`).

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
- La cellule placee exactement au-dessus en `[tx, ty, tz + 1]` dans `03_grid.json` doit obligatoirement porter le code `T` (`OPEN_STAIRWELL`). `validate-grid` verifie ce point (`HEADROOM_BLOCKED_ON_STAIRS`).
- Le generateur de structure ne pose jamais de dalle de sol sur une case `T`, garantissant 384 cm de hauteur libre.
- L'escalier lui-meme est un asset a poser comme une prop (`05_props.json`), pas une cellule de grille : `build-structure` ne sait poser que des sols et des murs de perimetre.

## 6 bis. Ce que `build-structure` fait vraiment

- Il pose un sol sur toute cellule sauf `V` et `T`.
- Il pose des murs **seulement sur le perimetre de la grille**, pour les cellules `#`. Le mur est place a l'exterieur de la tuile, pour laisser l'interieur 512 x 512 libre.
- Les codes `W` (mur interieur) et `P` (porte) ne sont **pas construits** par le CLI : les decrire dans `05_props.json`, ou les poser a la main.
- Un `#` a l'interieur declenche l'avertissement `INTERIOR_WALL_NOT_BUILT`.
- `validate-grid` exige que toute la bordure externe soit `#` ou `V` (`UNCLOSED_BORDER`).

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
`size_cm`, `pivot_offset_cm` et `measured` sont remplis par `measure-palette`. `compile-transforms` refuse une entree sans `measured`.
```json
{
  "assets": {
    "floor_basic": {
      "uefn_path": "/Game/Athena/Environments/Blueprints/Floors/BP_Floor.BP_Floor",
      "category": "STRUCTURE_FLOOR",
      "size_cm": [512.0, 512.0, 16.0],
      "pivot_offset_cm": [0.0, 0.0, -8.0],
      "measured": {"at": "2026-10-20T00:00:00+00:00", "kind": "actor"}
    },
    "wall_basic": {
      "uefn_path": "/Game/Athena/Environments/Blueprints/Walls/BP_Wall.BP_Wall",
      "category": "STRUCTURE_WALL",
      "size_cm": [16.0, 512.0, 384.0],
      "pivot_offset_cm": [0.0, 0.0, 0.0]
    },
    "player_spawner": {
      "uefn_path": "/CRD_PlayerSpawn/ItemDefinitions/PID_CP_Devices_PlayerSpawner.PID_CP_Devices_PlayerSpawner",
      "category": "DEVICE_SPAWNER",
      "size_cm": [512.0, 400.0, 324.0],
      "pivot_offset_cm": [0.0, 0.0, 0.0]
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
- Les categories `STRUCTURE_FLOOR` et `STRUCTURE_WALL` sont celles que `build-structure` utilise (la premiere de chaque categorie est retenue).
- Une categorie qui commence par `DEVICE` est posee par `PlaceDevice` et mesuree comme un device.
- Les valeurs de taille et de pivot ci-dessus sont des exemples : les remplacer par les mesures reelles.

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
`asset_key` est la cle obligatoire (elle pointe vers `02_palette.json`) ; `device_class` n'est qu'une mention lisible.
Le champ `properties` n'est **pas applique** par le CLI : il sert de liste a regler ensuite avec `Object.set_properties`.
```json
{
  "devices": [
    {
      "actor_label": "Spawner_Team1_01",
      "asset_key": "player_spawner",
      "device_class": "player_spawner_device",
      "tile": [1, 1, 0],
      "slot": "NORTH_EDGE",
      "face_towards": "SOUTH",
      "on_floor": true,
      "properties": {
        "playerTeam": {"teamType": "TeamIndex", "teamIndex": 1},
        "enabledDuringPhase": "Always"
      }
    }
  ]
}
```
- Valeurs de `slot` : les 9 ancres de la section 3. Valeurs de `face_towards` : `NORTH`, `EAST`, `SOUTH`, `WEST`, `CENTER`, ou un `actor_label` deja place avant.
- Les noms de proprietes sont a confirmer par `Object.list_properties` (voir `devices-catalog-and-wiring.md`).

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
`scene_errors` signale les acteurs absents de la scene ou aux bounds illisibles lors d'un `audit-scene --live`.
Le rapport porte la source (`compiled` ou `live`) et le perimetre reel de `check-navigation`.
```json
{
  "timestamp": "2026-10-20T01:00:00+00:00",
  "source": "live",
  "status": "PASSED",
  "error_count": 0,
  "overlap_errors": [],
  "gravity_errors": [],
  "scene_errors": [],
  "navigation_errors": [],
  "navigation_scope": "paires de props dans une meme tuile ; pas de capsule ni de murs"
}
```
Portee reelle des controles, a dire a l'utilisateur sans enjoliver :
- `check-navigation` ne teste que deux props d'une meme tuile face a face. Il ne tient compte ni de la capsule joueur, ni des murs, ni des rampes, ni des passages entre tuiles. Un `PASSED` ne prouve pas que la carte est jouable.
- `MIN_CORRIDOR_HEIGHT`, `MAX_JUMP_HEIGHT` et `MAX_SPRINT_JUMP_LENGTH` ne sont pas verifies par le CLI : controler la grille a la lecture.