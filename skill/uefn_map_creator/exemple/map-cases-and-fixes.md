# Catalogue des Cas de Figure et Corrections Automatiques UEFN

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
      "device_class": "player_spawner_device",
      "tile": [1, 1, 0],
      "slot": "NORTH_EDGE",
      "face_towards": "SOUTH",
      "on_floor": true,
      "properties": {"TeamIndex": 1}
    },
    {
      "actor_label": "Spawner_Team1_02",
      "device_class": "player_spawner_device",
      "tile": [1, 2, 0],
      "slot": "NORTH_EDGE",
      "face_towards": "SOUTH",
      "on_floor": true,
      "properties": {"TeamIndex": 1}
    },
    {
      "actor_label": "Spawner_Team2_01",
      "device_class": "player_spawner_device",
      "tile": [4, 1, 0],
      "slot": "SOUTH_EDGE",
      "face_towards": "NORTH",
      "on_floor": true,
      "properties": {"TeamIndex": 2}
    },
    {
      "actor_label": "Spawner_Team2_02",
      "device_class": "player_spawner_device",
      "tile": [4, 2, 0],
      "slot": "SOUTH_EDGE",
      "face_towards": "NORTH",
      "on_floor": true,
      "properties": {"TeamIndex": 2}
    },
    {
      "actor_label": "Barrier_Team1",
      "device_class": "barrier_device",
      "tile": [1, 1, 0],
      "slot": "SOUTH_EDGE",
      "face_towards": "SOUTH",
      "on_floor": true,
      "properties": {"BarrierWidth": 2, "BarrierHeight": 1}
    },
    {
      "actor_label": "Barrier_Team2",
      "device_class": "barrier_device",
      "tile": [4, 1, 0],
      "slot": "NORTH_EDGE",
      "face_towards": "NORTH",
      "on_floor": true,
      "properties": {"BarrierWidth": 2, "BarrierHeight": 1}
    }
  ]
}
```

---

## Cas 2 : Carte Moyenne Modulaire avec Prefabriques (Zone Wars / Mini-Ville)

### Contexte
Au lieu de poser 200 murs pour creer des maisons, on mesure un Prefabrique Fortnite entier dans `02_palette.json` (qui mesure `1536 x 1024 x 768 cm`, soit exactement `3 x 2 x 2` tuiles) et on le pose sur l'ancre `CORNER_SW` de la tuile de depart.

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
La carte totale fait `18 x 12` tuiles. Comme elle depasse `8 x 8` tuiles, l'agent a l'interdiction de tout generer en une seule fois. Il divise la carte en 3 zones connectees par des portes `P` et valide chaque zone de l'Etape 3 a l'Etape 7 avant de passer a la suivante.

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

### Rapport d'Erreur (`06_audit_report.json`)
```json
{
  "status": "FAILED",
  "error_count": 1,
  "overlap_errors": [
    {
      "type": "OVERLAP_ERROR",
      "actor_a": "Weapon_Vending_01",
      "actor_b": "Wall_North_02",
      "penetration_cm": 42.0,
      "tile": [0, 2, 0],
      "suggestion": "Place Weapon_Vending_01 using RELATIVE_TO_ACTOR IN_FRONT_OF Wall_North_02 with gap_cm >= 10.0"
    }
  ],
  "gravity_errors": [],
  "navigation_errors": []
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

---

## Cas 5 : Correction Automatique d'un Objet Flottant ou Enterre (`GRAVITY_ERROR`)

### Rapport d'Erreur (`06_audit_report.json`)
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
      "suggestion": "Enable snap_to_floor: true and apply pivot_offset_cm Z correction from 02_palette.json"
    }
  ],
  "navigation_errors": []
}
```

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

## Cas 6 : Correction d'un Couloir Bouche ou d'un Escalier sans Tremie (`NAV_BLOCKED`)

### Rapport d'Erreur (`06_audit_report.json`)
```json
{
  "status": "FAILED",
  "error_count": 2,
  "overlap_errors": [],
  "gravity_errors": [],
  "navigation_errors": [
    {
      "type": "CORRIDOR_TOO_NARROW",
      "from": "Spawner_Team1_01",
      "to": "Objective_Main",
      "tile": [2, 1, 0],
      "free_width_cm": 64.0,
      "required_width_cm": 100.0,
      "blocking_actors": ["Generator_Prop_01", "Generator_Prop_02"]
    },
    {
      "type": "HEADROOM_BLOCKED_ON_STAIRS",
      "stair_tile": [3, 2, 0],
      "upper_tile": [3, 2, 1],
      "current_upper_cell": ".",
      "required_upper_cell": "T"
    }
  ]
}
```

### Corrections Appliquees par l'Agent
1. **Dans `05_props.json`** : Supprimer `Generator_Prop_02` et deplacer `Generator_Prop_01` sur l'ancre `"slot": "WEST_EDGE"` pour degager `390 cm` de passage au centre de la tuile `[2, 1, 0]`.
2. **Dans `03_grid.json`** : Remplacer la cellule `[3, 2]` de l'etage `z_index: 1` par `"T"` (`OPEN_STAIRWELL`) pour supprimer la dalle de plafond qui bloquait la sortie de l'escalier.