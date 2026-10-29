# Lead_Programmer — outils (allowlist)

> **Tool Definitions** (WP3 p.8) + borne de sécurité (WP2 p.47 *least privilege*,
> `util/multi_agent/05-securite-mcp.md`).
> Point d'entrée unique : `python script/uefn_spatial_cli.py <commande> --workspace <absolu>`.
> Le CLI est le gateway : **commande absente de cette page = appel refusé**, pas « à tenter quand même ».
> Codes retour : `0` PASSED · `1` FAILED (**traité** : relire avant de rejouer) · `2` OFFLINE
> (rien d'exécuté) · `3` TIMEOUT (état inconnu : relire, jamais relancer à l'aveugle).
> Mon accès MCP est **lecture + écriture de mesure uniquement** : je ne pose rien de définitif.

## Autorisé — lecture et validation (aucun effet de bord)

| Commande / outil | Quand / pourquoi | Paramètres clés | Sortie à savoir lire |
|---|---|---|---|
| `search-playsets` | trouver un asset **légal** dans le catalogue exposé | `--type PPID\|PID\|ALL`, motif | `status`, `count`, `results[].asset_path`, `class` (`FortPlaysetPropItemDefinition` / `FortPlaysetItemDefinition`) ; fichier `search_<motif>.json` conservé |
| `list-devices` / `Device.ListDeviceAssets` | retrouver l'`asset_path` **exact** d'un device | type de device | liste de `PID_*` ; un device absent = `DEVICE_ASSET_NOT_FOUND`, pas un chemin approximatif |
| `Scene.find_actors` | vérifier l'état du niveau avant/après mesure | `{"name": "MEASURE_"}` | `returnValue: []` = niveau propre ; sinon liste des orphelins avec `refPath` |
| `ActorTools.get_actor_bounds` | la **mesure** : boîte alignée aux axes d'un acteur posé | `{"actor": {"refPath": ...}}` | `{min, max, isValid}` ; `size_cm = max − min` ; ⚠️ `min == max == 0` avec `isValid: true` = asset non mesurable |
| `ActorTools.get_actor_transform` | relecture de la pose et **du yaw** | `{"actor": {"refPath": ...}}` | transform relue ; yaw ≠ yaw demandé ⇒ mesure rejetée |
| `Scene.get_current_level` | confirmer sur quel niveau je mesure | `{}` | `returnValue: "/<guide>/<niveau>"` (ex. `claudtest`) |
| `ValkyrieToolset.SessionToolset.GetSessionStatus` | vérifier que la session autorise les écritures | `{}` | `Disconnected` / `Connected` |
| `verse-scan`, `verse-grep`, `Verse.ReadFile` | **lecture seule** pour arbitrer `verse_architecture` (fichiers existants, signatures consommées) | workspace, motif | état des `.verse` du projet ; ⚠️ une réponse `[]` ne prouve **pas** une absence |
| `preflight_ok.json`, `01_gdd.json` | mes conditions d'entrée | workspace | `status: "READY"` ; `requested_assets` (liste à mesurer) |

## Autorisé — écriture dans l'éditeur (gate HITL, save préalable)

