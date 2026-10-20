# Routage MCP UEFN : outils prouves, signatures, pieges

Source : campagne de tests du 2026-10-19 (`mcp_tests/RAPPORT_MCP.md`, 388 outils, 182 proven, 11 failed, 195 unknown).
Statuts : **proven** = ecrit puis relu par un autre outil ; **unknown** = non teste ou non recoupe ; **failed** = faux ou en erreur.
Ne jamais presenter un outil unknown comme fiable.
Inventaire complet range par type : `mcp_tools/` (388 outils, un fichier par toolset). Ce fichier-ci
ne garde que la routage utile au constructeur de carte.

## 1. Transport

- Un seul serveur : MCP officiel UEFN, `http://127.0.0.1:8000/mcp`, sans authentification. Ne jamais l'exposer hors de la machine.
- Il n'y a **pas** de Bridge Python `:9210`, pas de `batch.exec`, pas d'`editor.undo`, pas de `validate_folder` / `validate_selected`, pas de `.t3d`. Aucun equivalent prouve.
- Pas de module `unreal` : dans `execute_tool_script`, `import unreal` est refuse. Modules permis : `json`, `math`, `datetime`, `copy`, `re`, `time`.
- Pas de PCG, pas de duplication d'**acteur** (`AssetTools.duplicate` ne duplique qu'un dossier ou un asset, et reste inconnu : jamais appele), pas de diff de niveau (`SceneTools.diff` failed).
- **Un seul appel a la fois**, jamais en parallele, jamais deux agents sur l'editeur : tout s'execute sur le game thread.
- Protocole : `initialize` -> en-tete `Mcp-Session-Id` -> `notifications/initialized` -> `tools/call` avec
  `{"name": "call_tool", "arguments": {"toolset_name": ..., "tool_name": ..., "arguments": {...}}}`. Reponse JSON ou SSE.
- Client fourni : `script/mcp_client.py` (gere session, SSE, timeouts, journal). Ne pas recoder le protocole.

```bash
python script/mcp_client.py ping
python script/mcp_client.py call Scene find_actors '{"name": "Spawner", "collision_channels": []}'
python script/mcp_client.py call Object list_properties @args.json --max 8000
```
Codes retour : `0` ok, `1` erreur outil, `2` editeur injoignable (rien execute), `3` timeout (etat inconnu).
Variables : `UEFN_MCP_URL`, `UEFN_MCP_TIMEOUT` (60 s par defaut).

## 2. Alias de toolsets (mcp_client.py)

| alias | toolset complet |
|---|---|
| EditorApp | `EditorToolset.EditorAppToolset` |
| Logs | `EditorToolset.LogsToolset` |
| Verse | `ValkyrieToolset.VerseToolset` |
| Session | `ValkyrieToolset.SessionToolset` |
| Device | `ValkyrieToolset.DeviceToolset` |
| Entity | `ValkyrieToolset.EntityToolset` |
| Actor | `editor_toolset.toolsets.actor.ActorTools` |
| Asset | `editor_toolset.toolsets.asset.AssetTools` |
| Object | `editor_toolset.toolsets.object.ObjectTools` |
| Scene | `editor_toolset.toolsets.scene.SceneTools` |
| Prog | `editor_toolset.toolsets.programmatic.ProgrammaticToolset` |
| SMesh | `editor_toolset.toolsets.static_mesh.StaticMeshTools` |

Un acteur se passe toujours en `{"refPath": "<chemin complet>"}`. Une transform : `{"location": {x,y,z}, "rotation": {pitch,yaw,roll}, "scale": {x,y,z}}`.

## 3. Matrice d'aiguillage (outils et signatures verifiees)

