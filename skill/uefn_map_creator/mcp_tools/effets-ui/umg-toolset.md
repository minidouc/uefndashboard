# UMGToolSet.UMGToolSet

Famille : `effets-ui` | Alias CLI : aucun | Outils : 21 (verifie 2, echec 0, inconnu 19, dont 14 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **MoveUIComponent**(widgetBlueprint*,widgetName*,componentClassToMove*,relativeToComponentClass*,...) — Deplacer un composant d'interface utilisateur avant ou apres un autre composant sur le meme widget. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **SetNamedSlotContent**(widgetBlueprint*,slotName*,widgetClass*,widgetName*,...) — Deplacer ou ajouter du contenu pour un emplacement nomme. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **AddUIComponent**(widgetBlueprint*,widgetName*,componentClass*) — Ajouter un composant d'interface utilisateur de la classe donnee au widget nomme. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **AddWidget**(widgetBlueprint*,widgetClass*,widgetDisplayName*,parentWidget,...) — Ajouter un widget a l'arborescence a la position specifiee. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **CreateWidgetBlueprint**(folderPath*,assetName*,parentClass*) — Creer une nouvelle ressource de blueprint de widget. [DANGEREUX | inconnu]
  - motif : Cree un asset dans le Content Browser
- **MoveWidget**(widgetBlueprint*,widget*,newParent*,childIndex) — Deplacer un widget vers un nouveau panneau parent a la position specifiee. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **RemoveUIComponent**(widgetBlueprint*,widgetName*,componentClass*) — Supprimer un composant d'interface utilisateur de la classe donnee du widget nomme. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **RenameWidget**(widgetBlueprint*,widget*,newDisplayName*) — Renommer un widget. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **ReplaceWidgetWithNamedSlot**(widgetBlueprint*,widgetToReplace*,namedSlot*) — Remplacer un widget hote par le contenu de l'un de ses creneaux nommes. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **ReplaceWidgetWithTemplate**(widgetBlueprint*,widgetToReplace*,templateClass*) — Remplacer une instance de widget dans l'arborescence des widgets du blueprint par une nouvelle instance creee a partir d'une classe de widget de ... [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **WrapWidgets**(widgetBlueprint*,widgets*,wrapperClass*) — Encapsuler un ou plusieurs widgets dans un nouveau widget de panneau de la classe specifiee. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **RemoveWidget**(widgetBlueprint*,widget*) — Supprimer un widget et ses enfants de l'arborescence. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **ReplaceWidgetWithChild**(widgetBlueprint*,widgetToReplace*) — Remplacer un widget de panneau par son premier enfant, en supprimant le panneau de l'arborescence. [DANGEREUX | inconnu]
  - motif : Modifie un asset WidgetBlueprint
- **CompileWidgetBlueprint**(widgetBlueprint*) — Compiler un blueprint de widget. [DANGEREUX | inconnu]
  - motif : Compile (et donc salit) un asset WidgetBlueprint
- **GetNamedSlots**(widgetBlueprint*) — Renvoyer les emplacements nommes disponibles et leur contenu, le cas echeant (distincts de la hierarchie d'arborescence). [lecture | inconnu]
- **GetWidgetClassInfo**(widgetClass*) — Renvoyer la categorie, la description et s'il s'agit d'un panneau pour une classe de widget unique. [lecture | verifie]
- **GetWidgetDescription**(widgetBlueprint*,startWidget,maxDepth) — Vidage complet des proprietes de chaque widget dans l'arborescence. [lecture | inconnu]
- **GetWidgets**(widgetBlueprint*) — Renvoyer les informations de blueprint et tous les widgets dans l'ordre d'un parcours en profondeur. [lecture | inconnu]
- **GetWidgetTreeDepth**(widgetBlueprint*,startWidget) — Renvoyer la profondeur maximale de l'arbre de widgets. [lecture | inconnu]
- **ListWidgetBlueprints**(folderPath*) — Repertorier les blueprints de widget dans un dossier de contenu. [lecture | inconnu]
- **ListWidgetClasses**(filter) — Repertorier les classes de widgets disponibles, filtrees en option par sous-chaine de nom. [lecture | verifie]
