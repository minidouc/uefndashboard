# editor_toolset.toolsets.curve_table.CurveTableTools

Famille : `assets-ressources` | Alias CLI : aucun | Outils : 10 (verifie 0, echec 0, inconnu 10, dont 7 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **import_file**(folder_path*,asset_name*,source_file*,interp_mode*) — Imports a file from disk as a CurveTable asset. [DANGEREUX | inconnu]
  - motif : Importe un asset dans le Content Browser
- **add_key**(curve_table*,row_name*,key*) — Adds a key to a row. [DANGEREUX | inconnu]
  - motif : Modifie un asset CurveTable
- **rename_row**(curve_table*,row_name*,new_row_name*) — Renames a row in the curve table. [DANGEREUX | inconnu]
  - motif : Modifie un asset CurveTable
- **set_keys**(curve_table*,row_name*,keys*) — Replaces all keys in a row with the provided list. [DANGEREUX | inconnu]
  - motif : Modifie un asset CurveTable
- **add_row**(curve_table*,row_name*,default_value) — Adds a new row to the curve table with an optional default value. [DANGEREUX | inconnu]
  - motif : Modifie un asset CurveTable
- **create**(folder_path*,asset_name*) — Creates a new CurveTable asset. [DANGEREUX | inconnu]
  - motif : Cree un asset dans le Content Browser
- **diff**(old_asset_path*,new_asset_path*) — Returns a unified text diff between two CurveTable assets. [lecture | inconnu]
- **get_keys**(curve_table*,row_name*) — Returns all keys for a row. [lecture | inconnu]
- **remove_row**(curve_table*,row_name*) — Removes a row from the curve table. [DANGEREUX | inconnu]
  - motif : Modifie un asset CurveTable
- **list_rows**(curve_table*) — Lists the names of all rows in the curve table. [lecture | inconnu]
