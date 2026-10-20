# MVVMToolset.MVVMToolset

Famille : `effets-ui` | Alias CLI : aucun | Outils : 15 (verifie 1, echec 0, inconnu 14, dont 8 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **CreateViewBinding**(widgetBlueprint*,sourceContext*,sourcePropertyPath*,destinationContext*,...) — Creer une liaison de vue entre SourceProperty et la propriete de destination. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **CreateViewEventBinding**(widgetBlueprint*,eventContext*,eventPropertyPath*,destinationContext*,...) — Creer une liaison d'evenements de vue entre EventProperty et la propriete de destination. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **AddViewModelProperty**(viewModel*,propertyName*,propertyType*,defaultValue*) — Ajouter une propriete a un ViewModel existant [DANGEREUX | inconnu]
  - motif : Modifie un asset ViewModel
- **SetBindingMode**(widgetBlueprint*,bindingId*,mode*) — Definir le mode de liaison (OneTimeToDestination/OneWayToDestination/TwoWay/OneWayToSource) d'une liaison de vue existante. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **AddViewModelToWidget**(widgetBlueprint*,viewModelClass*) — Ajouter un ViewModel au WidgetBlueprint [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **GetWidgetViewConfig**(widgetBlueprint*,outConfiguration*) — Renvoyer la configuration de la vue MVVM. [lecture | inconnu]
- **ListBindableWidgetProperties**(widgetBlueprint*,widget*) — Repertorier les chemins de proprietes pouvant etre lies sur un widget (candidats comme source/destination de liaison). [lecture | inconnu]
- **RemoveWidgetViewBinding**(widgetBlueprint*,bindingId*) — Supprimer la liaison de vue sur le WidgetBlueprint [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **SetWidgetViewConfig**(widgetBlueprint*,configuration*) — Ecrire la configuration de la vue MVVM sur la vue du WidgetBlueprint. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **FixupMVVMData**(widgetBlueprint*) — Tenter de reparer les donnees MVVM. [DANGEREUX | inconnu]
  - motif : Regenere les graphes d'un asset WidgetBlueprint
- **ListConversionFunctions**(widgetBlueprint*) — Repertorier les fonctions de conversion disponibles pour un WidgetBlueprint qui lient une propriete source a une propriete de destination [lecture | inconnu]
- **ListViewModels**(searchPath*) — Repertorier tous les ViewModel sous le chemin de recherche [lecture | verifie]
- **ListWidgetViewBindings**(widgetBlueprint*) — Repertorier toutes les liaisons de vue sur le WidgetBlueprint [lecture | inconnu]
- **ListWidgetViewEvents**(widgetBlueprint*) — Repertoriez les proprietes d'evenement disponibles pour un WidgetBlueprint (c'est-a-dire un delegue de multidiffusion) [lecture | inconnu]
- **ListWidgetViewModels**(widgetBlueprint*) — Repertorier tous les ViewModel sur le WidgetBlueprint [lecture | inconnu]