| besoin | outil (statut) | arguments exacts | note |
|---|---|---|---|
| niveau courant | `Scene.get_current_level` (proven) | `{}` | sert de ping |
| pagination | `EditorApp.GetCVarValue` / `SetCVarValue` (proven) | `{"name": "ModelContextProtocol.PaginationPageSize"}` / `+ "value": "200"` | vaut `0` au demarrage : la mettre a 200 avant toute liste |
| chercher un asset | `Asset.find_assets` (proven) | `{"folder_path", "name", "asset_type", "recursive", "tags"}` | dossier inexistant -> `[]` sans erreur |
| chercher un device | `Device.ListDeviceAssets` (proven) | `{"nameFilter": "Button"}` | renvoie `{displayName, assetPath, category, bIsVerseDevice}` |
| poser un acteur | `Scene.add_to_scene_from_asset` (proven) | `{"asset_path", "name", "xform", "parent", "snap_to_ground"}` | `name` devient le label |
| poser un device | `Device.PlaceDevice` (proven) | `{"assetPath": {"refPath"}, "transform"}` | yaw ignore (0 demande, 90 relu) : forcer la transform apres |
| transform | `Actor.set_actor_transform` / `get_actor_transform` (proven) | `{"actor", "xform", "worldspace": true}` | relu a 0,1 pres |
| label, tag | `Actor.set_label` / `add_tag` (proven) | `{"actor", "label"}` / `{"actor", "tag"}` | |
| mesurer | `Actor.get_actor_bounds` (proven) | `{"actor"}` | renvoie `{min, max, isValid}` |
| raycast | `Scene.trace_world` (proven) | `{"start", "end"}` | rien touche -> `null` sans erreur |
| retrouver | `Scene.find_actors` (proven) | `{"name"?, "tag"?, "collision_channels": []}` | `collision_channels` obligatoire ; `folderPath` vaut toujours `"None"` |
| supprimer | `Scene.remove_from_scene` (proven) | `{"actor"}` | marche aussi sur un EntityProxyActor |
| lot | `Prog.execute_tool_script` (proven) | `{"script": "..."}` | renvoie une chaine JSON |
| proprietes | `Object.list_properties` / `get_properties` / `set_properties` (proven) | `{"instance"}` / `+ "properties": [..]` / `+ "values": "<chaine JSON>"` | `values` est une **chaine**, pas un objet |
| cablage | `Device.GetBindingOptions` / `AddEventBinding` / `ListEventBindings` / `RemoveEventBinding` (proven) | voir `devices-catalog-and-wiring.md` | |
| camera | `EditorApp.SetCameraTransform` / `GetCameraTransform` (proven) | `{"transform"}` / `{}` | teste a pitch -30 ; pitch -90 non teste |
| capture | `EditorApp.CaptureViewport` (proven) | `{}` | PNG en ligne dans `content[]` de type image, aucun fichier ecrit |
| logs editeur | `Logs.GetLogEntries` (proven) | `{"category", "pattern", "maxEntries"}` | categorie inconnue -> erreur |
| compiler Verse | `Verse.BuildAll` (proven, session Disconnected) | `{}` | renvoie la liste des diagnostics |
| etat session | `Session.GetSessionStatus` (proven) | `{}` | `Disconnected`, `Connecting`, `Reconnecting`, `Connected`, `UpdatingContent` |

**Prouves mais non branches dans le CLI** (relus le 2026-10-19, utiles au constructeur) :
- `Scene.trace_world(start*, end*)` -> distance jusqu'au premier impact (relu : 9606,05 cm, impact au
  sommet des bounds d'un acteur identifie). Candidat pour controler les degagements que
  `check-navigation` ne couvre pas.
- `Scene.replace_actors_with_asset(actors*, asset_path*, copy_source_properties)` -> remplace des
  acteurs en place, label et tags conserves (relu : `StaticMesh` null -> `/Engine/BasicShapes/Sphere`,
  tags `["MCPTEST"]` gardes, `find_actors` = 1).
- `Scene.set_actor_folder(actor*, folder_path*)` -> range l'acteur dans un dossier de l'outliner (relu
  par `get_folders` et `get_actors_in_folder`). Peut completer le tag de menage.
- `Scene.set_actor_hidden(actor*, hidden*)` -> visible ou masque (relu dans les deux sens). Ne remplace
  pas une suppression.
Avant d'en brancher un : le retester dans `MCP_TestLevel` avec des acteurs `MCPTEST_*`.

Outils a ne pas utiliser :
- `StaticMeshTools.get_lod_count`, `get_vertex_count`, `get_triangle_count`, `is_nanite_enabled` : **failed** sur contenu cuit. Lire `Asset.get_asset_tags` (LODs, NaniteEnabled) a la place.
- `EntityToolset.DeleteEntity` : **failed** (« Cannot delete the root entity »). Utiliser `Scene.remove_from_scene` sur l'EntityProxyActor.
- `NiagaraToolset_System.GetDynamicInputSchema` : **crashe l'editeur** sur une entree non dynamique.
- Listes d'`AssetData` (ex. `get_referencing_materials`) : objets vides `{}`, inexploitables.

## 4. Lots avec execute_tool_script

Seul moyen prouve de faire un lot : aucun outil de spawn n'accepte plusieurs acteurs.
Mesures : 10 spawns + 10 tags = 1,3 s ; 100 spawns + 100 tags = 3,7 s, contre ~66 s en appels unitaires.
Lots prouves : 10 et 100. Le CLI utilise des lots de 10 pour limiter la perte en cas de timeout.

