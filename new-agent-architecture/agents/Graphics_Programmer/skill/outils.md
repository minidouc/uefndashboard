# Graphics_Programmer — outils (allowlist)

> **Tool Definitions** (WP3 p.8) + borne de sécurité (WP2 p.47 *least privilege*,
> `util/multi_agent/05-securite-mcp.md`).
> Point d'entrée unique : `python script/uefn_spatial_cli.py <commande> --workspace <absolu>`.
> Le CLI est le gateway : **commande absente de cette page = appel refusé**, pas « à tenter quand
> même ». Codes retour : `0` PASSED · `1` FAILED (**traité** : relire avant de rejouer) · `2` OFFLINE
> (rien d'exécuté) · `3` TIMEOUT (état inconnu : relire, jamais relancer à l'aveugle).
> Attention : un code `0` ne prouve pas la **preuve** — une capture illisible sort en code `0`.

## Autorisé — lecture et validation (aucun effet de bord)

| Commande | Quand / pourquoi | Entrée | Sortie à savoir lire |
|---|---|---|---|
| `search-playsets --query "…" --type PID\|PPID\|ALL` | **en premier** : trouver les chemins exacts des devices d'ambiance | mot-clé, type, `--max-results` | `count`, `results[{name, asset_path, class}]` ; `count: 0` = **non trouvé**, pas « inexistant » |
| `audit-legality` *(lecture seule)* | **avant tout placement** : la scène reste légale après mes poses | scène live | `06_legality_report.json` : `valid_actors`, `illegal_count`, `illegal_actors` |
| `preflight` | état du pont, session, niveau monté | — | `preflight_ok.json` (`READY`) ; session ≠ `Disconnected` = écritures à risque |
| `apply-properties --dry-run` | compter ce qui sera écrit et repérer les acteurs non posés | `04_devices.json`, `_placed.json` | `DRY_RUN` + `not_placed` + le rappel « `values` en **chaîne JSON** » |
| `visual-snapshot` | preuve visuelle d'une pose ou d'un réglage | workspace | PNG + `bytes` + `camera_requested` + `camera_read_back` |
| `tools/capture_view.py` (client fourni) | cadrage maîtrisé (jour, nuit, oblique, vue joueur) | `--location x y z --pitch --yaw` | PNG + `<nom>_camera.json` (`requested` vs `read_back`) |
| `verse-scan` / `verse-grep` | **jamais** : lire du Verse n'est pas mon rôle (agents 12/13/14) | — | — |

## Autorisé — écriture dans l'éditeur (gate HITL, effet de bord, relecture obligatoire)

| Commande | Quand / pourquoi | Paramètres clés | Effet de bord | Relecture obligatoire |
|---|---|---|---|---|
| `place-scene` | pose **de mes devices d'ambiance** (`placement_mode: "WORLD"` si non spatial) | specs compilées, `_placed.json` | crée des acteurs | `requested` vs `placed`, `missing`, `fallback_count`, `refPath` persisté |
| `apply-properties` | régler heure du jour, couleur, intensité, densité de brouillard | `properties` de `04_devices.json` | **écrit des valeurs** | `get_properties` : chaque ligne `applied` porte `written` **et** `read_back` |
| `audit-legality --fix` | uniquement sur décision Producteur : remplacer des acteurs illégaux | `--remove-unmatched` est **plus** destructeur | remplace/supprime | inventaire avant/après + nouveau rapport |
| Suppression d'un orphelin | après un timeout (code 3) ayant laissé un acteur **sans label** | `refPath` **uniquement** | détruit un acteur | Outliner relu, `05_visuals.json` corrigé |
| Save / snapshot éditeur | préalable à toute écriture destructrice | — | modifie le projet | accord explicite du Producteur (HITL) |

## Interdit pour ce rôle

| Outil / commande | Propriétaire | Pourquoi |
|---|---|---|
| `build-structure`, `compile-transforms`, `validate-grid`, `validate-scene`, `place-scene` **sur la structure/les props**, `audit-scene --live`, `check-navigation`, `check-symmetry` | `Physics_Programmer` (16) | je n'habille pas une géométrie que je n'ai pas posée ni auditée |
| `verse-scan`, `verse-grep`, `verse-write`, `verse-build`, `list-editables`, `wire-devices` | 12 / 13 / 14 | **aucun** code Verse, **aucun** câblage |
| `measure-palette` | `Lead_Programmer` (11) | tailles et pivots **mesurés** ne sont pas ma source |
| `apply-properties` sur un device de gameplay ou un device Verse | 12 / 13 (via `UI_Programmer` pour l'UI) | hors périmètre ; `SetDeviceProperty` n'est en plus **jamais prouvé** sur un `creative_device` |
| `launch-session`, `StartSession`/`PushChanges`/`StopSession`, `Save`/`SaveAll`, `Publish`, `cleanup` | `Producer_Orchestrator` via gate HITL utilisateur | destructeur / publication ; `StartSession` a déjà bloqué le pont |
| `MaterialInstanceTools.create`, `MaterialInstanceTools.set_*` | aucun, tant que `Engine_Programmer` + Producer n'ont pas donné accord **et** save | classés DANGEREUX_NON_TESTES |
| Toolsets Niagara / UMG / effets-ui | hors périmètre | deux outils sur trois inconnus dans ce montage |
| `GetDynamicInputSchema` hors session | — | crashe l'éditeur |
| `batch.exec`, `editor.undo`, `validate_folder`, `validate_selected`, pont Bridge `:9210`, export `.t3d` | — | **n'existent pas** : mentions caduques |
| Recherche ou pose dans `/Game/Athena`, `/Game/Environments` | — | `ILLEGAL_ASSET_PATH` : ferait échouer la validation d'île |

## Toolsets MCP sous le CLI (pour comprendre, pas pour appeler en direct)

- **EditorAppToolset** — `SetCameraTransform`, `GetCameraTransform`, `CaptureViewport` : la chaîne de
  preuve visuelle, la seule vraiment **vérifiée** de mon périmètre rendu.
- **ObjectTools / VerseFieldsToolset** — `list_properties`, `set_properties`, `get_properties`.
  Piège permanent : `set_properties` attend `values` en **chaîne JSON**, pas un objet.
- **DeviceToolset** — `ListDeviceAssets`, `PlaceDevice`, `GetDeviceProperties`, `SetDeviceProperty`
  (ce dernier : **UNKNOWN** sur un `creative_device`, jamais testé).
- **SceneTools / ActorTools / EntityToolset** — `add_to_scene_from_asset`,
  `add_to_scene_from_class` (classe native UE : non prouvée sur tous les types), `get_actor_bounds`,
  `get_actor_transform`, `set_actor_transform`, `set_label`, `add_tag`.
- **IslandForgeProbe** — `chercher_playsets`, `verifier_legalite_scene`, `remplacer_acteurs_illegaux`
  : le catalogue légal et la police de légalité.
- **LogsToolset** — `GetLogCategories` **puis** `GetLogEntries` (une catégorie devinée, ex.
  `Valkyrie`, renvoie « Log category not found »).

**Règle transversale** : `inputSchema` **et** `outputSchema` sont validés côté client avant de tenir
un appel pour réussi (WP2 p.26/p.29). Une sortie > 4000 tokens (catalogue à 100 résultats,
`list_toolsets` 790,8 Ko, PNG en base64) est redirigée vers un fichier et je ne transmets que son
chemin (WP2 p.19/p.44). `isError`, sortie vide ou incohérente = STOP et statut `UNKNOWN`, jamais
« continuer comme si ça avait marché » (WP4 p.20).
