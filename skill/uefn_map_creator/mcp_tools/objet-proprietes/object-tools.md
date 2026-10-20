# editor_toolset.toolsets.object.ObjectTools

Famille : `objet-proprietes` | Alias CLI : `Object` | Outils : 6 (verifie 6, echec 0, inconnu 0, dont 0 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **get_properties**(instance*,properties*) — Returns the values of one or more properties on an object. [lecture | verifie]
- **reset_properties**(instance*,properties*) — Resets one or more properties on an object to their default values, removing any per-instance overrides. [ecriture | verifie]
- **set_properties**(instance*,values*) — Sets the values of properties on an object. [ecriture | verifie]
- **get_class**(instance*) — Returns the class of an Unreal object. [lecture | verifie]
- **list_properties**(instance*) — Returns a list of properties that are on the specified object. [lecture | verifie]
- **search_subclasses**(base_class*,class_name) — Finds all subclasses of a given class. [lecture | verifie]
