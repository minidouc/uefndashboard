# Tool output — `measure-palette` (spawn, bounds, destruction, orphelin)

> **Tool Outputs** (WP3 p.8). Sorties **brutes réelles** du run UEFN documenté (Corpo Plaza,
> 2026-10-23/24, niveau `claudtest`), tirées de `ws_corpo_plaza\_mcp_calls.jsonl`, puis la lecture
> que j'en fais.

## 1. Le spawn de mesure, tel qu'il part

```json
// SceneTools.add_to_scene_from_asset
{"asset_path": "/Engine/BasicShapes/Cube",
 "name": "MEASURE_structure_floor",
 "xform": {"location": {"x": 0.0, "y": -20000.0, "z": 5000.0},
           "rotation": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
           "scale": {"x": 1.0, "y": 1.0, "z": 1.0}},
 "snap_to_ground": false}
// réponse
{"returnValue": {"refPath": "/dc587e05-5351-4d88-b9bd-dc21fbb17a81/claudtest.claudtest:PersistentLevel.StaticMeshActor_UAID_…"}}
// isError: false   duration_ms: 316
```

**Lecture :** la mesure se pose **hors zone de jeu** (`y = -20000`), à yaw 0, `snap_to_ground:
false`. La spec de l'agent 11 dit « spawn en `(0, 0, 0)` » : la valeur **appliquée** par le harnais
est celle du journal, et l'écart est consigné dans `level_state_after.spawn_reference`. Le
`refPath` retourné est **noté** : c'est par lui que la destruction se fait.

## 2. Les bounds : la seule taille qui compte

```json
// ActorTools.get_actor_bounds — bassin (MEASURE_basin, vague 2)
{"actor": {"refPath": "/dc587e05-…/claudtest.claudtest:PersistentLevel.Mall_Fountain_Whole_NoFX_C_UAID_08F97E52BCAA070E03_1879050866"}}
// réponse (isError false, 331 ms)
{"returnValue": {"min": {"x": -500.16820650915071, "y": -20500.167941839507, "z": 4999.9720458984375},
                 "max": {"x":  500.16763305664057, "y": -19499.831484711212, "z": 5512},
                 "isValid": true}}
```

**Lecture :** `size_cm = max − min` → **1000.34 × 1000.34 × 512.03** (valeur écrite dans
`02_palette.json`). Le centre des bounds moins la position de l'acteur donne `pivot_offset_cm`
`[0.0, 0.0, 255.99]` → pivot **BOTTOM**. Rien n'est arrondi : 1000.34 n'est pas 1000.

## 3. Le piège des bornes nulles (PID de tours)

```json
// ActorTools.get_actor_bounds — PID_CP_Sunburst_Building_a (conteneur de playset)
{"returnValue": {"min": {"x": 0, "y": 0, "z": 0}, "max": {"x": 0, "y": 0, "z": 0}, "isValid": true}}
// isError: false   duration_ms: 301
```

**Lecture :** `isValid: true` **ne veut pas dire mesurable**. Un `FortPlaysetRoot` rend une boîte
nulle : ce n'est pas une taille de 0 cm, c'est un asset **non mesurable**. Conduite : suppression
immédiate, remplacement par le `PPID` de la même famille (`PPID_CRP_Sunburst_CP_Building_Scifi_01`,
mesuré 9561.23 × 3141.13 × 24484.3), trace dans `blocked_assets` avec `NULL_BOUNDS`. **Quatre PID
consécutifs ont rendu le même cas** dans ce run (23:54:24 → 23:58:04), ce n'est pas un accident.

## 4. Orphelin après `WinError 10054` : relire, puis supprimer par `refPath`

