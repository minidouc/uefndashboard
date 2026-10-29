# Tool output — `place-scene` et `build-structure`

> **Tool Outputs** (WP3 p.8). Forme **réelle** de ce que rend le harnais après une pose par batch
> (extraite du run UEFN documenté, 2026-10-24). À savoir lire avant d'annoncer quoi que ce soit.

## 1. Sortie de batch, succès complet

```json
{
  "status": "PASSED",
  "requested_props": 128,
  "placed_props": 128,
  "missing": [],
  "fallback_count": 0,
  "koi_cyan_placed": true,
  "koi_orange_placed": true,
  "towers_placed": 16
}
```

**Lecture :** `requested_props` / `placed_props` + `missing: []` = tout ce que disait la spec est
posé. `fallback_count > 0` **n'est pas** un succès neutre : chaque fallback est une entité posée
autrement que demandé → à consigner et à expliquer dans le handoff.

## 2. Ce qui est persisté par acteur (`_placed.json`)

```json
{
  "Spawner_Plaza_01": {
    "refPath": "/dc587e05-5351-4d88-b9bd-dc21fbb17a81/claudtest.claudtest:PersistentLevel.BP_Creative_Player_Spawner_Prop_C_UAID_08F97E52BCAA090E03_1884200392",
    "asset": "/CRD_PlayerSpawn/ItemDefinitions/PID_CP_Devices_PlayerSpawner.PID_CP_Devices_PlayerSpawner",
    "kind": "device",
    "xform": {
      "location": { "x": 3389.81, "y": 6897.64, "z": 128.0 },
      "rotation": { "pitch": 0.0, "yaw": 0.0, "roll": 0.0 },
      "scale": { "x": 1.0, "y": 1.0, "z": 1.0 }
    }
  }
}
```

**Lecture :** la clé = `actor_label` de l'Outliner, `refPath` = l'ancre de câblage des programmeurs
Verse (alias `savedActor`), `xform` = la transform **relue**, pas la demandée. Ce fichier est la
source d'idempotence : un label qui y figure n'est **pas** re-posé.

## 3. Échecs que je sais reconnaître

| Sortie | Signification | Conduite |
|---|---|---|
| code `2`, `editeur injoignable sur http://127.0.0.1:8000/mcp` | pont hors ligne **ou** sur un autre port (8001 observé) | vérifier `UEFN_MCP_URL`, remonter à `Engine_Programmer` ; **rien n'a été exécuté** |
| code `3`, `McpTimeout` / `WinError 10054` | pose peut-être appliquée sans réponse | relire l'Outliner, chercher les acteurs **sans label**, supprimer l'orphelin **par `refPath`**, puis reprendre |
| `TRANSFORM_MISMATCH` | l'éditeur n'a pas appliqué l'échelle/rotation demandée | la taille réellement occupée n'est pas celle de la spec → corriger la spec, recompiler |
| `FLOOR_NOT_TILE_SIZED` | asset mesuré ≠ 512 × 512 en X/Y | appliquer l'échelle suggérée, passer par `Lead_Programmer` pour la palette |
| `missing: ["…"]` avec code `1` | batch **partiel** | l'appel a été traité : on ne rejoue pas le lot entier sans relire |

## 4. Preuve visuelle après pose

`visual-snapshot` rend un PNG, mais sa caméra par défaut
(`Z = max(lignes, colonnes) × 512 × 1,2`) est **trop proche** pour une grande scène : image coupée
ou surexposée = preuve inutilisable. Correction documentée : même suite d'appels
(`SetCameraTransform` → `GetCameraTransform` → `CaptureViewport`) avec caméra reculée
(ex. `location {x: 6912, y: 6912, z: 35000}`, `pitch -90`), puis **relecture de la caméra** et
contrôle de la taille du fichier. Une capture ne prouve que ce qu'elle montre : la relire.
