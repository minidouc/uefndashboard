# UI_Programmer — outils (allowlist)

> **Tool Definitions** (WP3 p.8) + borne de sécurité (WP2 p.47 *least privilege*,
> `util/multi_agent/05-securite-mcp.md`).
> Point d'entrée unique : `python script/uefn_spatial_cli.py <commande> --workspace <absolu>`.
> Le CLI est le gateway : **commande absente de cette page = appel refusé**, pas « à tenter quand
> même ». Codes retour : `0` PASSED · `1` FAILED (**traité** : relire avant de rejouer) · `2` OFFLINE
> (rien d'exécuté) · `3` TIMEOUT (état inconnu : relire, jamais relancer à l'aveugle).

## Autorisé — lecture et validation (aucun effet de bord)

| Commande | Quand / pourquoi | Entrée | Sortie à savoir lire |
|---|---|---|---|
| `verse-scan` | **avant** toute écriture : état réel des `.verse` du projet | `--root`, `--recursive` | `_verse_files.json` (`count`, `files`, `warning` si vide) |
| `verse-grep` | vérifier **chaque** signature de 12/13 que je m'apprête à appeler | `--symbols A,B` ou `--pattern` + `--glob` | `_verse_grep.json` : `resolved`, `not_found`, `scope` |
| `list-editables` *(sans `--apply`)* | table `@editable` → `actor_label` → `refPath` de mon device UI | `--live --device <label>` pour lire `list_properties` | `10_editables.json` : `editable_count`, `actor_references`, `parameters`, `without_target`, `mapping`, bloc `live`, `scope` |
| `preflight` | pont joignable, pagination à 200, état de session | workspace | `Disconnected` exigé avant `verse-build` |
| `audit-scene` *(hors ligne, lecture)* | vérifier qu'un device UI référencé existe bien dans les specs | specs + `_placed.json` | `06_audit_report.json` (`source: "spec"` **ne prouve pas** la scène) |

## Autorisé — écriture (gate HITL, effet de bord, relecture obligatoire)

| Commande | Quand / pourquoi | Paramètres clés | Effet de bord | Relecture obligatoire |
|---|---|---|---|---|
| `verse-write` | créer `ui_hud.verse` / `ui_menus.verse`, **uniquement** ceux listés dans `02_palette.json` → `verse_architecture` | `--file <local>` `--path <chemin projet>` **`--i-agree-to-modify-project`** | écrit le **code source du projet** (`VerseToolset.WriteFile`, classé DANGEREUX) | `read_back_matches: true` (`Verse.ReadFile`) + historique `_verse_written.json` — sinon **on ne compile pas** |
| `verse-build` | compiler après écriture relue | `--log-entries N` (défaut 15) ; session **`Disconnected`** exigée | `Verse.BuildAll` (relance la compilation du projet) | diagnostics **et** ligne de succès récente dans `Logs.GetLogEntries` catégorie `VerseBuild` → `09_verse_report.json` |
| `wire-devices` | câbler les Direct Events de **mon** device UI | `--dry-run` d'abord ; `--allow-empty` si toute la logique est en Verse | crée des liens événement → fonction | `ListEventBindings` **sur la cible** → `08_wiring_report.json` |
| `list-editables --apply` | câbler automatiquement mes `@editable` d'acteur (`savedActor`) | exige le device Verse posé (`Game_Manager_01` sinon `DEVICE_NOT_PLACED`) | pose un device et écrit des propriétés | `GetDeviceProperties` / `get_properties` → `wiring: "AUTO_VERIFIED"`, sinon `MANUEL` + `wiring_errors` |

## Interdit pour ce rôle

| Outil / commande | Propriétaire | Pourquoi |
|---|---|---|
| `build-structure`, `place-scene`, `compile-transforms`, `audit-scene --live`, `check-navigation`, `check-symmetry` | `Physics_Programmer` (16) | je ne déplace **rien** dans la scène 3D |
| `apply-properties` sur un device de gameplay ou d'ambiance | `Graphics_Programmer` (15) / agents 12-13 | je n'affiche pas, je ne règle pas |
| `measure-palette`, publication de `verse_architecture` | `Lead_Programmer` (11) | la liste des fichiers `.verse` n'est pas ma source |
| écriture dans `game_manager.verse` ou tout `.verse` d'un autre agent | 12 / 13 | hors périmètre : remontée au Producteur, jamais un patch |
| `check-validator` sans `--no-save`, `Asset.save_assets`, `Scene.save_actor`, publication (aucun outil MCP : faite à la main), `launch-session`, `cleanup` | Producteur via gate HITL utilisateur | destructeur / publication |
| `GetDynamicInputSchema` hors session | — | crashe l'éditeur (mémoire de projet) |
| `batch.exec`, `editor.undo`, `validate_folder`, Bridge `:9210`, `.t3d` | — | **n'existent pas** : mentions caduques |
| Toolsets Niagara / matériaux (`set_material`, `MaterialInstanceTools.create`) | `Graphics_Programmer` | hors périmètre et jamais testés |

## Toolsets MCP sous le CLI (pour comprendre, pas pour appeler en direct)

- **VerseToolset** (`Verse.ListFiles`, `Verse.Grep`, `Verse.ReadFile`, `Verse.WriteFile`,
  `Verse.BuildAll`) — mon outillage principal. `WriteFile` = effet de bord sur le code du projet.
- **SessionToolset** (`Session.GetSessionStatus`) — garde-fou préalable à `verse-build`
  (`Disconnected` attendu ; `Connecting` / `UpdatingContent` / `Connected` = STOP).
- **LogsToolset** (`Logs.GetLogEntries {"category":"VerseBuild"}`) — la ligne de succès. Attention :
  la catégorie littérale `Valkyrie` n'existe pas (`Log category 'Valkyrie' not found`), les vraies
  sont `LogValkyrie`, `LogValkyrieValidation`.
- **DeviceToolset** (`Device.GetBindingOptions`, `AddEventBinding`, `ListEventBindings`,
  `ListDeviceAssets`, `ListDeviceProperties`, `GetDeviceProperties`, `SetDeviceProperty`) — câblage.
  Les deux derniers restent **UNKNOWN** sur un `creative_device` : jamais présentés comme fiables.
- **ObjectTools** (`list_properties`, `get_properties`, `set_properties`) — lecture de mes
  `@editable` et écriture de `savedActor` en mode `--apply`. `values` est une **chaîne JSON**.

**Règle transversale** : `inputSchema` **et** `outputSchema` sont validés côté client avant de tenir
un appel pour réussi (WP2 p.26/p.29). Une sortie > 4000 tokens (inventaire `verse-scan`, log
`VerseBuild`, table `mapping`) est redirigée vers un fichier et je ne transmets que son chemin
(WP2 p.19/p.44). `isError`, sortie vide ou incohérente = STOP et statut `UNKNOWN`, jamais
« continuer comme si ça avait marché » (WP4 p.20).
