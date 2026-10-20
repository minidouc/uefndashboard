# editor_toolset.toolsets.material_instance.MaterialInstanceTools

Famille : `assets-ressources` | Alias CLI : aucun | Outils : 14 (verifie 3, echec 0, inconnu 11, dont 8 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **create**(folder_path*,asset_name*,parent*) — Creates a new MaterialInstanceConstant asset derived from a parent material. [DANGEREUX | inconnu]
  - motif : Cree un asset dans le Content Browser
- **set_parameter_override**(instance*,name*,override*) — Enables or disables a parameter override on a material instance. [DANGEREUX | inconnu]
  - motif : Modifie un asset MaterialInstance
- **set_scalar_parameter**(instance*,name*,value*) — Sets the value of a scalar parameter on a material instance. [DANGEREUX | inconnu]
  - motif : Modifie un asset MaterialInstance
- **set_static_switch_parameter**(instance*,name*,value*) — Sets the value of a static switch parameter on a material instance. [DANGEREUX | inconnu]
  - motif : Modifie un asset MaterialInstance
- **set_texture_parameter**(instance*,name*,value*) — Assigns a texture to a texture parameter on a material instance. [DANGEREUX | inconnu]
  - motif : Modifie un asset MaterialInstance
- **set_vector_parameter**(instance*,name*,value*) — Sets the value of a vector parameter on a material instance. [DANGEREUX | inconnu]
  - motif : Modifie un asset MaterialInstance
- **diff**(old_asset_path*,new_asset_path*) — Returns a unified text diff between two MaterialInstanceConstant assets. [lecture | inconnu]
- **get_scalar_parameter**(instance*,name*) — Gets the current value of a scalar parameter on a material instance. [lecture | verifie]
- **get_static_switch_parameter**(instance*,name*) — Gets the value of a static switch parameter on a material instance. [lecture | inconnu]
- **get_texture_parameter**(instance*,name*) — Gets the texture assigned to a texture parameter on a material instance. [lecture | inconnu]
- **get_vector_parameter**(instance*,name*) — Gets the current value of a vector parameter on a material instance. [lecture | verifie]
- **set_parent**(instance*,parent*) — Changes the parent of a material instance. [DANGEREUX | inconnu]
  - motif : Modifie un asset MaterialInstance
- **clear_parameters**(instance*) — Clears all parameter overrides on a material instance, reverting to parent defaults. [DANGEREUX | inconnu]
  - motif : Modifie un asset MaterialInstance
- **list_parameters**(material*) — Returns all parameters exposed by a material or instance, with their names and types. [lecture | verifie]