Patron (le script doit definir `run()` ; `execute_tool(nom_complet, chaine_json)` renvoie `{"returnValue": ...}` et leve une exception en cas d'erreur) :

```python
import json
SPECS = json.loads('[{"asset": "/Game/X.X", "label": "Floor_0_0_0", "xform": {...}, "tag": "UEFNMAP"}]')
def run():
    placed, errors = [], []
    for s in SPECS:
        try:
            a = execute_tool('editor_toolset.toolsets.scene.SceneTools.add_to_scene_from_asset',
                             json.dumps({'asset_path': s['asset'], 'name': s['label'],
                                         'xform': s['xform'], 'snap_to_ground': False}))['returnValue']
            execute_tool('editor_toolset.toolsets.actor.ActorTools.add_tag',
                         json.dumps({'actor': {'refPath': a['refPath']}, 'tag': s['tag']}))
            placed.append([s['label'], a['refPath']])
        except Exception as e:
            errors.append([s['label'], str(e)])
    return {'placed': placed, 'errors': errors}
```

Regles :
- Un `try/except` par element : un echec ne doit pas perdre le reste du lot. Il n'y a **pas** d'annulation de transaction : ce qui est cree reste cree.
- Persister les `refPath` apres chaque lot (le CLI ecrit `_placed.json`) : c'est ce qui rend la relance idempotente.
- Relire chaque transform hors du script (`get_actor_transform`) : le retour du script ne prouve pas la position.

## 5. Discipline de lecture

- **Relire apres chaque ecriture**, par un autre outil. Une erreur ne prouve pas l'absence d'effet : `set_properties` a deja renvoye une erreur en appliquant une partie des valeurs.
- **Reponse vide = inconnu, pas absent.** 14 appels invalides ont renvoye `[]`, `null`, `false` ou `{}` sans erreur (`find_assets` sur un dossier inexistant, `exists("pas un chemin")`, `ListDeviceAssets`, `trace_world`, `CaptureViewport` avec arguments faux...).
- `find_actors` : filtrer ensuite sur l'egalite exacte du label (la recherche par nom est une sous-chaine).
- Le pivot d'un Cube moteur est le centre de sa boite ; pour tout autre asset, **mesurer** (`measure-palette`), ne jamais supposer.

## 6. Timeout et etat inconnu

Si un appel expire (code 3, `TIMEOUT_OUTCOME_UNKNOWN`), l'action a peut-etre eu lieu.
1. **Ne pas relancer a l'aveugle.**
2. Relire : `find_actors` par label ou par tag, `get_actor_transform`, `GetSessionStatus`.
3. Relancer seulement ce qui manque. Les commandes du CLI le font : `place_actors` relit chaque label du lot et signale `BATCH_RECOVERED`.
4. Limite connue : un timeout pendant `PlaceDevice` peut laisser un device **sans label** (le label est pose par un appel suivant). Une relance cree alors un doublon. Apres un timeout de `place-scene`, chercher les devices sans le tag de la map avant de relancer.

## 7. Commandes du CLI (`script/uefn_spatial_cli.py`)

| commande | editeur | role |
|---|---|---|
| `preflight` | oui | ping, pagination a 200, etat session |
| `measure-palette [--force] [--dry-run]` | oui | pose chaque asset a (0, -20000, 5000), relit bounds et pivot, supprime ; ecrit `02_palette.json` |
| `validate-grid [fichier]` | non | bordures fermees, escaliers, symetrie, accessibilite 2D |
| `build-structure [--dry-run]` | oui | sols et murs de perimetre par lots de 10, relecture des transforms |
| `compile-transforms` | non | calcule `_compiled_scene.json` (devices et props) |
| `place-scene [--dry-run]` | oui | devices (PlaceDevice puis transform forcee) et props (lots) |
| `audit-scene [--live]` | non / oui | chevauchements et gravite ; `--live` remplace la theorie par les bounds relus |
| `check-navigation` | non | couloirs < 100 cm entre props d'une meme tuile (pas de capsule, pas de murs) |
| `visual-snapshot [--output]` | oui | camera au-dessus de la grille, pitch -90, PNG decode |
| `cleanup` | oui | **supprime tous les acteurs portant le tag de la map** (`UEFN_MAP_TAG`, defaut `UEFNMAP`) |

Toutes prennent `--workspace` (defaut `workspace_map`). Chaque appel est journalise dans `<workspace>/_mcp_calls.jsonl`.
`--dry-run` renvoie `DRY_RUN`, jamais `PASSED`. Codes retour : `0` PASSED, `1` FAILED, `2` editeur injoignable, `3` timeout.
Statut `PASSED` = relu dans l'editeur. Aucune commande ne sauvegarde le niveau.

## 8. Interdits sans accord explicite de l'utilisateur

`Save` / `SaveAll`, `StartSession`, `PushChanges`, publication, `EnablePythonInUEFN`, tout outil qui modifie un asset du projet (`set_material`, `add_socket`, `set_nanite_enabled`, `import_file`, `create_level`, `load_level`, `create_data_layer_asset`...), `VerseToolset.WriteFile`.
`StartSession` a deja bloque le pont pendant un test anterieur.
