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
- `scale` (facteur unique ou `[x, y, z]`) est optionnel dans `02_palette.json` : la taille et le pivot **mesures** sont multiplies par ce facteur, et le facteur est repris dans le transform pose. `place-scene` relit l'echelle : si l'editeur ne l'applique pas, `TRANSFORM_MISMATCH` le dit au lieu de laisser une taille fausse dans les controles. Un asset dont la taille mesuree n'est pas 512 x 512 en X/Y declenche `FLOOR_NOT_TILE_SIZED` avec l'echelle suggeree.

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

## 5 bis. Miroir d'un acteur (`check-symmetry`)

Trois formules, une par mode (`symmetry_axis` de `03_grid.json`). `rows` et `cols` sont les
dimensions de la matrice de l'etage concerne.

| mode | tuile `[r, c, z]` | position locale `(lx, ly, lz)` dans la tuile | yaw |
|---|---|---|---|
| `X` | `[rows-1-r, c, z]` | `(512 - lx, ly, lz)` | `(180 - yaw) % 360` |
| `Y` | `[r, cols-1-c, z]` | `(lx, 512 - ly, lz)` | `(-yaw) % 360` |
| `R180` | `[rows-1-r, cols-1-c, z]` | `(512 - lx, 512 - ly, lz)` | `(yaw + 180) % 360` |

La comparaison porte sur les **coordonnees locales** (`lx = centre_x - tx * 512`, etc.), pas sur
les coordonnees absolues : deux acteurs de tailles differentes restent comparables, et le
controle ne depend pas de la place de la tuile dans la carte. Invariant a retenir : deux
positions miroirs somment a 512 sur chaque axe retourne.

L'appariement est en `O(n)` : les acteurs sont groupes par `(paire de tuiles triee, asset_key)`,
puis apparies au plus proche a l'interieur de chaque groupe (les groupes restent petits, donc le
cout ne depend pas de la taille de la carte). Au-dela de `MIRROR_SEARCH_CM` (768 cm) d'ecart
local, le partenaire est declare **absent** (`MIRROR_PARTNER_MISSING`) plutot que mal place.
`RELATIVE_TO_ACTOR` n'a pas besoin de cas particulier : l'enfant herite de la tuile de son
parent, et sous `R180` un enfant `RIGHT_OF` a pour miroir un enfant `RIGHT_OF` du parent miroir.

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
`size_cm`, `pivot_offset_cm` et `measured` sont remplis par `measure-palette`. `compile-transforms` refuse une entree sans `measured`. `scale` (nombre ou `[x, y, z]`) est optionnel : il multiplie la taille et le pivot mesures, et il est pose puis relu.
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
    "floor_from_engine_cube": {
      "uefn_path": "/Engine/BasicShapes/Cube",
      "category": "STRUCTURE_FLOOR",
      "scale": [5.12, 5.12, 0.32],
      "size_cm": [100.0, 100.0, 100.0],
      "pivot_offset_cm": [0.0, 0.0, 0.0],
      "measured": {"at": "2026-10-20T00:00:00+00:00", "kind": "actor"},
      "notes": "Cube moteur mis a l'echelle : dalle 512 x 512 x 32 cm"
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

`symmetric: true` exige un `symmetry_axis` parmi **`X`**, **`Y`** et **`R180`** (`validate-grid`
renvoie `SYMMETRY_AXIS_UNSUPPORTED` sinon, pas un silence) :
- `X` : miroir sur les lignes, `[r, c]` <-> `[rows-1-r, c]` (Nord <-> Sud). `R_N` <-> `R_S`.
- `Y` : miroir sur les colonnes, `[r, c]` <-> `[r, cols-1-c]` (Est <-> Ouest). `R_E` <-> `R_W`.
- `R180` : rotation de 180 degres, `[r, c]` <-> `[rows-1-r, cols-1-c]`. Les deux echanges a la
  fois **et** `S1` <-> `S2` : c'est le mode des arenes versus en diagonale (gabarit
  `1v1_arena`).
En `X`/`Y`, `S1` et `S2` sont tenus pour equivalents : une carte peut separer ses equipes sur
l'autre axe (gabarit `boxfight`, S1 au Nord et S2 au Sud, est declare en `X`). L'echange des
equipes n'est donc **pas** verifie en miroir ; l'avertissement `SYMMETRY_SCOPE` de
`validate-scene` le rappelle.
Une case posee **sur** le plan de symetrie n'a pas de partenaire possible : elle doit etre son
propre miroir (`#`, `.`, `P`, `O`, `T`, `V`), sinon `SYMMETRY_ON_AXIS`.

