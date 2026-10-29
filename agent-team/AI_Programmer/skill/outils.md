# AI_Programmer — outils (allowlist)

> **Tool Definitions** (WP3 p.8) + borne de sécurité (WP2 p.47 *least privilege*,
> `util/multi_agent/05-securite-mcp.md`).
> Point d'entrée unique : `python script/uefn_spatial_cli.py <commande> --workspace <absolu>`.
> Le CLI est le gateway : **commande absente de cette page = appel refusé** (`UNKNOWN_TOOL_BLOCKED`
> remonté au Producer), pas « à tenter quand même ».
> Codes retour : `0` PASSED · `1` FAILED (**traité** : relire avant de rejouer) · `2` OFFLINE
> (rien d'exécuté) · `3` TIMEOUT (état inconnu : relire, jamais relancer à l'aveugle).

## Autorisé — lecture et validation (aucun effet de bord)

| Commande | Quand / pourquoi | Entrée | Sortie à savoir lire |
|---|---|---|---|
| `verse-scan` | **avant** toute écriture : ce que le projet Verse contient réellement | `--root ""` `--recursive` | `_verse_files.json` : `files` (dossiers + `.verse`). 606 entrées pour 0 `.verse` = rien à relire |
| `verse-grep` | vérifier **chaque** signature que j'appelle (`MoveTo`, `Damage`, `Hide`, `NavigateTo`…) | `--symbols a,b` ou `--pattern`, `--path-glob "/Fortnite.com (Fortnite)/**"` | `_verse_grep.json` : `resolved` (`filePath`, `span`, `lineText`), `not_found`. Un `[]` ne prouve PAS l'absence |
| `verse-read --path <chemin>` *(via `Verse.ReadFile`)* | relire le texte écrit ; comparer à mon fichier local | `path` du `.verse` monté | texte brut ; `isError` + `file does not exist: '…'.` = fichier absent (expected avant écriture) |
| `GetSessionStatus` | **obligatoire avant `verse-build`** | — | `Disconnected` attendu ; toute autre valeur = STOP |
| `list-editables` | table `@editable` → cible, **sans rien écrire** | `verse/` + `04_devices.json` + `_placed.json` | `10_editables.json` : `without_target`, `wiring_errors`, `mapping` (`kind`, `wiring`) ; `NO_VERSE_STAGED` si rien n'est stageable |
| `Object.list_properties` / `get_properties` | retrouver le **nom exact** d'une propriété, relire une valeur | `{"instance": {"refPath": …}}` | liste réelle (parfois avec espaces : `interaction Text`) ; `PROPERTY_NOT_FOUND` + `nearest` |
| `Device.GetBindingOptions` | chaîner **exactement** `sourceEvents` / `targetFunctions` avant binding | `{"devicePath": {"refPath": source}}` | `{"sourceEvents": […], "targetFunctions": […]}` |
| `Device.ListEventBindings` | **la preuve** d'un lien, lue sur la **cible** | refPath du device cible | bindings présents ; un `null` côté `AddEventBinding` ne prouve rien |
| `Logs.GetLogEntries` / `GetLogCategories` | recouper `VerseBuild` après build ; logs de session | `{"category":"VerseBuild","maxEntries":15}` | lignes **localisées** (« Compilation terminée. ») ; catégorie `Valkyrie` inexistante → `LogValkyrie` |
| `validate-scene` | cohérence specs ↔ palette et légalité des chemins avant câblage | `02`, `04`, `05` | `ILLEGAL_ASSET_PATH`, labels en double |

## Autorisé — écriture dans l'éditeur (gate HITL, save préalable)

