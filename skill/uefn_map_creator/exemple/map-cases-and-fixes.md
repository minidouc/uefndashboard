# Catalogue des Cas de Figure et Corrections Automatiques UEFN

Chaque device est reference par une `asset_key` vers `02_palette.json` (`device_class` ne sert que de mention lisible).
Le champ `properties` n'est pas applique par le CLI : il sert de liste a regler avec `Object.set_properties` puis a relire.
Un asset de la palette doit avoir ete mesure (`measure-palette`) : `compile-transforms` refuse toute entree sans `measured`.

## Cas 1 : Petite Carte Competitive Symetrique (Box Fight 2v2 / 1v1 Build Fight)

### Contexte
Carte de `4 x 6` tuiles sur 1 etage (`Z = 0`). La symetrie doit etre parfaite sur l'axe Nord-Sud pour qu'aucune equipe ne soit desavantagee.

### Sortie Attendue dans `workspace_map/03_grid.json`
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
        ["#", ".", ".", "#"],
        ["#", "S2", "S2", "#"],
        ["#", "#", "#", "#"]
      ]
    }
  ]
}
```

### Sortie Attendue dans `workspace_map/04_devices.json`
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
      "properties": {"playerTeam": {"teamType": "TeamIndex", "teamIndex": 1}}
    },
    {
      "actor_label": "Spawner_Team1_02",
      "asset_key": "player_spawner",
      "device_class": "player_spawner_device",
      "tile": [1, 2, 0],
      "slot": "NORTH_EDGE",
      "face_towards": "SOUTH",
      "on_floor": true,
      "properties": {"playerTeam": {"teamType": "TeamIndex", "teamIndex": 1}}
    },
    {
      "actor_label": "Spawner_Team2_01",
      "asset_key": "player_spawner",
      "device_class": "player_spawner_device",
      "tile": [4, 1, 0],
      "slot": "SOUTH_EDGE",
      "face_towards": "NORTH",
      "on_floor": true,
      "properties": {"playerTeam": {"teamType": "TeamIndex", "teamIndex": 2}}
    },
    {
      "actor_label": "Spawner_Team2_02",
      "asset_key": "player_spawner",
      "device_class": "player_spawner_device",
      "tile": [4, 2, 0],
      "slot": "SOUTH_EDGE",
      "face_towards": "NORTH",
      "on_floor": true,
      "properties": {"playerTeam": {"teamType": "TeamIndex", "teamIndex": 2}}
    },
    {
      "actor_label": "Barrier_Team1",
      "asset_key": "barrier",
      "device_class": "barrier_device",
      "tile": [1, 1, 0],
      "slot": "SOUTH_EDGE",
      "face_towards": "SOUTH",
      "on_floor": true
    },
    {
      "actor_label": "Barrier_Team2",
      "asset_key": "barrier",
      "device_class": "barrier_device",
      "tile": [4, 1, 0],
      "slot": "NORTH_EDGE",
      "face_towards": "NORTH",
      "on_floor": true
    }
  ]
}
```
- `playerTeam` et `BarrierWidth` / `BarrierHeight` sont des noms notes, non verifies : relancer `Object.list_properties` sur le device pose pour trouver les vrais noms (certains contiennent des espaces).
- Deux devices partagent la meme tuile `[1, 1, 0]` avec des ancres differentes : verifier `audit-scene` (chevauchement) apres placement.

---

## Cas 2 : Carte Moyenne Modulaire avec Prefabriques (Zone Wars / Mini-Ville)

### Contexte
Au lieu de poser 200 murs pour creer des maisons, on mesure un Prefabrique Fortnite entier dans `02_palette.json` et on le pose sur l'ancre `CORNER_SW` de la tuile de depart.
L'encombrement au sol est calcule par `compile-transforms` a partir des **bounds relus**, pas d'une taille supposee : le bloc `measured` est rempli par `measure-palette`, et une emprise multi-tuiles est acceptee tant qu'elle ne chevauche pas une autre prop.

### Entree dans `workspace_map/02_palette.json`
```json
{
  "assets": {
    "prefab_house_two_story": {
      "uefn_path": "/Game/Athena/Prefabs/Suburban/PG_Suburban_House_01.PG_Suburban_House_01",
      "category": "PREFAB_BUILDING",
      "size_cm": [1536.0, 1024.0, 768.0],
      "footprint_tiles": [3, 2, 2],
      "pivot_offset_cm": [-768.0, -512.0, -384.0]
    }
  }
}
```

