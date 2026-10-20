# editor_toolset.toolsets.scene.SceneTools

Famille : `scene-acteur` | Alias CLI : `Scene` | Outils : 28 (verifie 17, echec 1, inconnu 10, dont 4 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **add_to_scene_from_asset**(asset_path*,name*,xform*,parent,...) — Creates a new actor in the scene from an asset. [ecriture | verifie]
- **add_to_scene_from_class**(actor_type*,name*,xform*,parent,...) — Creates a new instance of the specified object at the specified transform. [ecriture | verifie]
- **add_actors_to_data_layer**(actors*,asset_path*) — Adds actors to a data layer, creating its instance in the current world if it has none yet. [ecriture | inconnu]
- **diff**(old_scene_path*,new_scene_path*) — Returns a unified text diff between two scene asset packages. [lecture | echec]
  - erreur : SceneTools.diff: level (World) diff is not yet supported: /d2c00ace-96a8-49df-b878-4900ea8ef303/MCP_TestLevel
- **remove_actors_from_data_layer**(actors*,asset_path*) — Removes actors from a data layer. [ecriture | inconnu]
- **rename_folder**(old_path*,new_path*) — Renames a folder in the outliner. [ecriture | verifie]
- **replace_actors_with_asset**(actors*,asset_path*,copy_source_properties) — Replaces actors in the scene with new actors created from an asset (e.g. [ecriture | verifie]
- **replace_actors_with_class**(actors*,actor_type*) — Replaces actors in the scene with new instances of a native Actor class, matching the editor's "Replace Selected Actors With..." command. [ecriture | verifie]
- **set_actor_folder**(actor*,folder_path*) — Assigns an actor to the specified folder in the outliner. [ecriture | verifie]
- **set_actor_hidden**(actor*,hidden*) — Shows or hides the actor in the editor viewport and outliner. [ecriture | verifie]
- **trace_world**(start*,end*) — Traces a line through the world and returns the distance to the first hit. [lecture | verifie]
- **create_data_layer_asset**(asset_path*,is_runtime) — Creates a new Data Layer asset in the content browser. [DANGEREUX | inconnu]
  - motif : Cree un asset dans le Content Browser
- **create_level**(level_path*,world_partition) — Creates a new empty level asset and opens it in the editor. [DANGEREUX | inconnu]
  - motif : Cree un asset niveau et change de niveau (risque de boite modale de sauvegarde)
- **delete_folder**(folder_path*) — Deletes a folder from the outliner. [ecriture | verifie]
- **find_actors**(root,name,actor_type,tag,...) — Searches the scene for actors that match specific criteria. [lecture | verifie]
- **get_actor_asset_path**(actor*) — Returns the content path that identifies this actor on disk. [lecture | verifie]
- **get_actors_in_data_layer**(asset_path*) — Returns descriptors for the loaded actors assigned to a data layer. [lecture | inconnu]
- **get_actors_in_folder**(folder_path*,recursive) — Returns descriptors for the actors in the specified outliner folder. [lecture | verifie]
- **is_actor_hidden**(actor*) — Returns whether the actor is hidden in the editor viewport and outliner. [lecture | verifie]
- **load_actors**(actors*) — Loads the actors described by the given descriptors into the editor and returns them. [ecriture | inconnu]
  - motif : non execute : les seuls acteurs modifiables (MCPTEST_*) ne sont jamais sauvegardes (Save interdit) ; decharger un ...
- **load_level**(level_path*) — Loads a level in the editor. [DANGEREUX | inconnu]
  - motif : Change de niveau (risque de boite modale de sauvegarde)
- **remove_from_scene**(actor*) — Deletes an actor from the scene. [ecriture | verifie]
- **save_actor**(actor*) — Saves the actor to disk. [DANGEREUX | inconnu]
  - motif : Sauvegarde sur disque : interdit (regle 4)
- **unload_actors**(actors*) — Unloads previously loaded World Partition actors from the editor. [ecriture | inconnu]
  - motif : non execute : les seuls acteurs modifiables (MCPTEST_*) ne sont jamais sauvegardes (Save interdit) ; decharger un ...
- **get_collision_channels**() — Returns all available collision channels for use with find_actors. [lecture | verifie]
- **get_current_level**() — Returns the path to the current level asset. [lecture | verifie]
- **get_data_layers**() — Returns the data layer instances in the current world. [lecture | inconnu]
  - motif : aucun outil de lecture independant des data layers
- **get_folders**() — Returns all folder paths currently in use in the outliner. [lecture | verifie]
