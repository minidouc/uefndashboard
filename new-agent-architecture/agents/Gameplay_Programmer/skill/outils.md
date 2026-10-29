# Gameplay_Programmer — outils (allowlist)

> **Tool Definitions** (WP3 p.8) + borne de sécurité (WP2 p.47 *least privilege*,
> `util/multi_agent/05-securite-mcp.md`).
> Point d'entrée unique : `python script/uefn_spatial_cli.py <commande> --workspace <absolu>`.
> Le CLI est le gateway : **commande absente de cette page = appel refusé**, pas « à tenter quand même ».
> Codes retour : `0` PASSED · `1` FAILED (**traité** : relire avant de rejouer) · `2` OFFLINE
> (rien d'exécuté) · `3` TIMEOUT (état inconnu : relire, jamais relancer à l'aveugle).

## Autorisé — lecture et validation (aucun effet de bord)

| Commande | Quand / pourquoi | Entrée | Sortie à savoir lire |
|---|---|---|---|
| `verse-scan` | **avant** d'écrire : ce que le projet Verse contient réellement | `root: ""`, `recursive: true` | `_verse_files.json` : `files` (dossiers + `.verse`). 606 entrées pour 0 `.verse` = rien à relire |
| `verse-grep` | vérifier **chaque** signature d'API dans les digests, avant de l'appeler | `--pattern <symbole>`, `--path-glob "/Fortnite.com (Fortnite)/**"` | `_verse_grep.json` : `resolved` (avec `filePath`, `span`, `lineText`), `not_found`. Un `[]` ne prouve PAS l'absence |
| `verse-read` *(via `Verse.ReadFile`)* | relire le texte écrit ; comparer à mon fichier local | `path` du `.verse` dans le contenu monté | texte brut ; `isError` + `file does not exist: '…'.` = fichier absent |
| `list-editables` | table `@editable` → cible, **sans rien écrire** | `verse/` + `04_devices.json` + `_placed.json` | `10_editables.json` : `without_target`, `wiring_errors`, `mapping` (`kind`, `wiring`) |
| `validate-scene` | cohérence specs ↔ palette et légalité des chemins avant câblage | `02`, `04`, `05` | `ILLEGAL_ASSET_PATH`, labels en double |
| `GetSessionStatus` | **obligatoire avant `verse-build`** | — | `Disconnected` attendu ; toute autre valeur = STOP |
| `Object.list_properties` | retrouver le **nom exact** d'une propriété de device | `{"instance": {"refPath": …}}` | liste des propriétés réelles ; `PROPERTY_NOT_FOUND` renvoie `nearest` |

## Autorisé — écriture dans l'éditeur (gate HITL, save préalable)

| Commande | Quand / pourquoi | Paramètres clés | Effet de bord | Relecture obligatoire |
|---|---|---|---|---|
| `verse-write` | déposer mon `.verse` dans le projet (étape 8) | `--local-file`, `--verse-path`, **`--i-agree-to-modify-project`** | `Verse.WriteFile` (classe **DANGEREUX**) : modifie le code source du projet | `read_back_matches: true` dans `_verse_written.json` ; sinon on **ne compile pas** |
| `verse-build` | compiler le Verse du projet | `--log-entries` (15 par défaut) | `Verse.BuildAll` : recrée les classes mondiales, peut invalider les `creative_device` posés | `09_verse_report.json` : `error_diagnostics: []` **ET** `success_lines` non vide, horodatage récent |
| `list-editables --apply` | câbler une référence `@editable` → acteur posé | `--device <label>`, `--apply` | `Object.set_properties` sur `{"savedActor": {"refPath": …}}` | chaque ligne ACTEUR repassée en `AUTO_VERIFIED` ; **jamais sans accord explicite du Producer** |
| `wire-devices` | câbler les `bindings` déclarés dans `04_devices.json` | `--allow-empty` si toute la logique passe par Verse | `Device.AddEventBinding` (idempotent) | `Device.ListEventBindings` sur **la cible** → `wired[].read_back` |
| `apply-properties` | régler les propriétés de gameplay des devices (`playerTeam`, `enabledDuringPhase`, …) | `04_devices.json` → `properties` | `Object.set_properties` | `07_properties_report.json` : `written` vs `read_back` sur chaque ligne |
| `Save World` *(gate)* | verrouiller le travail avant un handoff | — | écrit le fichier de projet | statut de `Save` relu ; **accord utilisateur préalable** |

