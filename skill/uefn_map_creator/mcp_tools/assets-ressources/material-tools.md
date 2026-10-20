# editor_toolset.toolsets.material.MaterialTools

Famille : `assets-ressources` | Alias CLI : aucun | Outils : 25 (verifie 9, echec 1, inconnu 15, dont 14 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **connect_expressions**(from_expression*,from_output_name*,to_expression*,to_input_name*) — Connects an expression node's output pin to another expression node's input pin. [DANGEREUX | inconnu]
  - motif : Modifie un asset Material
- **connect_to_output**(expression*,output_name*,material_property*) — Connects an expression node's output to one of the material's output properties. [DANGEREUX | inconnu]
  - motif : Modifie un asset Material
- **rename_parameter_group**(material_or_function*,old_name*,new_name*) — Renames a parameter group across all parameter expressions in a Material or MaterialFunction. [DANGEREUX | inconnu]
  - motif : Modifie un asset Material
- **add_expression**(material_or_function*,expression_class*,x,y) — Adds a new expression node to a Material or MaterialFunction graph. [DANGEREUX | inconnu]
  - motif : Modifie un asset Material
- **create_function**(folder_path*,asset_name*) — Creates a new empty MaterialFunction asset. [DANGEREUX | inconnu]
  - motif : Cree un asset dans le Content Browser
- **create_material**(folder_path*,asset_name*) — Creates a new empty Material asset. [DANGEREUX | inconnu]
  - motif : Cree un asset dans le Content Browser
- **create_parameter_collection**(folder_path*,asset_name*) — Creates a new empty MaterialParameterCollection (MPC) asset. [DANGEREUX | inconnu]
  - motif : Cree un asset dans le Content Browser
- **delete_expression**(material_or_function*,expression*) — Removes an expression node from a Material or MaterialFunction graph. [DANGEREUX | inconnu]
  - motif : Modifie un asset Material
- **delete_parameter_group**(material_or_function*,group_name*) — Removes a parameter group, ungrouping all parameters that belong to it. [DANGEREUX | inconnu]
  - motif : Modifie un asset Material
- **diff_function**(old_asset_path*,new_asset_path*) — Returns a unified text diff between two MaterialFunction assets. [lecture | verifie]
- **diff_material**(old_asset_path*,new_asset_path*) — Returns a unified text diff between two Material assets. [lecture | verifie]
- **disconnect_expressions**(to_expression*,to_input_name*) — Disconnects the input pin of an expression node, removing whatever is connected to it. [DANGEREUX | inconnu]
  - motif : Modifie un asset Material
- **disconnect_from_output**(material*,material_property*) — Disconnects the expression currently connected to a material output property. [DANGEREUX | inconnu]
  - motif : Modifie un asset Material
- **get_expression_inputs**(material_or_function*,expression*) — Returns the current wiring of each input pin on a material expression. [lecture | verifie]
- **get_property_input**(material*,material_property*) — Returns the expression and output pin feeding a material output property. [lecture | verifie]
- **delete_unused_expressions**(material*) — Deletes all expression nodes not connected to any material output. [DANGEREUX | inconnu]
  - motif : Modifie un asset Material
- **get_expression_input_names**(expression*) — Returns the names of all input pins on a material expression node. [lecture | verifie]
- **get_expression_output_names**(expression*) — Returns the names of all output pins on a material expression node. [lecture | verifie]
- **get_expressions**(material_or_function*) — Returns all expression nodes in a Material or MaterialFunction graph. [lecture | verifie]
- **get_referencing_materials**(material_function*) — Returns asset data for all Materials that reference this MaterialFunction. [lecture | echec]
  - erreur : renvoie 242 objets AssetData vides ({}) pour SmoothCeil : serialisation cassee, aucun nom exploitable
- **get_statistics**(material*) — Returns compiled shader statistics for a Material or MaterialInstance on the current shader platform: instruction counts, texture-sample counts, and ... [lecture | inconnu]
- **layout_expressions**(material_or_function*) — Automatically arranges all expression nodes in a Material or MaterialFunction graph. [DANGEREUX | inconnu]
  - motif : Modifie un asset Material
- **list_expression_classes**(material_or_function*,search) — Returns MaterialExpression subclasses valid for the given context. [lecture | verifie]
- **list_parameter_groups**(material_or_function*) — Returns the unique parameter group names defined in a Material or MaterialFunction. [lecture | verifie]
- **recompile**(material_or_function*) — Recompiles a Material or MaterialFunction after edits. [DANGEREUX | inconnu]
  - motif : Recompile (et peut salir) un asset Material
