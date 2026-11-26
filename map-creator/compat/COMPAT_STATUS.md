# Statut de compatibilité UEFN (Agent PC ↔ Harnais)

Version UEFN ciblée : **39.10** · Dernière synchronisation de référence : **2026-10-28 (à reprouver sur UEFN actuel par l'Agent PC)**

| Capacité / Outil MCP | Statut | Preuve / Fixture | Notes terrain |
| --- | --- | --- | --- |
| `SceneTools.get_current_level` | OK | `fixtures/get_current_level.json` | Lecture seule vérifiée |
| `SceneTools.find_actors` | OK | `fixtures/find_actors.json` | Renvoie `actorPath` et `bounds` (relecture groupée par lot) |
| `PrimitiveTools.add_cube` | OK | `fixtures/add_cube.json` | Portée X/Y <= 3900 uu, épaisseur min 256 uu |
| `SceneTools.add_to_scene_from_class` | OK | `fixtures/add_cube.json` | Prouvé lots 1–9 corpo-plaza |
| `SceneTools.add_to_scene_from_asset` | UNTESTED | `fixtures/add_from_asset.json` | À reprouver sur UEFN actuel (packs Fortnite / Sunburst) |
| `DeviceToolset.PlaceDevice` | OK | `fixtures/place_device.json` | Spawner, lights, billboard, skydome prouvés |
| `AssetTools.save_assets` | OK | `fixtures/save_assets.json` | Toujours suivi de `is_dirty` + relecture `LevelBounds` |
| `AssetTools.is_dirty` | OK | `fixtures/is_dirty.json` | Doit renvoyer `false` après save |
| `SceneTools.set_actor_folder` | BROKEN | `fixtures/set_actor_folder.json` | Rend `rc=0` sans effet (`folderPath="None"`) — rollback via `refPath` |
| `VerseToolset.BuildAll` | UNTESTED | `fixtures/verse_build.json` | Vérifier les diagnostics `Error` après MAJ UEFN |
| `StaticMeshTools.import_file` | UNTESTED | `fixtures/meshy_import.json` | Import Meshy confirmé manuellement, poids mémoire à mesurer |
| `Memory.island_budget_query` | UNTESTED | — | Mesure mémoire île par script à trouver sur UEFN actuel |
| `Landscape.terrain_tools` | BROKEN | — | Aucun outil terrain dans l'inventaire MCP (sans solution) |