## Interdit pour ce rôle

| Outil / commande | Propriétaire | Pourquoi |
|---|---|---|
| `place-scene`, `build-structure`, `PlaceDevice`, `set_actor_transform`, `add_to_scene_from_asset` | `Physics_Programmer` (16) / `Level_Designer` | je consomme les `refPath`, je ne déplace **rien** dans la 3D |
| arbres de comportement PNJ / Gardes, `NavigateTo`, effets sur `fort_character`, caméras | `AI_Programmer` (13) | hors de mon périmètre de fichiers |
| `canvas`, `text_block`, HUD, menus | `UI_Programmer` (14) | je transmets des **valeurs**, je ne dessine pas |
| `StartSession`, `StopSession`, `PushChanges`, `Publish`, `launch-session` | `Producer_Orchestrator` via gate HITL | destructeur / publication ; `verse-build` exige `Disconnected` |
| `SetDeviceProperty`, `ListDeviceProperties`, `GetDeviceProperties` *(sur un `creative_device`)* | — | statut **« inconnu »** (`mcp_tools/devices/device-toolset.md`) : jamais testés sur un device Verse |
| `GetClientLogEntries` hors session | — | statut **« echec »** : `No client log was found; start a play-in-client session first.` |
| `Game.MutateVerb`, `SetIsReceivingCommand`, `AddHero` | — | **n'existent pas** : mentions caduques du catalogue |
| `batch.exec`, `editor.undo`, `validate_folder` | — | n'existent pas |
| `Object.search_subclasses {name:"fort_character"}` | — | crashe l'éditeur (mémoire de projet) |

## Toolsets MCP sous le CLI (pour comprendre, pas pour appeler en direct)

- **ValkyrieToolset.VerseToolset** (`verse-scan` / `verse-grep` / `verse-write` / `verse-build`) —
  `ListFiles`, `Grep`, `ReadFile`, `WriteFile` (**DANGEREUX**), `BuildAll`.
- **ValkyrieToolset.SessionToolset** — `GetSessionStatus` (lecture), `StartSession` / `StopSession` /
  `PushChanges` (gates HITL, hors de mon rôle).
- **ValkyrieToolset.DeviceToolset** — `GetBindingOptions`, `AddEventBinding`, `ListEventBindings`,
  `PlaceDevice` (hors rôle) : la preuve d'un lien se lit sur la **cible**.
- **editor_toolset.toolsets.object.ObjectTools** — `list_properties`, `get_properties`,
  `set_properties` : `values` est une **chaîne JSON**, pas un objet ; toute écriture est relue.
- **EditorToolset.LogsToolset** — `GetLogEntries` / `GetLogCategories` : catégorie réelle
  `VerseBuild` pour la compilation, `LogValkyrie` / `LogValkyrieValidation` pour la session.

**Règle transversale** : `inputSchema` **et** `outputSchema` sont validés côté client avant de
tenir un appel pour réussi (WP2 p.26/p.29). Une sortie > 4000 tokens est redirigée vers un fichier
et je ne transmets que son chemin (WP2 p.19/p.44). `isError`, sortie vide ou incohérente = STOP et
statut `UNKNOWN`, jamais « continuer comme si ça avait marché » (WP4 p.20). Un seul appel MCP à la
fois, jamais en parallèle, jamais pendant qu'un autre agent tient l'éditeur.
