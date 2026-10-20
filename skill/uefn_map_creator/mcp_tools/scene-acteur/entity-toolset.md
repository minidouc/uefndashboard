# ValkyrieToolset.EntityToolset

Famille : `scene-acteur` | Alias CLI : `Entity` | Outils : 13 (verifie 12, echec 1, inconnu 0, dont 0 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **SetComponentProperty**(component*,propertyName*,value*) — Write one property on a component, by its friendly Verse name. [ecriture | verifie]
- **AddComponent**(entity*,componentClass*) — Attach a component to a Verse entity. [ecriture | verifie]
- **CreateEntity**(entityClass*,transform*,name,parentEntity) — Create a Verse entity in the current editor scene. [ecriture | verifie]
- **GetComponentProperty**(component*,propertyName*) — Read a component's editable property value, by its friendly Verse name. [lecture | verifie]
- **RemoveComponent**(entity*,componentClass*) — Remove a component from a Verse entity. [ecriture | verifie]
- **SetEntityTransform**(entity*,transform*) — Set a Verse entity's world transform (adds a transform component if it has none). [ecriture | verifie]
- **DeleteEntity**(entity*) — Delete a Verse entity from the current editor scene. [ecriture | echec]
  - erreur : Cannot delete the root entity.
- **GetComponents**(entity*) — List the components attached to a Verse entity. [lecture | verifie]
- **GetEntityTransform**(entity*) — Get a Verse entity's world transform. [lecture | verifie]
- **ListComponentProperties**(component*) — List a Verse component's editable properties. [lecture | verifie]
- **FindEntities**(rootEntity,bRecursive,nameFilter) — Find Verse entities in the current editor scene, optionally scoped and filtered. [lecture | verifie]
- **ListComponentClasses**(nameFilter) — List the concrete Verse component classes that can be attached (verse::component subclasses), optionally filtered. [lecture | verifie]
- **ListEntityClasses**(nameFilter) — List the concrete Verse entity classes that can be instantiated (verse::entity subclasses), optionally filtered. [lecture | verifie]