```json
// SceneTools.find_actors (après un code 3 sur la mesure du bassin)
{"name": "MEASURE_"}
// réponse (isError false, 368 ms) — un acteur reste dans le niveau
{"returnValue": [{
  "guid": "DFED0C5E-4E08-030D-FF43-8199EFB8CCF3",
  "nativeClass": {"refPath": "/Game/Building/ActorBlueprints/Mall/Props/Mall_Fountain_Whole_NoFX.Mall_Fountain_Whole_NoFX_C"},
  "name": "Mall_Fountain_Whole_NoFX_C_UAID_08F97E52BCAA070E03_1454350865",
  "label": "MEASURE_basin",
  "bounds": {"min": {"x": -500.168…, "y": -20500.168…, "z": 4999.972},
             "max": {"x": 500.167…, "y": -19499.831…, "z": 5512}, "isValid": true},
  "actorPath": "/dc587e05-…/claudtest.claudtest:PersistentLevel.Mall_Fountain_Whole_NoFX_C_UAID_08F97E52BCAA070E03_1454350865"
}]}

// SceneTools.remove_from_scene — ciblage PAR refPath, jamais par label
{"actor": {"refPath": "/dc587e05-…/claudtest.claudtest:PersistentLevel.Mall_Fountain_Whole_NoFX_C_UAID_08F97E52BCAA070E03_1454350865"}}
// réponse
{"returnValue": true}                                   // 151 ms

// SceneTools.find_actors {"name": "MEASURE_"} — contrôle de restitution
{"returnValue": []}                                      // 83 ms → niveau rendu propre
```

**Lecture :** le `WinError 10054` (connexion réinitialisée) donne un **code 3** : la mesure est
interrompue, pas annulée. Le spawn a survécu, la destruction non. On ne rejoue **jamais** à
l'aveugle (risque : deux `MEASURE_basin` dans la scène, donc deux mesures divergentes). Ordre
obligatoire : `find_actors` → suppression par `refPath` → ré-inventaire → nouvelle mesure.

⚠️ Le `nativeClass` d'un acteur **peut** être un `/Game/...` (ici
`/Game/Building/ActorBlueprints/...`) **sans** que la palette cite ce chemin : ce qui est illégal,
c'est le `asset_path` demandé (`/Game/Athena`, `/Game/Environments`).

## 5. Yaw : la condition qui invalide une mesure

`PlaceDevice` est documenté comme **ignorant le yaw demandé** (0 demandé, 90 relu). La règle :
mesurer à yaw 0 **et relire** la transform. Si le yaw relu n'est pas 0, la mesure est **rejetée**
(`YAW_NOT_VERIFIED`), parce qu'un bound tourné est plus grand que la taille théorique — c'est
exactement la cause des 91 chevauchements vus plus tard côté `Physics_Programmer`. La correction de
pose (`set_actor_transform` puis relecture) appartient à `place-scene`, pas à la mesure.

## 6. Échecs reconnus, codes retour et messages exacts

| Sortie / message brut (ANNEXE B) | Code | Conduite dans la palette |
|---|---|---|
| `OFFLINE` · `editeur injoignable sur http://127.0.0.1:8000/mcp` | 2 | aucune mesure lancée ; renvoi à `Engine_Programmer` (`preflight_ok.json`) |
| `WinError 10054` pendant la mesure d'un asset | 3 | relecture `find_actors MEASURE_` + suppression par `refPath` avant tout rejou |
| `{"status":"FAILED","error_kind":"TIMEOUT_OUTCOME_UNKNOWN","error":"timeout 60.0s : timed out"}` | 3 | état inconnu : on ne déclare **aucune** taille pour l'asset interrompu |
| bounds `min == max == {0,0,0}` avec `isValid: true` | 1 (à mon niveau) | `NULL_BOUNDS` → remplacement PPID, jamais `size_cm: [0,0,0]` |
| `ILLEGAL_ASSET_PATH` (`/Game/Athena`, `/Game/Environments`) | 1 | bloqué et signalé, alternative proposée |
| `PALETTE_EMPTY` (aucun `requested_assets`) | 1 | je ne choisis pas les assets : `BLOCKED` vers le design |
| « Output too large » (sortie > 4000 tokens, ex. 790,8 Ko) | 0 | contenu gardé sur fichier, seul le chemin va dans le handoff |

**Transversal :** un seul appel MCP à la fois ; `inputSchema` et `outputSchema` validés côté client ;
`isError` ou sortie vide = STOP et `UNKNOWN` ; et la mission n'est **jamais** rendue tant qu'un
`MEASURE_*` traîne dans l'Outliner.
