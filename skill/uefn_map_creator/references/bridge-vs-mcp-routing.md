# Routage Hybride UEFN : Python Bridge (`:9210`) vs UEFN MCP (`:8000`)

## 1. Architecture de Transport

- **Point d'entree principal** : Serveur HTTP Python Bridge local sur `http://127.0.0.1:9210`.
- **Serveur secondaire** : Serveur officiel UEFN MCP sur `http://127.0.0.1:8000/mcp` (ou appel direct en memoire via `unreal.ToolsetRegistry` depuis le Bridge).
- **Regle d'or** : Executer 85% des operations via le Bridge Python (`route: "python"`) et 15% via les Toolsets MCP (`route: "toolset_registry"` ou `route: "mcp"`).

## 2. Matrice d'Aiguillage des Commandes

| Domaine d'Action | Route Obligatoire | Commande / Toolset Exact | Justification Technique |
| :--- | :--- | :--- | :--- |
| Recherche dans le Content Browser | `python` (Bridge) | `assets.search` / `unreal.EditorAssetLibrary` | Evite de charger des milliers de chemins dans le contexte MCP. |
| Mesure 3D des Boites Englobantes | `python` (Bridge) | `actor.get_actor_bounds()` en spawn temporaire | Non expose avec precision par le MCP standard. |
| Construction Structurelle (Murs, Sols, Toits) | `python` (Bridge) | `batch.exec` (`actors.spawn` + `ScopedEditorTransaction`) | Place 500 acteurs en 1 seul tick Slate et 1 seul bloc `Ctrl+Z`. |
| Placement et Calcul des Decors (Props) | `python` (Bridge) | `batch.exec` via `uefn_spatial_cli.py compile-transforms` | Applique la formule de boite englobante et le raycast au sol. |
| Controle Camera et Capture 2D | `python` (Bridge) | `viewport.set_camera` (`Pitch=-90`) + `screenshot_viewport` | Indispensable pour l'audit visuel orthographique quadrille. |
| Audit de Collision, Gravite et Navigation | `python` (Bridge) | `uefn_spatial_cli.py audit-scene` et `check-navigation` | Calculs vectoriels intensifs impossibles via JSON-RPC unitaire. |
| Validation Pre-Publication des Assets | `python` (Bridge) | `validate_folder` / `validate_selected` | Verifie les LODs et la liste blanche de proprietes UEFN. |
| Lecture, Ecriture et Compilation Verse | `toolset_registry` / `mcp` | `ValkyrieToolset.VerseToolset` (*Build Verse Code*) | L'API Python `unreal.*` pure ne peut pas compiler le code Verse. |
| Catalogue et Placement des Devices Creatif | `toolset_registry` / `mcp` | `ValkyrieToolset.DeviceToolset` | Gere nativement les appareils Creatif V2 du catalogue Fortnite. |
| Cablage des Tableaux `@editable` Complexes | `python` (Bridge `.t3d`) + `mcp` | `DeviceToolset` ou `verse.export_t3d` / `verse.set_property` | Contourne l'echec de `set_editor_property` sur les sous-objets Verse. |
| Lancement Session Play-in-Client (PIC) | `toolset_registry` / `mcp` | `ValkyrieToolset.SessionToolset` | Seul moyen d'executer *Launch Session* et *Push Verse Changes*. |
| Lecture des Logs d'Execution Client | `toolset_registry` / `mcp` | `ValkyrieToolset.SessionToolset` (*Check Client Log*) | Recupere les sorties `Print("[ASSERT_OK]")` du client Fortnite. |

## 3. Regle d'Execution Atomique (`batch.exec`)

Lors de l'envoi d'une construction au Bridge Python, toujours regrouper les creations dans une seule charge utile `batch.exec` :

```json
{
  "command": "batch.exec",
  "transaction_name": "Build_Arena_Zone_A",
  "stop_on_error": true,
  "operations": [
    {"op": "actors.spawn", "asset": "/Game/...", "label": "Floor_0_0", "location": [256.0, 256.0, 0.0], "rotation": [0.0, 0.0, 0.0]},
    {"op": "actors.spawn", "asset": "/Game/...", "label": "Wall_N_0_0", "location": [512.0, 256.0, 0.0], "rotation": [0.0, 0.0, 180.0]}
  ]
}
```

En cas d'echec d'une seule operation du lot, envoyer immediatement `{"command": "editor.undo"}` au Bridge pour annuler toute la transaction proprement.

## 4. Protocole de Securite sur Timeout et `outcome_unknown`

Les operations UEFN lourdes (compilation Verse volumineuse, cuisson des assets, lancement de la session Play-in-Client) peuvent prendre entre 30 et 300 secondes.

Si le Bridge ou le serveur MCP retourne :
```json
{
  "status": "ERROR",
  "error_code": "TIMEOUT",
  "outcome_unknown": true
}
```

**Procedure obligatoire :**
1. **INTERDICTION** de relancer la meme commande de creation ou de lancement de session immediatement.
2. Si l'operation concernait des acteurs : appeler `actors.list` dans le Bridge pour verifier si les `actor_label` ont deja ete crees dans le niveau.
3. Si l'operation concernait la session Fortnite : appeler `GetSessionStatus` dans `ValkyrieToolset.SessionToolset` toutes les 10 secondes jusqu'a ce que l'etat se stabilise (`Connected`, `InGame` ou `Idle`).
4. Ne reprendre le workflow qu'une fois l'etat reel confirme.