| Commande | Quand / pourquoi | Paramètres clés | Effet de bord | Relecture obligatoire |
|---|---|---|---|---|
| `verse-write` | déposer **mon** `.verse` de mécanique | `--local-file`, `--path`, **`--i-agree-to-modify-project`** | `Verse.WriteFile` (classe **DANGEREUX**) : modifie le code source du projet ; sans accord → `CONSENT_REQUIRED`, code `1` | `read_back_matches: true` + `bytes` dans `_verse_written.json` ; sinon **on ne compile pas** |
| `verse-build` | compiler le Verse du projet | `--log-entries` (15 par défaut) | `Verse.BuildAll` : recrée les classes mondiales, **compile tout le projet**, peut invalider les `creative_device` posés | `09_verse_report.json` : `error_diagnostics: []` **ET** `success_lines` horodatée après l'appel |
| `list-editables --apply` | câbler une référence `@editable` → acteur posé, et poser le `creative_device` des mécaniques en `Zone_Logic` | `--device <label>`, `--apply` | `Device.SetDeviceProperty` / `Object.set_properties` sur `{"savedActor": {"refPath": …}}` | chaque ligne ACTEUR repassée en `AUTO_VERIFIED` ; **jamais sans accord explicite du Producer** |
| `wire-devices` | câbler les `bindings` de **mes** devices déclarés dans `04_devices.json` | `--dry-run` d'abord, `--allow-empty` si toute la logique passe par Verse | `Device.AddEventBinding` (idempotent) | `Device.ListEventBindings` sur **la cible** → `wired[].read_back` (`08_wiring_report.json`) |
| `apply-properties` | régler **mes** devices de mécanique (button, trigger, spawner d'input, granter) | `04_devices.json` → `properties` | `Object.set_properties` (`values` = **chaîne JSON**) | `07_properties_report.json` : `written` vs `read_back` sur chaque ligne ; `not_placed` = aucun appel reçu |
| `Save World` *(gate)* | verrouiller avant un handoff ou une demande de session | — | écrit le fichier de projet | statut de `Save` relu ; **accord utilisateur préalable via le Producer** |

## Interdit pour ce rôle

| Outil / commande | Propriétaire réel | Pourquoi |
|---|---|---|
| `place-scene`, `build-structure`, `PlaceDevice`, `add_to_scene_from_asset`, `set_actor_transform`, `apply_physics`, `cleanup` | `Physics_Programmer` (16) | je consomme les `refPath`, je ne déplace et ne pose **rien** dans la 3D |
| `measure-palette`, `search-playsets`, `verse_architecture` | `Lead_Programmer` (11) | la palette et la répartition des fichiers ne sont pas ma source |
| `03_grid.json` (matrice, zones) | `Level_Designer` (09) | je lis les zones d'action, je ne les redessine pas |
| `game_manager_device.verse`, boucle globale, économie, boutique, quêtes, sauvegarde, timers | `Gameplay_Programmer` (12) | j'**appelle** ses fonctions et je lui **rend** des événements |
| `ui_hud.verse`, `ui_menus.verse`, `canvas`, `text_block`, menus | `UI_Programmer` (14) | j'expose des **valeurs** (`values_for_agent14`), je ne dessine pas |
| `StartSession`, `StopSession`, `PushChanges`, `launch-session`, publication (aucun outil MCP : faite à la main) | `Producer_Orchestrator` (gate HITL utilisateur) | destructeur / publication ; et `verse-build` exige `Disconnected` |
| `SetDeviceProperty`, `ListDeviceProperties`, `GetDeviceProperties` *(hors flux `list-editables --apply`)* | — | statut **« inconnu »** sur un device Verse : jamais revérifiés hors ce chemin |
| `GetClientLogEntries` hors session | — | statut **« echec »** : `No client log was found; start a play-in-client session first.` |
| `GetDynamicInputSchema` hors session | — | **crashe l'éditeur** (mémoire de projet) |
| `Object.search_subclasses {"name":"fort_character"}` | — | crash éditeur signalé : je passe par le digest Verse |
| `batch.exec`, `editor.undo`, `validate_folder`, `verse.set_property`, injection `.t3d` | — | **n'existent pas** : mentions caduques d'un Bridge disparu |
| `WID_` posé en acteur ; juger un asset légal ou illégal d'après son chemin | — | un `WID_` s'assigne à un `item_granter_device` (recette : `Gameplay_Programmer/skill/tool-output/devices-objets-et-ile.md`) ; légalité = journal du validateur (`../../_commun/legalite-assets.md`) |
| Toolsets `effets-ui` (Niagara / UMG / MVVM), `AssetTools` en écriture | hors périmètre | deux outils sur trois y sont `inconnu` ; un Niagara custom n'est pas ma voie |

## Toolsets MCP sous le CLI (pour comprendre, pas pour appeler en direct)

- **ValkyrieToolset.VerseToolset** — `ListFiles`, `Grep`, `ReadFile`, `WriteFile` (**DANGEREUX**),
  `BuildAll` : mes quatre premiers gestes de la chaîne Verse.
- **ValkyrieToolset.DeviceToolset** — `GetBindingOptions`, `AddEventBinding`, `ListEventBindings`,
  `ListDeviceProperties` / `SetDeviceProperty` (statut inconnu hors `--apply`) : la preuve d'un lien
  se lit sur la **cible**.
- **editor_toolset.toolsets.object.ObjectTools** (6 outils, tous `verifie`) — `list_properties`,
  `get_properties`, `set_properties`, `reset_properties`, `get_class`, `search_subclasses` : le seul
  chemin d'accès aux propriétés d'un acteur ou d'un device Verse.
- **ValkyrieToolset.SessionToolset** — `GetSessionStatus` (lecture) seulement ; `StartSession`,
  `StopSession`, `PushChanges`, `GetGameState`, `GetClientLogEntries` relèvent du Producteur.
- **EditorToolset.LogsToolset** — `GetLogEntries` / `GetLogCategories` : `VerseBuild` pour la
  compilation, `LogValkyrie` / `LogValkyrieValidation` pour la session.
- **SceneTools / ActorTools en lecture** — `find_actors`, `get_actor_transform` : uniquement pour
  **relier** un label et une transform avant de rejouer après un timeout.

**Règle transversale** : `inputSchema` **et** `outputSchema` sont validés **côté client** avant de
tenir un appel pour réussi (WP2 p.26/p.29) — les annotations du serveur (`destructiveHint`…) ne
sont que des indices, on ne s'appuie jamais dessus (WP2 p.27). Une sortie > 4000 tokens est
redirigée vers un fichier et je ne transmets que son chemin + un résumé de 200 caractères
(WP2 p.19/p.44). `isError`, sortie vide (`[]`, `null`, `false`) ou incohérente = **STOP** et statut
`UNKNOWN`, jamais « continuer comme si ça avait marché » (WP4 p.20). **Un seul appel MCP à la fois**,
jamais en parallèle, jamais pendant qu'un autre agent tient l'éditeur, et `verse-build` exige une
session **Disconnected** relue avant l'appel.
