# Les 388 outils MCP releves le 2026-10-19

Campagne : terminee apres reprise : crash de l'editeur UEFN le 2026-10-19 a 21:50:53 (heure locale) pendant NiagaraToolset_System.GetDynamicInputSchema (phase 2) ; editeur relance par l'utilisateur, MCP_TestLevel rouvert, pagination remise a 200 (run ....
Version : ++Fortnite+Release-42.40-CL-59247843 (UEFN AppVersion 6.0.0-59247843) | niveau de test : `MCP_TestLevel` | pagination : 200

Relancer la generation : `python script/build_tools_index.py --inventory DIR --capabilities FICHIER --out mcp_tools`.

| Famille | Fichier | Toolset | Alias | Outils | verifie | echec | inconnu |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `scene-acteur` | [scene-tools.md](scene-acteur/scene-tools.md) | `editor_toolset.toolsets.scene.SceneTools` | Scene | 28 | 17 | 1 | 10 |
| `scene-acteur` | [actor-tools.md](scene-acteur/actor-tools.md) | `editor_toolset.toolsets.actor.ActorTools` | Actor | 18 | 18 | 0 | 0 |
| `scene-acteur` | [entity-toolset.md](scene-acteur/entity-toolset.md) | `ValkyrieToolset.EntityToolset` | Entity | 13 | 12 | 1 | 0 |
| `scene-acteur` | [primitive-tools.md](scene-acteur/primitive-tools.md) | `editor_toolset.toolsets.primitive.PrimitiveTools` | Primitive | 4 | 4 | 0 | 0 |
| `objet-proprietes` | [object-tools.md](objet-proprietes/object-tools.md) | `editor_toolset.toolsets.object.ObjectTools` | Object | 6 | 6 | 0 | 0 |
| `objet-proprietes` | [verse-fields-toolset.md](objet-proprietes/verse-fields-toolset.md) | `VerseFieldsToolset.VerseFieldsToolset` | - | 7 | 0 | 0 | 7 |
| `devices` | [device-toolset.md](devices/device-toolset.md) | `ValkyrieToolset.DeviceToolset` | Device | 9 | 6 | 0 | 3 |
| `verse` | [verse-toolset.md](verse/verse-toolset.md) | `ValkyrieToolset.VerseToolset` | Verse | 10 | 4 | 0 | 6 |
| `editor-session` | [editor-app-toolset.md](editor-session/editor-app-toolset.md) | `EditorToolset.EditorAppToolset` | EditorApp | 37 | 29 | 2 | 6 |
| `editor-session` | [logs-toolset.md](editor-session/logs-toolset.md) | `EditorToolset.LogsToolset` | Logs | 4 | 4 | 0 | 0 |
| `editor-session` | [session-toolset.md](editor-session/session-toolset.md) | `ValkyrieToolset.SessionToolset` | Session | 8 | 2 | 1 | 5 |
| `editor-session` | [programmatic-toolset.md](editor-session/programmatic-toolset.md) | `editor_toolset.toolsets.programmatic.ProgrammaticToolset` | Prog | 2 | 2 | 0 | 0 |
| `editor-session` | [valkyrie-python-toolset.md](editor-session/valkyrie-python-toolset.md) | `ValkyrieToolset.ValkyriePythonToolset` | Python | 2 | 0 | 0 | 2 |
| `assets-ressources` | [asset-tools.md](assets-ressources/asset-tools.md) | `editor_toolset.toolsets.asset.AssetTools` | Asset | 17 | 8 | 0 | 9 |
| `assets-ressources` | [static-mesh-tools.md](assets-ressources/static-mesh-tools.md) | `editor_toolset.toolsets.static_mesh.StaticMeshTools` | SMesh | 16 | 3 | 4 | 9 |
| `assets-ressources` | [skeletal-mesh-tools.md](assets-ressources/skeletal-mesh-tools.md) | `editor_toolset.toolsets.skeletal_mesh.SkeletalMeshTools` | - | 22 | 12 | 0 | 10 |
| `assets-ressources` | [texture-tools.md](assets-ressources/texture-tools.md) | `editor_toolset.toolsets.texture.TextureTools` | - | 4 | 3 | 0 | 1 |
| `assets-ressources` | [material-tools.md](assets-ressources/material-tools.md) | `editor_toolset.toolsets.material.MaterialTools` | - | 25 | 9 | 1 | 15 |
| `assets-ressources` | [material-instance-tools.md](assets-ressources/material-instance-tools.md) | `editor_toolset.toolsets.material_instance.MaterialInstanceTools` | - | 14 | 3 | 0 | 11 |
| `assets-ressources` | [curve-table-tools.md](assets-ressources/curve-table-tools.md) | `editor_toolset.toolsets.curve_table.CurveTableTools` | - | 10 | 0 | 0 | 10 |
| `assets-ressources` | [data-table-tools.md](assets-ressources/data-table-tools.md) | `editor_toolset.toolsets.data_table.DataTableTools` | - | 11 | 0 | 0 | 11 |
| `assets-ressources` | [physics-asset-toolset.md](assets-ressources/physics-asset-toolset.md) | `PhysicsToolsets.PhysicsAssetToolset` | - | 17 | 2 | 0 | 15 |
| `effets-ui` | [niagara-toolset-system.md](effets-ui/niagara-toolset-system.md) | `NiagaraToolsets.NiagaraToolset_System` | - | 46 | 27 | 0 | 19 |
| `effets-ui` | [niagara-toolset-component.md](effets-ui/niagara-toolset-component.md) | `NiagaraToolsets.NiagaraToolset_Component` | - | 4 | 3 | 0 | 1 |
| `effets-ui` | [niagara-toolset-assets.md](effets-ui/niagara-toolset-assets.md) | `NiagaraToolsets.NiagaraToolset_Assets` | - | 3 | 1 | 1 | 1 |
| `effets-ui` | [niagara-toolset-info.md](effets-ui/niagara-toolset-info.md) | `NiagaraToolsets.NiagaraToolset_Info` | - | 1 | 1 | 0 | 0 |
| `effets-ui` | [umg-toolset.md](effets-ui/umg-toolset.md) | `UMGToolSet.UMGToolSet` | - | 21 | 2 | 0 | 19 |
| `effets-ui` | [widget-animation-toolset.md](effets-ui/widget-animation-toolset.md) | `WidgetAnimationToolset.WidgetAnimationToolset` | - | 10 | 0 | 0 | 10 |
| `effets-ui` | [mvvm-toolset.md](effets-ui/mvvm-toolset.md) | `MVVMToolset.MVVMToolset` | - | 15 | 1 | 0 | 14 |
| `effets-ui` | [gameplay-tags-toolset.md](effets-ui/gameplay-tags-toolset.md) | `GameplayTagsToolset.GameplayTagsToolset` | - | 4 | 3 | 0 | 1 |

Total : 388 outils dans 30 toolsets.
