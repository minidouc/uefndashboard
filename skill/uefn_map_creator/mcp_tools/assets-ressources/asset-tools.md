# editor_toolset.toolsets.asset.AssetTools

Famille : `assets-ressources` | Alias CLI : `Asset` | Outils : 17 (verifie 8, echec 0, inconnu 9, dont 7 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **duplicate**(path*,new_path*) — Makes a copy of a folder or asset. [DANGEREUX | inconnu]
  - motif : Cree des assets dans le Content Browser
- **move**(path*,new_path*) — Moves or renames an asset or folder. [DANGEREUX | inconnu]
  - motif : Renommage/deplacement d'asset dans le Content Browser
- **create_folder**(path*) — Creates a folder at the specified path. [DANGEREUX | inconnu]
  - motif : Cree un dossier dans le Content Browser
- **delete**(path*) — Deletes an asset or folder. [DANGEREUX | inconnu]
  - motif : Suppression d'asset/dossier dans le Content Browser
- **exists**(path*) — Determines if a folder or asset exists. [lecture | verifie]
- **get_asset_class**(asset_path*) — Gets the class of an asset. [lecture | verifie]
- **get_asset_tags**(asset_path*) — Gets the asset registry tags for an asset. [lecture | verifie]
- **get_dependencies**(asset_path*) — Lists assets that the specified asset depends on. [lecture | verifie]
- **get_metadata_tags**(asset_path*) — Gets the metadata tags for an asset. [lecture | inconnu]
- **get_referencers**(asset_path*) — Lists assets that reference the specified asset. [lecture | verifie]
- **is_dirty**(asset_path*) — Checks whether an asset has unsaved changes. [lecture | inconnu]
  - motif : Reverifie en phase 3 sur le package du niveau (avant/apres ecriture).
- **list_folders**(root_path*,recursive) — Lists the folders contained within a folder. [lecture | verifie]
- **load_asset**(asset_path*) — Loads an asset from the project. [lecture | verifie]
- **reload_asset**(asset_path*) — Reloads an asset from disk, discarding any unsaved in-memory changes. [DANGEREUX | inconnu]
  - motif : Recharge depuis le disque en jetant les modifications non sauvegardees
- **save_assets**(asset_paths*) — Saves assets to disk. [DANGEREUX | inconnu]
  - motif : Sauvegarde : interdit (regle 4)
- **update_metadata_tags**(asset_path*,set_tags,remove_tags) — Sets or removes metadata tags on an asset. [DANGEREUX | inconnu]
  - motif : Modifie les metadonnees d'un asset du projet
- **find_assets**(folder_path,name,asset_type,recursive,...) — Searches the project for assets that match specific criteria. [lecture | verifie]
