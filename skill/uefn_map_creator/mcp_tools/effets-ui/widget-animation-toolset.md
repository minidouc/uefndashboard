# WidgetAnimationToolset.WidgetAnimationToolset

Famille : `effets-ui` | Alias CLI : aucun | Outils : 10 (verifie 0, echec 0, inconnu 10, dont 7 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **AddWidgetToAnimation**(widgetBlueprint*,animation*,objectToBind*) — Ajouter un UWidget (ou un UPanelSlot avec du contenu non nul) comme liaison possessible sur une animation de widget. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **RenameWidgetAnimation**(widgetBlueprint*,animation*,newName*) — Renommer une animation. [DANGEREUX | inconnu]
  - motif : Renomme dans un asset WidgetBlueprint
- **CreateWidgetAnimation**(widgetBlueprint*,animationName*,lengthSeconds) — Creer une nouvelle UWidgetAnimation sur un blueprint de widget et renvoyer son resume. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **FindWidgetAnimation**(widgetBlueprint*,animationName*) — Trouver une animation par nom interne. [lecture | inconnu]
- **RemoveWidgetAnimation**(widgetBlueprint*,animation*) — Supprimer une animation d'un blueprint de widget [DANGEREUX | inconnu]
  - motif : Supprime dans un asset WidgetBlueprint
- **RemoveWidgetBinding**(animation*,bindingGuid*) — Supprimer une liaison (par GUID) d'une animation de widget. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **SetWidgetAnimationDisplayLabel**(animation*,displayLabel*) — Definir l'etiquette d'affichage destinee a l'utilisateur affichee dans le panneau Animations [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **SetWidgetAnimationLength**(animation*,lengthSeconds*) — Definir la longueur de lecture de l'animation en secondes. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **GetWidgetAnimationBindings**(animation*) — Obtenir toutes les liaisons sur une animation de widget en tant qu'entrees FMovieSceneBindingProxy [lecture | inconnu]
- **ListWidgetAnimations**(widgetBlueprint*) — Lister toutes les animations sur un blueprint de widget [lecture | inconnu]