| Commande / outil | Quand / pourquoi | Paramètres clés | Effet de bord | Relecture obligatoire |
|---|---|---|---|---|
| `measure-palette` | la commande qui **produit** `02_palette.json` : spawn temporaire → bounds → destruction | `--workspace`, `--force` pour re-mesurer, un asset à la fois | crée **puis détruit** un acteur `MEASURE_<asset_key>` | `size_cm`, `pivot_offset_cm`, `measured: {at, kind}` écrits par l'outil ; `find_actors "MEASURE_"` ⇒ `[]` |
| `add_to_scene_from_asset` *(dans le seul cadre d'une mesure)* | poser l'asset à mesurer hors zone de jeu | `asset_path`, `name: "MEASURE_…"`, xform `(0,-20000,5000)`, `snap_to_ground: false` | crée un acteur temporaire | `returnValue.refPath` noté, puis bounds |
| `PlaceDevice` *(dans le seul cadre d'une mesure)* | mesurer un device (`kind: "device"`) | `{"assetPath": {"refPath"}, "transform"}` | crée un device temporaire | yaw relu (`PlaceDevice` est connu pour ignorer le yaw demandé) puis bounds |
| `remove_from_scene` | détruire **immédiatement** ce qui vient d'être mesuré | `{"actor": {"refPath": …}}` — **jamais** par label | **destructif**, limité aux acteurs `MEASURE_*` créés par moi | `returnValue: true` puis `find_actors` |
| écriture de mes artefacts | `02_palette.json`, `search_<motif>.json`, `tech/architecture.md` | chemin absolu du workspace | crée/écrit des fichiers de **sortie** | relecture du fichier écrit + validation JSON par le code du pipeline |

## Interdit pour ce rôle

| Outil / commande | Propriétaire réel | Pourquoi |
|---|---|---|
| `place-scene`, `build-structure` | `Physics_Programmer` | je mesure des assets, je ne construis pas le niveau |
| `compile-transforms`, `validate-grid` | `Physics_Programmer` / le harnais | aucune transform de pose ne sort de moi |
| `audit-scene --live`, `check-navigation`, `check-symmetry` | `Physics_Programmer` | collisions et flottants ne sont pas ma preuve |
| `apply-properties` | `Graphics_Programmer` (ambiance) / 12 (gameplay) | je ne règle aucun device |
| `wire-devices`, `list-editables`, `verse-write`, `verse-build` | 12 / 13 / 14 | je **déclare** des signatures et des fichiers, je n'écris aucune logique Verse |
| `cleanup` | `Producer_Orchestrator` (décision) / `Engine_Programmer` (exécution) | destructif hors mesure : jamais de mon initiative |
| `launch-session`, `Save`/`SaveAll`, `Publish` | `Producer_Orchestrator` via gate HITL utilisateur | ouverture de session et publication |
| `Asset.find_assets` dans `/Game/Athena`, `/Game/Environments` | — | assets Epic non exposés → `ILLEGAL_ASSET_PATH`, échec de validation d'île |
| `GetDynamicInputSchema` hors session | — | **crash connu de l'éditeur** : les schémas se lisent dans la doc de skill |
| `batch.exec`, `editor.undo`, `validate_folder` | — | **n'existent pas** : mentions caduques à ne pas promettre |

## Toolsets MCP sous le CLI (pour comprendre, pas pour appeler en direct)

- **SceneTools** — `add_to_scene_from_asset`, `find_actors`, `remove_from_scene` : le cycle de mesure.
- **ActorTools** — `get_actor_bounds`, `get_actor_transform`, `set_actor_transform`, `add_tag`
  (un acteur se passe **toujours** par `{"refPath": "<chemin complet>"}`, jamais par un label).
- **DeviceToolset / ValkyrieToolset.DeviceToolset** — `ListDeviceAssets`, `PlaceDevice`.
- **IslandForgeProbe** — `chercher_playsets` : la recherche de catalogue (PPID / PID).
- **ValkyrieToolset.VerseToolset** — `ListFiles`, lecture des `.verse` ; **écriture** réservée à 12/13/14.
- **ValkyrieToolset.SessionToolset / EditorAppToolset** — état de session et de l'éditeur : je lis, je
  ne répare pas (c'est `Engine_Programmer`).

**Règle transversale** : `inputSchema` **et** `outputSchema` sont validés côté client avant de tenir
un appel pour réussi (WP2 p.26/p.29). Une sortie > 4000 tokens est redirigée vers un fichier et je ne
transmets que son chemin (WP2 p.19/p.44). `isError`, sortie vide ou incohérente = **STOP** et statut
`UNKNOWN` (WP4 p.20). Un seul appel MCP à la fois, et je ne conserve dans la palette **que** ce que
les bornes ont réellement rendu.
