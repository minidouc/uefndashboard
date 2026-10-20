# editor_toolset.toolsets.data_table.DataTableTools

Famille : `assets-ressources` | Alias CLI : aucun | Outils : 11 (verifie 0, echec 0, inconnu 11, dont 6 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **import_file**(folder_path*,asset_name*,source_file*,schema*) — Imports a file from disk as a DataTable asset. [DANGEREUX | inconnu]
  - motif : Importe un asset dans le Content Browser
- **create**(folder_path*,asset_name*,schema*) — Creates a new DataTable asset with the specified column schema. [DANGEREUX | inconnu]
  - motif : Cree un asset dans le Content Browser
- **add_rows**(data_table*,row_names*) — Adds new rows with default values to the data table. [DANGEREUX | inconnu]
  - motif : Modifie un asset DataTable
- **diff**(old_asset_path*,new_asset_path*) — Returns a unified text diff between two DataTable assets. [lecture | inconnu]
- **get_rows**(data_table*,row_names*) — Returns the column values for one or more rows as a JSON string. [lecture | inconnu]
- **remove_rows**(data_table*,row_names*) — Removes rows from the data table. [DANGEREUX | inconnu]
  - motif : Modifie un asset DataTable
- **rename_rows**(data_table*,renames*) — Renames one or more rows in the data table. [DANGEREUX | inconnu]
  - motif : Modifie un asset DataTable
- **set_rows**(data_table*,values*) — Sets column values for one or more rows. [DANGEREUX | inconnu]
  - motif : Modifie un asset DataTable
- **get_schema**(data_table*) — Returns the column schema of the data table as a JSON string. [lecture | inconnu]
- **list_rows**(data_table*) — Lists the names of all rows in the data table. [lecture | inconnu]
- **search_row_structs**(struct_name) — Finds structs that can be used as a DataTable schema. [lecture | inconnu]
