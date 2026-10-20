# VerseFieldsToolset.VerseFieldsToolset

Famille : `objet-proprietes` | Alias CLI : aucun | Outils : 7 (verifie 0, echec 0, inconnu 7, dont 5 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **BindWidgetPropertyToVerseField**(widgetBlueprint*,verseFieldName*,targetWidget*,widgetPropertyPath*,...) — Binds a widget property to a Verse field on the same Widget Blueprint (the field is the MVVM SelfContext source). [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **EditVerseField**(widgetBlueprint*,fieldName*,spec*,newName*) — Edits an existing Verse field (retype/default/access/mutability). [DANGEREUX | inconnu]
  - motif : Modifie et recompile un asset WidgetBlueprint
- **AddVerseField**(widgetBlueprint*,fieldName*,spec*) — Adds a new Verse field (variable) to a Widget Blueprint. [DANGEREUX | inconnu]
  - motif : Modifie et recompile un asset WidgetBlueprint
- **DuplicateVerseField**(widgetBlueprint*,fieldName*,newName*) — Duplicates a Verse field under a new name. [DANGEREUX | inconnu]
  - motif : Modifie et recompile un asset WidgetBlueprint
- **RemoveVerseField**(widgetBlueprint*,fieldName*) — Removes a Verse field by name. [DANGEREUX | inconnu]
  - motif : Modifie et recompile un asset WidgetBlueprint
- **ListVerseFields**(widgetBlueprint*) — Lists the Verse-authored fields on a Widget Blueprint. [lecture | inconnu]
- **GetSupportedVerseFieldTypes**() — Accepted Spec.Type / Spec.EventParameterTypes values. [lecture | inconnu]
