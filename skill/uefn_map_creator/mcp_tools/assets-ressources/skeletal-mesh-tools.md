# editor_toolset.toolsets.skeletal_mesh.SkeletalMeshTools

Famille : `assets-ressources` | Alias CLI : aucun | Outils : 22 (verifie 12, echec 0, inconnu 10, dont 7 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **add_socket**(mesh*,socket_name*,bone_name*) — Adds a named socket to a skeletal mesh attached to a bone. [DANGEREUX | inconnu]
  - motif : Modifie un asset SkeletalMesh
- **import_file**(folder_path*,asset_name*,source_file*,skeleton,...) — Imports a mesh file from disk as a SkeletalMesh asset. [DANGEREUX | inconnu]
  - motif : Importe un asset dans le Content Browser
- **rename_socket**(mesh*,old_name*,new_name*) — Renames a socket on a skeletal mesh. [DANGEREUX | inconnu]
  - motif : Modifie un asset SkeletalMesh
- **set_material**(mesh*,slot_name*,material*) — Assigns a material to a named slot on a skeletal mesh asset. [DANGEREUX | inconnu]
  - motif : Modifie un asset SkeletalMesh
- **set_socket_transform**(mesh*,socket_name*,transform*) — Sets the local transform of a socket relative to its parent bone. [DANGEREUX | inconnu]
  - motif : Modifie un asset SkeletalMesh
- **assign_physics_asset**(mesh*,physics_asset*) — Assigns a physics asset to a skeletal mesh. [DANGEREUX | inconnu]
  - motif : Modifie un asset SkeletalMesh
- **get_bone_children**(mesh*,bone_name*) — Returns the direct children of a bone. [lecture | verifie]
- **get_bone_parent**(mesh*,bone_name*) — Returns the name of a bone's parent, or an empty string for the root bone. [lecture | verifie]
- **get_material**(mesh*,slot_name*) — Returns the material assigned to a named slot on a skeletal mesh. [lecture | verifie]
- **get_socket_bone**(mesh*,socket_name*) — Returns the name of the bone that a socket is attached to. [lecture | verifie]
- **get_socket_transform**(mesh*,socket_name*) — Returns the local transform of a socket relative to its parent bone. [lecture | inconnu]
- **remove_socket**(mesh*,socket_name*) — Removes a named socket from a skeletal mesh. [DANGEREUX | inconnu]
  - motif : Modifie un asset SkeletalMesh
- **get_bone_names**(mesh*) — Returns the names of all bones in a skeletal mesh in hierarchy order. [lecture | verifie]
- **get_bounds**(mesh*) — Returns the local-space bounding volume of a skeletal mesh. [lecture | inconnu]
- **get_lod_count**(mesh*) — Returns the number of LODs in a skeletal mesh asset. [lecture | verifie]
- **get_material_slots**(mesh*) — Returns the names of all material slots in a skeletal mesh. [lecture | verifie]
- **get_morph_target_names**(mesh*) — Returns the names of all morph targets on a skeletal mesh. [lecture | verifie]
- **get_physics_asset**(mesh*) — Returns the physics asset assigned to a skeletal mesh. [lecture | verifie]
- **get_section_count**(mesh*,lod_index) — Returns the number of sections in a specific LOD of a skeletal mesh. [lecture | inconnu]
- **get_skeleton**(mesh*) — Returns the skeleton asset associated with a skeletal mesh. [lecture | verifie]
- **get_socket_names**(mesh*) — Returns the names of all sockets on a skeletal mesh. [lecture | verifie]
- **get_vertex_count**(mesh*,lod_index) — Returns the number of vertices in a specific LOD of a skeletal mesh. [lecture | verifie]
