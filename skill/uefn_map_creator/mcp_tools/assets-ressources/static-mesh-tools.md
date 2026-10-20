# editor_toolset.toolsets.static_mesh.StaticMeshTools

Famille : `assets-ressources` | Alias CLI : `SMesh` | Outils : 16 (verifie 3, echec 4, inconnu 9, dont 8 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **import_file**(folder_path*,asset_name*,source_file*,import_materials,...) — Imports a mesh file from disk as a StaticMesh asset. [DANGEREUX | inconnu]
  - motif : Importe un asset dans le Content Browser
- **set_material**(mesh*,slot_name*,material*) — Assigns a material to a named slot on a static mesh asset. [DANGEREUX | inconnu]
  - motif : Modifie un asset StaticMesh
- **generate_lods**(mesh*,triangle_percents*) — Auto-generates LODs for a static mesh using triangle reduction. [DANGEREUX | inconnu]
  - motif : Modifie un asset StaticMesh
- **get_material**(mesh*,slot_name*) — Returns the material assigned to a named slot on a static mesh. [lecture | verifie]
- **set_lod_thresholds**(mesh*,thresholds*) — Sets the screen-size thresholds at which each LOD becomes active. [DANGEREUX | inconnu]
  - motif : Modifie un asset StaticMesh
- **set_nanite_enabled**(mesh*,enabled*) — Enables or disables Nanite for a static mesh. [DANGEREUX | inconnu]
  - motif : Modifie un asset StaticMesh
- **generate_convex_collisions**(mesh*,hull_count,max_hull_verts,hull_precision) — Generates convex hull collision shapes for a static mesh. [DANGEREUX | inconnu]
  - motif : Modifie un asset StaticMesh
- **get_bounds**(mesh*) — Returns the local-space bounding box of a static mesh. [lecture | verifie]
- **get_lod_count**(mesh*) — Returns the number of LODs in a static mesh asset. [lecture | echec]
  - erreur : renvoie 0 alors que AssetTools.get_asset_tags(Cube).LODs = "1"
- **get_lod_thresholds**(mesh*) — Returns the screen-size thresholds at which each LOD becomes active. [lecture | inconnu]
- **get_material_slots**(mesh*) — Returns the names of all material slots in a static mesh. [lecture | verifie]
- **get_triangle_count**(mesh*,lod_index) — Returns the number of triangles in a specific LOD of a static mesh. [lecture | echec]
  - erreur : LOD index 0 is out of range.
- **get_vertex_count**(mesh*,lod_index) — Returns the number of vertices in a specific LOD of a static mesh. [lecture | echec]
  - erreur : LOD index 0 is out of range.
- **is_nanite_enabled**(mesh*) — Returns whether Nanite is enabled for a static mesh. [lecture | echec]
  - erreur : renvoie false alors que AssetTools.get_asset_tags(Cube).NaniteEnabled = "True"
- **remove_collisions**(mesh*) — Removes all collision shapes from a static mesh. [DANGEREUX | inconnu]
  - motif : Modifie un asset StaticMesh
- **remove_lods**(mesh*) — Removes all auto-generated LODs from a static mesh, keeping only LOD 0. [DANGEREUX | inconnu]
  - motif : Modifie un asset StaticMesh
