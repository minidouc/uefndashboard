# Protocole de synchronisation — Agent PC (UEFN) ↔ Agent Git (Harnais)

Ce dossier est le **pont unique** entre :
- **l'Agent PC** (connecté à ton éditeur UEFN local sur Windows), qui prouve ce qui marche réellement ;
- **l'Agent Git / Harnais Rust** (`map-creator/`), qui développe et teste le système hors ligne.

## Règle de séparation stricte
- L'Agent PC n'écrit **QUE** dans `map-creator/compat/` (`COMPAT_STATUS.md`, `fixtures/*.json`, `mcp-inventory.latest.json`).
- Le Harnais Rust **lit** ce dossier en lecture seule (ou via l'action humaine `compat.ingest_fixture` dans le Dashboard) et ne devine jamais un format de retour MCP.

## Checklist de vérification pour l'Agent PC
À exécuter sur la version actuelle d'UEFN, dans l'ordre :
1. **Ping & Inventaire MCP** : capturer la liste des toolsets/outils dans `compat/mcp-inventory.latest.json`.
2. **Lecture de scène (`SceneTools.get_current_level`, `SceneTools.find_actors`)** : enregistrer la réponse brute complète dans `compat/fixtures/find_actors.json`.
3. **Pose d'une primitive (`PrimitiveTools.add_cube` ou `SceneTools.add_to_scene_from_class`)** : enregistrer la réponse brute dans `compat/fixtures/add_cube.json`, puis relire les bornes via `SceneTools.find_actors`.
4. **Pose d'un asset catalogue (`SceneTools.add_to_scene_from_asset`)** : tester sur 1 asset légal Fortnite/Sunburst, capturer `compat/fixtures/add_from_asset.json`.
5. **Persistance (`AssetTools.save_assets` + `AssetTools.is_dirty` + relecture `LevelBounds`)** : enregistrer dans `compat/fixtures/save_assets.json` et `compat/fixtures/is_dirty.json`.
6. **Compilation Verse (`VerseToolset.BuildAll`)** : capturer un build sain + un build avec 1 erreur dans `compat/fixtures/verse_build.json`.
7. **Import Meshy / Mesh 3D + poids mémoire** : importer 3 objets types, noter la mémoire mesurée et les limites de textures/LOD dans `COMPAT_STATUS.md`.
8. **Mettre à jour `compat/COMPAT_STATUS.md`** (1 ligne par capacité : `OK`, `FORMAT_CHANGED`, `BROKEN`, `UNTESTED`) puis pousser ou coller dans l'onglet **Preuves & Compatibilité** du Dashboard.