### Placement sans collision dans `workspace_map/05_props.json`
```json
{
  "props": [
    {
      "actor_label": "Building_House_North",
      "asset_key": "prefab_house_two_story",
      "placement_mode": "TILE_ANCHOR",
      "tile": [2, 2, 0],
      "slot": "CORNER_SW",
      "face_towards": "SOUTH",
      "snap_to_floor": true
    },
    {
      "actor_label": "Street_Lamp_Front",
      "asset_key": "prop_street_lamp",
      "placement_mode": "RELATIVE_TO_ACTOR",
      "reference_actor": "Building_House_North",
      "direction": "IN_FRONT_OF",
      "gap_cm": 150.0,
      "face_towards": "SOUTH",
      "snap_to_floor": true
    }
  ]
}
```

---

## Cas 3 : Gros Projet par Decoupage en Zones (Tycoon / RPG / Donjon)

### Contexte
La carte totale fait `18 x 12` tuiles. Comme elle depasse `8 x 8` tuiles, l'agent a l'interdiction de tout generer en une seule fois. Il divise la carte en 3 zones connectees par des portes `P` et valide chaque zone (grille, structure, placement, audit) avant de passer a la suivante.
Rappel : il n'existe pas de PCG ni d'outil de duplication dans le MCP teste. Une grande carte = beaucoup d'acteurs poses un par un, par lots de 10 dans `execute_tool_script` ; les listes `find_actors` demandent la pagination a 200 (`preflight`).

### Structure de Decoupage dans `workspace_map/01_gdd.json`
```json
{
  "project_name": "Cyber_Factory_Tycoon",
  "game_mode": "tycoon",
  "scale_category": "LARGE",
  "grid_dimensions_tiles": [18, 12, 2],
  "zones": [
    {
      "zone_id": "Zone_A_PlayerHub",
      "bounds_tiles": {"min": [0, 0, 0], "max": [5, 5, 1]},
      "connects_to": [{"target_zone": "Zone_B_FactoryFloor", "door_tile": [5, 2, 0]}],
      "status": "VALIDATED_0_ERRORS"
    },
    {
      "zone_id": "Zone_B_FactoryFloor",
      "bounds_tiles": {"min": [6, 0, 0], "max": [11, 7, 1]},
      "connects_to": [
        {"target_zone": "Zone_A_PlayerHub", "door_tile": [6, 2, 0]},
        {"target_zone": "Zone_C_BossArena", "door_tile": [11, 4, 0]}
      ],
      "status": "IN_PROGRESS"
    },
    {
      "zone_id": "Zone_C_BossArena",
      "bounds_tiles": {"min": [12, 0, 0], "max": [17, 11, 1]},
      "connects_to": [{"target_zone": "Zone_B_FactoryFloor", "door_tile": [12, 4, 0]}],
      "status": "PENDING"
    }
  ]
}
```

---

## Cas 4 : Correction Automatique d'une Collision (`OVERLAP_ERROR`)

### Rapport d'Erreur (`06_audit_report.json`, produit par `audit-scene`)
```json
{
  "status": "FAILED",
  "source": "live",
  "error_count": 1,
  "overlap_errors": [
    {
      "type": "OVERLAP_ERROR",
      "actor_a": "Weapon_Vending_01",
      "actor_b": "Wall_North_02",
      "penetration_cm": 42.0,
      "tile": [0, 2, 0],
      "suggestion": "Placer Weapon_Vending_01 en RELATIVE_TO_ACTOR avec gap_cm >= 15."
    }
  ],
  "gravity_errors": [],
  "scene_errors": []
}
```

### Correction Appliquee par l'Agent dans `05_props.json`
```json
{
  "actor_label": "Weapon_Vending_01",
  "asset_key": "device_vending_machine",
  "placement_mode": "RELATIVE_TO_ACTOR",
  "reference_actor": "Wall_North_02",
  "direction": "IN_FRONT_OF",
  "gap_cm": 15.0,
  "face_towards": "SOUTH",
  "snap_to_floor": true
}
```
Attention : une entree de `05_props.json` est posee par `Scene.add_to_scene_from_asset`. Un device creatif doit rester dans `04_devices.json` (pose par `Device.PlaceDevice`), sinon il perd son comportement. Le deplacement d'un device se fait donc en repositionnant l'entree de `04_devices.json`, puis `compile-transforms` et `place-scene`.
Un acteur deja place est saute par `place-scene` (il est dans `_placed.json`) : pour le deplacer, soit corriger la transform avec `Actor.set_actor_transform`, soit le supprimer (`Scene.remove_from_scene`) et retirer sa ligne de `_placed.json` avant de relancer.

