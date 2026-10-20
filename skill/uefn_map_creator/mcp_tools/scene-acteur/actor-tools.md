# editor_toolset.toolsets.actor.ActorTools

Famille : `scene-acteur` | Alias CLI : `Actor` | Outils : 18 (verifie 18, echec 0, inconnu 0, dont 0 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **add_component**(owner*,component_type*,name*) — Adds a component to an actor instance or blueprint. [ecriture | verifie]
- **add_tag**(actor*,tag*) — Adds a tag to an actor. [ecriture | verifie]
- **diff**(old_actor*,new_actor*) — Returns a unified text diff between two actors. [lecture | verifie]
- **has_tag**(actor*,tag*) — Returns whether an actor has a specific tag. [lecture | verifie]
- **look_at**(actor*,target*) — Rotates an actor so its forward vector points at a world-space position. [ecriture | verifie]
- **remove_tag**(actor*,tag*) — Removes a tag from an actor. [ecriture | verifie]
- **set_actor_transform**(actor*,xform*,worldspace) — Updates the position, rotation, and/or scale of an actor. [ecriture | verifie]
- **set_label**(actor*,label*) — Sets the human-friendly name of the actor. [ecriture | verifie]
- **get_actor_bounds**(actor*) — Returns the bounding box of an actor. [lecture | verifie]
- **get_actor_transform**(actor*) — Returns the position, rotation, and scale of an actor. [lecture | verifie]
- **get_component_actor**(component*) — Returns the actor that owns the specified component. [lecture | verifie]
- **get_components**(actor*,component_type) — Returns the components that an actor contains. [lecture | verifie]
- **get_label**(actor*) — Returns the actor's human friendly name as it appears in the editor. [lecture | verifie]
- **get_parent_component**(component*) — Returns the parent component that this component is attached to, if any. [lecture | verifie]
- **get_root_component**(actor*) — Returns the root component of an actor, if any. [lecture | verifie]
- **get_tags**(actor*) — Returns the list of tags on an actor. [lecture | verifie]
- **remove_component**(component*) — Removes a component from an actor instance or blueprint. [ecriture | verifie]
- **set_parent_component**(component*,parent) — Sets the parent for the specified scene component. [ecriture | verifie]
