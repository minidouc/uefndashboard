# Engine_Programmer — outils (allowlist)

> **Tool Definitions** (WP3 p.8) + borne de sécurité (WP2 p.47 *least privilege*,
> `util/multi_agent/05-securite-mcp.md`).
> Point d'entrée unique : `python script/uefn_spatial_cli.py <commande> --workspace <absolu>`
> (et, pour les appels d'état bruts, le pont MCP sur le port **relu**).
> Une commande absente de cette page = **appel refusé**, pas « à tenter quand même ».
> Codes retour : `0` PASSED · `1` FAILED (**traité** : relire avant de rejouer) · `2` OFFLINE
> (rien d'exécuté) · `3` TIMEOUT (état inconnu : relire, jamais relancer à l'aveugle).

## Autorisé — lecture et validation (aucun effet de bord)

| Commande / outil | Quand / pourquoi | Paramètres clés | Sortie à savoir lire |
|---|---|---|---|
| `ping` découverte de pont | tout début de préflight : savoir **quel port répond** | `UEFN_MCP_URL`, ports 8000 puis 8001 | message `OFFLINE` + code 2 si injoignable |
| `list_toolsets` | inventorier les toolsets exposés | — | `Output too large` (>4000 tokens) → garder le **chemin du fichier** |
| `ValkyrieToolset.SessionToolset.GetSessionStatus` | état de session de l'éditeur | `{}` | `returnValue` : `Disconnected` / `Connected` / `Reconnecting` |
| `ValkyrieToolset.SessionToolset.StartSession` | **uniquement** sur accord du Producer, jamais en boucle | — | timeout → `TIMEOUT_OUTCOME_UNKNOWN`, code 3 |
| `Scene.get_current_level` | prouver le **nom interne** du niveau chargé | `{}` | `"/<guide>/<niveau>"` (ex. `claudtest`) |
| `ProgrammaticToolset.GetCVarValue` | lire la pagination et tout CVar d'environnement | `{"name": "ModelContextProtocol.PaginationPageSize"}` | chaîne (`"0"`, `"200"`) — jamais un nombre |
| `EditorAppToolset` (état / capture) | vérifier que l'éditeur est vivant et sans modale bloquante | workspace | image/PNG + état relu, sortie volumineuse → fichier |
| lecture processus + RAM (OS) | relever le process éditeur et l'usage mémoire **à l'instant T** | — | `Total_MB`, `Free_MB`, working set du process |
| `python script/tests/verify.py` | valider les **contrats** du harnais hors éditeur | — | `122/122 OK` (attendu) |
| `ListFiles` | vérifier l'arborescence du workspace et l'accès en lecture | dossier | liste de fichiers, présence de `Content/`, `Scripts/`, sortie |

## Autorisé — écriture (gate HITL, save préalable, **périmètre étroit**)

| Commande / outil | Quand / pourquoi | Paramètres clés | Effet de bord | Relecture obligatoire |
|---|---|---|---|---|
| `ProgrammaticToolset.SetCVarValue` | forcer la pagination à `200` (valeur `0` = troncation silencieuse) | `{"name": "...PaginationPageSize", "value": "200"}` | modifie la session éditeur en cours | **`GetCVarValue` immédiat** ; l'outil renvoie `returnValue: null`, ce n'est pas une preuve |
| `cleanup` (`ActorTools.remove_from_scene`) | **seulement sur demande explicite du Producteur**, jamais de mon initiative | `{"actor": {"refPath": "..."}}`, save préalable | **destructif** : retire des acteurs | `returnValue: true` puis relecture (`find_actors` / `get_actor_bounds`) + inventaire des `refPath` retirés |
| écriture de mes artefacts | `preflight_ok.json`, `mcp-inventory.json`, `tech/env-status.md` | chemin absolu du workspace | crée/ecrit un fichier de **sortie**, jamais de contenu de scène | relecture du fichier écrit + validation JSON par le validateur du pipeline |

## Interdit pour ce rôle

| Outil / commande | Propriétaire réel | Pourquoi |
|---|---|---|
| `place-scene`, `build-structure` | `Level_Designer` (via le CLI de pose) | je ne pose aucun acteur : je déclare si la machine et le pont tiennent |
| `measure-palette` | `Lead_Programmer` | les mesures de bounds ne sont pas mon livrable |
| `verse-*` (`verse-scan`, `verse-write`, `verse-build`), `list-editables`, `wire-devices` | 12 / 13 / 14 (`Gameplay_Programmer`, `AI_Programmer`, `UI_Programmer`) | aucun Verse, aucun câblage de device |
| `apply-properties` | `Graphics_Programmer` (ambiance) / 12 (gameplay) | je ne règle pas les devices |
| `compile-transforms`, `validate-grid`, `audit-scene --live` | `Physics_Programmer`, `Level_Designer` | hors périmètre de préflight |
| `Asset.find_assets` dans `/Game/Athena`, `/Game/Environments` | — | assets Epic non exposés → échec de validation d'île |
| `GetDynamicInputSchema` hors session | — | **crash connu de l'éditeur** ; les schémas se lisent dans la doc de skill |
| `launch-session`, `Save`/`SaveAll`, `Publish`, redémarrage de l'éditeur | `Producer_Orchestrator` via gate HITL utilisateur | destructeur / publication / perte de contexte |
| `batch.exec`, `editor.undo`, `validate_folder` | — | **n'existent pas** : mentions caduques |
| tout outil classé `DANGEREUX_UNTESTE` (138 dans l'inventaire de référence) | — | jamais appelé, donc non.allowlisté |

## Toolsets MCP sous le CLI (pour comprendre, pas pour appeler en direct)

- **ValkyrieToolset.SessionToolset** — vie de la session (`GetSessionStatus`, `StartSession`, `EndSession`).
- **ProgrammaticToolset** — CVar d'environnement (`GetCVarValue`, `SetCVarValue`) et `get_execution_environment`.
- **EditorAppToolset** — état de l'application, caméra et capture (`SetCameraTransform`, `CaptureViewport`).
- **SceneTools / ActorTools** — lecture d'état de la scène (`get_current_level`, `find_actors`,
  `get_actor_bounds`) ; `remove_from_scene` n'est utilisé que sur demande explicite.
- **Logs** — `GetLogEntries` / `GetLogCategories` : attention, la catégorie demandée peut ne pas
  exister (`Log category 'Valkyrie' not found.`), ce qui est une erreur d'appel, pas un état de l'éditeur.

**Règle transversale** : `inputSchema` **et** `outputSchema` sont validés côté client avant de tenir
un appel pour réussi (WP2 p.26/p.29). Une sortie > 4000 tokens est redirigée vers un fichier et je ne
transmets que son chemin (WP2 p.19/p.44). `isError`, sortie vide ou incohérente = **STOP** et statut
`UNKNOWN`, jamais « continuer comme si ça avait marché » (WP4 p.20). Un seul appel MCP à la fois :
l'éditeur et le pont partagent le même processus, la concurrence est la cause des timeouts 10054.