### Schema `04_devices.json`
`asset_key` est la cle obligatoire (elle pointe vers `02_palette.json`) ; `device_class` n'est qu'une mention lisible.
`properties` est applique par `apply-properties` (etape 6), qui confronte chaque nom a `Object.list_properties` et chaque valeur a `get_properties` : un nom invente donne `PROPERTY_NOT_FOUND`, une valeur relue differente donne `PROPERTY_MISMATCH`.
`bindings` est applique par `wire-devices`, qui valide `event` et `function` avec `Device.GetBindingOptions` sur la **source** puis recroise par `ListEventBindings` sur la **cible** : ne jamais ecrire un nom d'evenement ou de fonction devine.
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
      },
      "bindings": [
        {"event": "OnTriggered", "to": "Barrier_Center_01", "function": "Disable"}
      ]
    },
    {
      "actor_label": "Granter_Loadout_01",
      "asset_key": "item_granter",
      "placement_mode": "WORLD",
      "world_location_cm": [-5888.0, 1280.0, -2304.0],
      "zone": "Zone_Logic",
      "face_towards": "NORTH",
      "on_floor": false
    }
  ]
}
```
- Valeurs de `slot` : les 9 ancres de la section 3. Valeurs de `face_towards` : `NORTH`, `EAST`, `SOUTH`, `WEST`, `CENTER`, ou un `actor_label` deja place avant.
- Placement par defaut : `TILE_ANCHOR` (`tile` + `slot` obligatoires). `placement_mode: "WORLD"` pose le device en coordonnees absolues (`world_location_cm` = centre de la boite) : c'est le cas des devices **non spatiaux** de `Zone_Logic`, qui ne sont sur aucune tuile de `03_grid.json`. `on_floor: false` desactive alors le controle de gravite, et la tuile du rapport est derivee des coordonnees (negative hors grille).
- Les noms de proprietes sont a confirmer par `Object.list_properties` (voir `devices-catalog-and-wiring.md`).
- `"mirror": false` (optionnel, defaut `true`) sort l'acteur de `check-symmetry`. A poser **des deux cotes** d'une paire : un acteur symetrique dont le jumeau est exclu remonte `MIRROR_PARTNER_MISSING`. Les devices en `placement_mode: "WORLD"` sont ignores d'office (hors grille, aucun miroir possible) et listes dans le `scope` du rapport.

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
`mirror: false` s'applique ici comme dans `04_devices.json`. Un prop `RELATIVE_TO_ACTOR` herite de
la tuile de son `reference_actor` : son jumeau doit pointer vers le jumeau du parent et etre
declare **apres** lui (`validate-scene` refuse une reference non declaree). Sous `R180` la
relation est conservee : un enfant `RIGHT_OF` a pour miroir un enfant `RIGHT_OF` du parent miroir.

### Schema `06_audit_report.json` (ecrit par `audit-scene`)
Chevauchements, gravite, acteurs introuvables. `source` vaut `compiled` (aucun appel editeur),
`live` (bounds relus) ou `not_live` (`--live` demande mais **aucun** bounds relu : rien n'est verifie).
```json
{
  "timestamp": "2026-10-20T01:00:00+00:00",
  "source": "live",
  "status": "PASSED",
  "error_count": 0,
  "overlap_errors": [
    {"type": "OVERLAP_ERROR", "actor_a": "Cover_Crate_Main", "actor_b": "Pillar_Decor_01",
     "penetration_cm": 28.4, "tile": [2, 2, 0],
     "suggestion": "Placer Cover_Crate_Main en RELATIVE_TO_ACTOR avec gap_cm >= 15."}
  ],
  "gravity_errors": [
    {"type": "GRAVITY_ERROR", "actor": "Cover_Crate_Main", "distance_to_floor_cm": -12.0,
     "state": "BURIED", "tile": [2, 2, 0], "floor_reference": "bounds du sol",
     "suggestion": "Remesurer pivot_offset_cm (measure-palette --force) ou corriger snap_to_floor."}
  ],
  "scene_errors": [{"type": "ACTOR_NOT_FOUND", "actor": "Pillar_Decor_01"}],
  "other_report": "passages etroits : 06_navigation_report.json (check-navigation)",
  "gravity_scope": "bounds relus dans l'editeur"
}
```

### Schema `06_navigation_report.json` (ecrit par `check-navigation`)
Rapport separe : `check-navigation` n'herite pas des erreurs d'un audit precedent, et son
`status` est toujours coherent avec son code retour.
```json
{
  "timestamp": "2026-10-20T01:05:00+00:00",
  "command": "check-navigation",
  "status": "FAILED",
  "error_count": 1,
  "navigation_errors": [
    {"type": "CORRIDOR_TOO_NARROW", "tile": [2, 2, 0], "free_width_cm": 62.5,
     "required_width_cm": 100.0, "blocking_actors": ["Cover_Crate_Main", "Ammo_Box_Front"]}
  ],
  "navigation_scope": "paires de props dans une meme tuile ; pas de capsule, pas de murs, pas de devices, pas de passages entre tuiles",
  "other_report": "chevauchements et gravite : 06_audit_report.json (audit-scene), non recalcule ici"
}
```

### Schema `07_properties_report.json` (ecrit par `apply-properties`)
```json
{
  "timestamp": "2026-10-20T01:10:00+00:00",
  "status": "FAILED",
  "error_count": 1,
  "applied": [{"actor": "Spawner_Team1_01", "property": "playerTeam",
               "written": {"teamType": "TeamIndex", "teamIndex": 1},
               "read_back": {"teamType": "TeamIndex", "teamIndex": 1}}],
  "errors": [{"type": "PROPERTY_MISMATCH", "actor": "Barrier_Center_01",
              "property": "bIsActive", "written": true, "read_back": false}],
  "not_placed": [],
  "scope": "chaque valeur ecrite par set_properties est relue par get_properties ; les devices Verse (SetDeviceProperty) ne sont pas couverts : outil inconnu, jamais teste sur un creative_device"
}
```
Types d'erreur : `PROPERTY_NOT_FOUND` (avec `nearest`, suggestions de noms reels),
`PROPERTY_UNREADABLE` (valeur **inconnue**, pas valeur absente), `PROPERTY_MISMATCH`.
Un device declare dans `04_devices.json` mais absent de `_placed.json` part dans `not_placed`
et compte dans `error_count` : ne pas confondre « non regle » et « regle et faux ».

### Schema `08_wiring_report.json` (ecrit par `wire-devices`)
```json
{
  "timestamp": "2026-10-20T01:15:00+00:00",
  "status": "PASSED",
  "error_count": 0,
  "wired": [{"from": "Trigger_Zone_01", "event": "OnTriggered", "to": "Barrier_Center_01",
             "function": "Disable", "read_back": {"sourceEvent": "OnTriggered"}}],
  "errors": [{"type": "BINDING_NOT_READ_BACK", "from": "...", "event": "...", "to": "...",
              "function": "...", "target_bindings": "[...]",
              "detail": "le lien apparait sur la CIBLE : s'il n'y est pas, il n'est pas prouve"}],
  "not_placed": [],
  "scope": "cablage evenement -> fonction entre devices poses. Le cablage par canal (GameplayTagContainer) et les references @editable ne sont pas couverts."
}
```
Types d'erreur : `NO_BINDING_DECLARED` (aucun `bindings` dans `04_devices.json`),
`BINDING_EVENT_UNKNOWN` / `BINDING_FUNCTION_UNKNOWN` (nom absent de `GetBindingOptions`,
la liste reelle est dans le rapport), `BINDING_NOT_READ_BACK`.

### Schema `09_verse_report.json` (ecrit par `verse-build`)
```json
{
  "timestamp": "2026-10-20T01:20:00+00:00",
  "command": "verse-build",
  "session": "Disconnected",
  "status": "PASSED",
  "diagnostics_count": 0,
  "error_diagnostics": [],
  "warnings": [],
  "build_log_lines": ["LogVerseBuild: Build succeeded in 1.83s"],
  "success_lines": ["LogVerseBuild: Build succeeded in 1.83s"],
  "scope": "une liste de diagnostics vide ne suffit PAS : il faut aussi une ligne de succes recente dans VerseBuild"
}
```
Echecs : `SESSION_CONNECTED` (refus de compiler, rien n'est appele) et `status: "FAILED"` avec
`error_diagnostics` vides quand aucune ligne de succes n'a ete trouvee. `verse-write` n'ecrit pas
ici : il journalise dans `_verse_written.json` (`read_back_matches`).

### Schema `10_editables.json` (ecrit par `list-editables`)
```json
{
  "timestamp": "2026-10-20T01:25:00+00:00",
  "command": "list-editables",
  "status": "PASSED",
  "editable_count": 3,
  "actor_references": 2,
  "parameters": 1,
  "without_target": [],
  "mapping": [
    {"file": "round_controller.verse", "editable": "Spawner_Team1_01", "type": "player_spawner_device",
     "kind": "ACTEUR", "declared_in_04_devices": true, "asset_key": "player_spawner",
     "refPath": "PersistentLevel.Spawner_Team1_01", "wiring": "MANUEL"},
    {"file": "round_controller.verse", "editable": "DebugSelfTest", "type": "logic",
     "kind": "PARAMETRE", "declared_in_04_devices": false, "asset_key": null,
     "refPath": null, "wiring": "AUCUNE_CIBLE"}
  ],
  "live": null,
  "scope": "seules les references d'ACTEUR doivent viser un acteur pose"
}
```
`kind` separe les references d'acteur (`ACTEUR`, une cible est obligatoire) des parametres
(`logic`, `bool`, `int`, `float`, `string`, `message`, `locale`, `type`). Un `ACTEUR` sans
`refPath` part dans `without_target` : le cablage automatique des references est **UNKNOWN**
(hypothese `savedActor` jamais testee), donc cette liste sert a cabler a la main.
`live` n'est rempli qu'avec `--live --device <label du device Verse pose>`.

### Schema `11_symmetry_report.json` (ecrit par `check-symmetry`)
Symetrie reelle des acteurs : chaque entree de `04`/`05` est appariee a son miroir dans la tuile
opposee, puis compares **en coordonnees locales de tuile** (donc independant de la taille de
l'asset) et en yaw. `source` vaut `compiled` (specs seules), `live` (transforms et bounds relus)
ou `not_live` (`--live` demande mais aucun bounds relu).
```json
{
  "timestamp": "2026-10-21T23:20:40+00:00",
  "command": "check-symmetry",
  "status": "FAILED",
  "axis": "R180",
  "symmetric": true,
  "source": "compiled",
  "error_count": 1,
  "checked_pairs": 7,
  "spec_errors": [
    {"type": "SPEC_ASYMMETRY", "axis": "R180", "fault": "position",
     "actor_a": "Ramp_Duel_P1_01", "actor_b": "Ramp_Duel_P2_01",
     "tile_a": [3, 2, 0], "tile_b": [4, 5, 0],
     "expected_center_b_cm": [2304.0, 2816.0, 75.0],
     "center_b_cm": [2360.0, 2816.0, 75.0],
     "delta_cm": [56.0, 0.0, 0.0], "max_delta_cm": 56.0,
     "tolerance_cm": [1.0, 1.0, 1.0],
     "suggestion": "Amener Ramp_Duel_P2_01 en [2304.0, 2816.0, 75.0] (miroir de Ramp_Duel_P1_01 en tuile [3, 2, 0]), puis compile-transforms et place-scene."}
  ],
  "drift_errors": [
    {"type": "TRANSFORM_DRIFT", "actor": "Cover_Crate_01",
     "delta_location_cm": [40.0, 0.0, 0.0], "delta_yaw_deg": 0.0, "delta_scale": 0.0,
     "expected": {"location": {"x": 768.0, "y": 1792.0, "z": 78.0},
                  "rotation": {"yaw": 180.0}, "scale": {"x": 1.2, "y": 1.2, "z": 1.2}},
     "read_back": {"location": {"x": 808.0, "y": 1792.0, "z": 78.0},
                   "rotation": {"yaw": 180.0}, "scale": {"x": 1.2, "y": 1.2, "z": 1.2}},
     "suggestion": "L'acteur a bouge depuis place-scene, ou le placement n'a jamais ete corrige. Corriger la spec, puis cleanup + place-scene."}
  ],
  "scene_errors": [],
  "scope": [
    "16 acteurs de 04/05 controles (centre + yaw) ; 5 en placement_mode WORLD ignores (hors grille, aucun miroir possible): Granter_Loadout_01, Round_Timer_01, Score_Manager_01, End_Game_01, Hud_Message_01",
    "murs et sols de _compiled_structure.json non controles : leur symetrie vient de la matrice, verifiee par validate-grid.",
    "SPEC seulement : un acteur deplace dans l'editeur apres place-scene n'est pas vu. Relancer avec --live pour controler la scene posee."
  ]
}
```
(`spec_errors` et `drift_errors` ci-dessus ne sont pas issus du meme lancement : le premier est un
rapport reel, le second montre la forme d'un `TRANSFORM_DRIFT` obtenu avec `--live`.)

Types d'erreur :
- `SPEC_ASYMMETRY` / `SCENE_ASYMMETRY` : la paire existe mais le centre local ou le yaw n'est pas
  le miroir. `fault` vaut `position`, `yaw` ou `position+yaw` ; `expected_center_b_cm` est la
  correction a appliquer. Le meme controle sur les bounds relus donne `SCENE_ASYMMETRY`.
- `MIRROR_PARTNER_MISSING` : aucun acteur de meme `asset_key` dans la tuile miroir (ou aucun a
  moins de `MIRROR_SEARCH_CM` = 768 cm). Au-dela de cette distance le partenaire est declare
  **absent** plutot que mal place, ce qui est plus actionnable.
- `TRANSFORM_DRIFT` (`--live`) : le transform relu s'ecarte du transform compile au-dela de
  `POS_TOLERANCE_CM` / `YAW_TOLERANCE_DEG` / `SCALE_TOLERANCE`. C'est le seul controle qui voit un
  acteur deplace a la main dans l'editeur.
- `NOT_PLACED` (`--live`) : absent de `_placed.json`. `UNREADABLE_TRANSFORM` : reponse vide ou
  illisible, donc **inconnu** (jamais « l'acteur est a la bonne place »). `NO_LIVE_DATA` : aucun
  bounds relu, la scene posee n'est pas verifiee.
- `COMPILE_FAILED` : les specs ne compilent pas, rien n'est verifiable. Lancer
  `compile-transforms` seul pour la liste des erreurs.

Tolerances : `SYMMETRY_POS_TOLERANCE_CM` = 1.0 et `SYMMETRY_YAW_TOLERANCE_DEG` = 1.0 (les specs
sont calculees, un miroir juste tombe a ~0). Sur X et Y la tolerance est elargie de
`abs(taille_a - taille_b) / 2` pour absorber la difference de `rotated_size` a un yaw non cardinal.
Un acteur seul **sur** le plan de symetrie est son propre partenaire : le yaw n'est pas exige,
mais il doit etre centre sur l'axe.

Portee reelle des controles, a dire a l'utilisateur sans enjoliver :
- `check-navigation` ne teste que deux props d'une meme tuile face a face. Il ne tient compte ni de la capsule joueur, ni des murs, ni des devices, ni des rampes, ni des passages entre tuiles. Un `PASSED` ne prouve pas que la carte est jouable.
- `check-symmetry` ne compare que les acteurs de `04`/`05` : ni les sols et murs de `build-structure` (leur symetrie vient de la matrice, controlee par `validate-grid`), ni les devices en `placement_mode: "WORLD"`, ni les materials, les collisions ou les proprietes. Sans `--live` un acteur deplace a la main dans l'editeur n'est **pas** vu. En miroir `X`/`Y` l'echange des equipes (`S1` <-> `S2`) n'est pas verifie : seule la rotation `R180` l'exige.
- `GRAVITY_ERROR` n'est detectable **qu'avec `audit-scene --live`**. Hors ligne, le centre compile d'un `TILE_ANCHOR` est par construction pose au sol : la distance au sol vaut toujours 0, donc un `pivot_offset_cm` faux passe en `PASSED`. Le rapport le dit via `gravity_scope`. Un device en `placement_mode: "WORLD"` avec `on_floor: false` n'est pas controle du tout (il n'est pas cense reposer sur un sol de tuile).
- `source: "not_live"` avec `NO_LIVE_DATA` signifie qu'`audit-scene --live` n'a relu **aucun** bounds (pas de `_placed.json`) : rien n'est verifie, il ne faut pas lire ce rapport comme un controle.
- `apply-properties` et `wire-devices` ne touchent que les acteurs deja dans `_placed.json` : ce qui est dans `not_placed` n'a recu **aucun** appel editeur.
- `verse-build` ne prouve pas le comportement en jeu : il prouve que le code compile. La validation en session reste l'etape 10, avec accord explicite.
- `MIN_CORRIDOR_HEIGHT`, `MAX_JUMP_HEIGHT` et `MAX_SPRINT_JUMP_LENGTH` ne sont pas verifies par le CLI : controler la grille a la lecture.