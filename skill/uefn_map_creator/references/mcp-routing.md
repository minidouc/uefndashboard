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
python script/mcp_client.py call Device AddEventBinding @binding.json --log workspace_map/_mcp_calls.jsonl
```
Codes retour : `0` ok, `1` erreur outil (l'appel a ete traite, l'etat peut etre partiel), `2` editeur injoignable (rien execute), `3` timeout (etat inconnu).
Variables : `UEFN_MCP_URL`, `UEFN_MCP_TIMEOUT` (60 s par defaut), `UEFN_MCP_LOG` (journal JSONL).
Un appel direct n'est **pas journalise** sans `--log` ni `UEFN_MCP_LOG` : le CLI spatial, lui, ecrit toujours `<workspace>/_mcp_calls.jsonl`.

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
Un code 1 (`TOOL_ERROR`) sur une commande d'ecriture a la meme consequence : l'appel a ete traite, l'etat peut etre partiel. Seul le code 2 (`OFFLINE`) garantit que rien n'a ete execute.
1. **Ne pas relancer a l'aveugle.**
2. Relire : `find_actors` par label ou par tag, `get_actor_transform`, `GetSessionStatus`.
3. Relancer seulement ce qui manque. Les commandes du CLI le font : `place_actors` relit chaque label du lot et signale `BATCH_RECOVERED`.
4. Limite connue : un timeout pendant `PlaceDevice` peut laisser un device **sans label** (le label est pose par un appel suivant). Une relance cree alors un doublon. Apres un timeout de `place-scene`, chercher les devices sans le tag de la map avant de relancer.

## 7. Commandes du CLI (`script/uefn_spatial_cli.py`)

Toutes prennent `--workspace <chemin_absolu>` : le dossier d'etat de la carte, **hors du skill**
(refus `WORKSPACE_INSIDE_SKILL` sinon). `init` le cree depuis un gabarit (`templates/`).

| commande | editeur | role |
|---|---|---|
| `init --template blank\|1v1_arena\|boxfight [--force]` | non | cree le workspace et ses 5 specs ; `--list` liste les gabarits ; n'ecrase jamais un workspace rempli sans `--force` |
| `preflight` | oui | ping, pagination a 200, etat session |
| `measure-palette [--force] [--dry-run]` | oui | pose chaque asset a (0, -20000, 5000), relit bounds et pivot, supprime ; ecrit `02_palette.json` |
| `validate-grid [fichier]` | non | bordures fermees, escaliers, symetrie (`X`, `Y` ou `R180`), accessibilite 2D |
| `validate-scene` | non | forme des 5 specs (`spec_schema.py`) + coherence croisee ; `PALETTE_EMPTY` tant que rien n'est mesure |
| `build-structure [--dry-run]` | oui | sols et murs de perimetre par lots de 10, relecture des transforms |
| `compile-transforms` | non | calcule `_compiled_scene.json` (devices et props), echelle comprise |
| `place-scene [--dry-run]` | oui | devices (PlaceDevice puis transform forcee) et props (lots), relecture position/yaw/echelle |
| `audit-scene [--live]` | non / oui | chevauchements et gravite -> `06_audit_report.json` ; `--live` remplace la theorie par les bounds relus |
| `check-navigation` | non | couloirs < 100 cm entre props d'une meme tuile -> `06_navigation_report.json` (pas de capsule, pas de murs) |
| `check-symmetry [--live]` | non / oui | paires miroirs des specs (`SPEC_ASYMMETRY`, `MIRROR_PARTNER_MISSING`) -> `11_symmetry_report.json` ; `--live` ajoute le derive de placement (`TRANSFORM_DRIFT`) et la symetrie des bounds relus (`SCENE_ASYMMETRY`) |
| `apply-properties [--dry-run]` | oui | `list_properties` -> `set_properties` -> `get_properties` -> `07_properties_report.json` |
| `wire-devices [--dry-run]` | oui | `GetBindingOptions` -> `AddEventBinding` -> `ListEventBindings` (cible) -> `08_wiring_report.json` |
| `verse-scan [--root R] [--recursive]` | oui | `Verse.ListFiles` -> `_verse_files.json` (vide = inconnu, pas absent) |
| `verse-grep --pattern P \| --symbols A,B [--glob G]` | oui | `Verse.Grep` par symbole -> `_verse_grep.json` ; FAILED si un symbole manque |
| `verse-write --file F --path P [--i-agree-to-modify-project]` | oui | `WriteFile` puis `ReadFile` ; sans le flag : `CONSENT_REQUIRED`, rien n'est ecrit |
| `verse-build [--dry-run] [--log-entries N]` | oui | session `Disconnected` exigee, `BuildAll` + logs `VerseBuild` -> `09_verse_report.json` |
| `list-editables [--live --device LABEL]` | non / oui | table `@editable` -> `actor_label` -> `refPath` -> `10_editables.json` (cablage manuel) |
| `playtest-plan` | non | imprime la demande d'accord et la sequence de session ; **ne lance rien** |
| `visual-snapshot [--output]` | oui | camera au-dessus de la grille, pitch -90, PNG decode |
| `cleanup` | oui | **supprime tous les acteurs portant le tag de la map** (`UEFN_MAP_TAG`, defaut `UEFNMAP`) |

Chaque appel est journalise dans `<workspace>/_mcp_calls.jsonl`.
`--dry-run` renvoie `DRY_RUN`, jamais `PASSED`. Codes retour : `0` PASSED, `1` FAILED, `2` editeur injoignable, `3` timeout.
Statut `PASSED` = relu dans l'editeur (sauf commandes marquees « non », qui ne lisent que le disque).
Aucune commande ne sauvegarde le niveau, ne publie, ni ne lance de session.

Verification sans editeur : `python script/tests/verify.py` (faux serveur MCP
`script/tests/mock_mcp.py`, 127.0.0.1 uniquement) -> `110/110 OK`. Procedure complete :
`references/first-run.md`.

## 8. Interdits sans accord explicite de l'utilisateur

`Save` / `SaveAll`, `StartSession`, `PushChanges`, publication, `EnablePythonInUEFN`, tout outil qui modifie un asset du projet (`set_material`, `add_socket`, `set_nanite_enabled`, `import_file`, `create_level`, `load_level`, `create_data_layer_asset`...), `VerseToolset.WriteFile`.
`StartSession` a deja bloque le pont pendant un test anterieur.

## 9. Contournements du plafond MCP (ce qui marche, ce qui ne marche pas)

### Python ne donne aucune capacite nouvelle

`Prog.execute_tool_script` execute du Python **dans** l'editeur, mais le bac a sable n'expose que
`json`, `math`, `datetime`, `copy`, `re`, `time` et la fonction `execute_tool(nom, chaine_json)`.
Teste le 2026-10-19 : `import unreal` -> « Import of 'unreal' is not permitted » ;
`import toolset_registry` -> refuse aussi. **Python est un driver de boucle au-dessus des 388 memes
outils, pas une surface supplementaire.** Ne jamais presenter un script Python comme un contournement
du plafond (lumiere, materiaux par instance, feuillage, landscape).

### Ce que Python change vraiment : le debit et le calcul sur place

- 100 spawns + 100 tags en 3,7 s dans **un seul** appel, contre ~66 s en appels unitaires (§4).
  Le CLI reste a 10 par lot pour limiter la perte en cas de timeout ; hors CLI, le lot de 100 est prouve.
- `math` est disponible dans le script : les positions peuvent etre **calculees sur place**
  (repetition, grille, facade, skyline). C'est le substitut a l'absence de PCG et d'outil de duplication.
- `Primitive.add_cube` / `add_cone` / `add_cylinder` / `add_sphere` sont **[ecriture | verifie]** et
  n'ont **aucune commande du CLI** : ils ajoutent un composant a un acteur existant, donc une piece
 composee = 1 acteur au lieu de N. Jamais exerce par le skill : le composer reste a prouver.

### Lumiere : la seule voie est Niagara, et elle est a moitie prouvee

Aucun outil d'eclairage dans les 388 (recherche `LightToolset|add_light|Lightmass|set_light|LightComponent`
-> 0 resultat). Un systeme Niagara emissif (rendu sprite + couleur HDR) pose comme composant est
donc la seule source de lumiere atteignable.

| volet | outils | statut |
|---|---|---|
| poser | `NiagaraToolset_Component.SetSystem`, `SetVariable` | **[ecriture | verifie]** |
| lire | `GetEmitterTopology`, `GetModuleSchema`, `GetRendererSchema`, `GetAvailableDynamicInputs`, `GetSystemCompileState`, `GetStackIssues`, `GetSystemSummary` | **[lecture | verifie]** |
| creer | `CreateNiagaraSystem`, `AddEmitter`, `AddRenderer`, `SetRendererData`, `AddSetParametersModule`, `AddUserVariables`, `SetEmitterData`, `SetSystemData` | **[DANGEREUX | jamais appele]** |

Regles : un seul appel a la fois, `Save` avant le premier appel de chaque outil jamais teste, resultat
brut consigne. **`GetDynamicInputSchema` est interdit** (crashe l'editeur) : utiliser
`GetDynamicInputSchemaFromAsset`.

Seconde voie, complementaire : `MaterialInstanceTools.create` + `StaticMeshTools.set_material`.
Ces outils agissent au niveau de l'**asset** : tous les exemplaires du mesh changent ensemble.
Pour varier les apparences il faut plusieurs assets, pas plusieurs instances. Jamais testes.

### Derniere porte, non testee

`IsPythonEnabledInUEFN` renvoie deja `true`, donc l'interpreteur du projet est initialise, mais le bac
a sable MCP en est separe. Si le Python du projet est actif, la console Python de l'editeur a, elle, le
module `unreal` — hors d'atteinte du MCP : c'est de l'humain-dans-la-boucle (l'agent ecrit le script sur
le disque, l'utilisateur le colle dans l'editeur). `EnablePythonInUEFN` reste interdit sans accord (§8).
A traiter comme une hypothese, jamais comme un acquis.