---

## Cas 5 : Correction Automatique d'un Objet Flottant ou Enterre (`GRAVITY_ERROR`)

### Rapport d'Erreur (`06_audit_report.json`, produit par `audit-scene --live`)
Seul `--live` peut sortir cette erreur : il remplace les centres calcules par les bounds relus dans l'editeur. Un `audit-scene` hors ligne ne detecte jamais un objet flottant (`gravity_scope` le rappelle dans le rapport).
```json
{
  "status": "FAILED",
  "error_count": 1,
  "overlap_errors": [],
  "gravity_errors": [
    {
      "type": "GRAVITY_ERROR",
      "actor": "Cyber_Table_01",
      "distance_to_floor_cm": 58.5,
      "state": "FLOATING",
      "tile": [3, 3, 0],
      "floor_reference": "bounds du sol",
      "suggestion": "Remesurer pivot_offset_cm (measure-palette --force) ou corriger snap_to_floor."
    }
  ],
  "scene_errors": []
}
```
Un ecart constant sur tous les objets d'un meme asset designe un mauvais `pivot_offset_cm`, pas une erreur de grille : relancer `measure-palette --force` puis `compile-transforms`.

### Correction Appliquee par l'Agent dans `05_props.json`
```json
{
  "actor_label": "Cyber_Table_01",
  "asset_key": "prop_cyber_table",
  "placement_mode": "TILE_ANCHOR",
  "tile": [3, 3, 0],
  "slot": "CENTER",
  "face_towards": "NORTH",
  "snap_to_floor": true
}
```

---

## Cas 6 : Correction d'un Couloir Bouche ou d'un Escalier sans Tremie (`CORRIDOR_TOO_NARROW`)

### Rapport d'Erreur (`06_navigation_report.json`, produit par `check-navigation`)
```json
{
  "timestamp": "2026-10-20T01:05:00+00:00",
  "command": "check-navigation",
  "status": "FAILED",
  "error_count": 1,
  "navigation_errors": [
    {
      "type": "CORRIDOR_TOO_NARROW",
      "tile": [2, 1, 0],
      "free_width_cm": 64.0,
      "required_width_cm": 100.0,
      "blocking_actors": ["Generator_Prop_01", "Generator_Prop_02"]
    }
  ],
  "navigation_scope": "paires de props dans une meme tuile ; pas de capsule, pas de murs, pas de devices, pas de passages entre tuiles",
  "other_report": "chevauchements et gravite : 06_audit_report.json (audit-scene), non recalcule ici"
}
```

### Corrections Appliquees par l'Agent
1. **Dans `05_props.json`** : Supprimer `Generator_Prop_02` et deplacer `Generator_Prop_01` sur l'ancre `"slot": "WEST_EDGE"` pour degager le passage au centre de la tuile `[2, 1, 0]`.
2. **Dans `03_grid.json`** : Remplacer la cellule `[3, 2]` de l'etage `z_index: 1` par `"T"` (`OPEN_STAIRWELL`) pour supprimer la dalle de plafond qui bloquait la sortie de l'escalier. Cette erreur (`HEADROOM_BLOCKED_ON_STAIRS`) est signalee par `validate-grid`, pas par le rapport de navigation : elle n'apparait qu'en sortie propre, avec le code retour 1.

### Ou trouves tu ces erreurs
- `CORRIDOR_TOO_NARROW` vient de `check-navigation`, dans `navigation_errors` de `06_navigation_report.json`. Le rapport ne nomme pas les extremites du trajet (`from` / `to` n'existent pas) : il donne `tile`, `free_width_cm`, `required_width_cm` et les deux `blocking_actors`.
- `HEADROOM_BLOCKED_ON_STAIRS` vient de `validate-grid` (sortie propre, code retour 1), pas d'un rapport d'audit.
- `check-navigation` n'ecrit plus dans `06_audit_report.json` : les deux rapports sont separes, chacun avec son propre `status` coherent avec son code retour.
- apres un deplacement, relancer la chaine complete : `compile-transforms`, `place-scene` (ou repositionnement a la main), `audit-scene --live`, `check-navigation`.