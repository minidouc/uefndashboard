# EditorToolset.EditorAppToolset

Famille : `editor-session` | Alias CLI : `EditorApp` | Outils : 37 (verifie 29, echec 2, inconnu 6, dont 0 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **AddAssetsToCollection**(collection*,assetPaths*) — Ajouter des ressources a la collection specifiee. [ecriture | verifie]
- **CreateCollection**(collectionName*,shareType*) — Creer une nouvelle collection statique. [ecriture | verifie]
- **RemoveAssetsFromCollection**(collection*,assetPaths*) — Supprimer les ressources de la collection specifiee. [ecriture | verifie]
- **SetCVarValue**(name*,value*) — Definir la valeur d'une variable de console. [ecriture | verifie]
- **SetShowFlag**(flagName*,bEnabled*) — Activer/desactiver un indicateur d'affichage de moteur nomme sur le hublot actif de l'editeur de niveau (par ex. [ecriture | verifie]
- **CaptureAssetImage**(assetPath*) — Rendre une vignette pour la ressource specifiee (par ex. [lecture | verifie]
- **DestroyCollection**(collection*) — Supprimer la collection specifiee. [ecriture | verifie]
- **FocusOnActors**(actors*) — Repositionner la camera de l'editeur de niveau pour faire le focus sur les acteurs specifies. [ecriture | inconnu]
- **GetAssetThumbnails**(assetPaths*) — Renvoyer les vignettes mises en cache existantes des ressources (les images affichees par le navigateur de contenu) sans charger ou afficher les ... [lecture | verifie]
- **GetCollectionAssets**(collection*) — Renvoyer les ressources de la collection specifiee. [lecture | verifie]
- **GetCVarValue**(name*) — Lire la valeur actuelle d'une variable de console comme sa representation de chaine canonique (par ex. [lecture | verifie]
- **GetShowFlag**(flagName*) — Lire si un indicateur d'affichage de moteur nomme est actuellement active sur le hublot actif de l'editeur de niveau. [lecture | verifie]
- **OpenEditorForAsset**(assetPath*) — Ouvrir un editeur de ressources pour la ressource specifiee. [ecriture | echec]
  - erreur : Failed to open editor for asset: /Engine/BasicShapes/Cube.Cube
- **ScreenCoordsToWorld**(coords*,traceDistance) — Rechercher la position dans le monde de l'objet solide le plus proche a un ensemble donne de coordonnees d'espace de visualisation normalisees. [lecture | verifie]
- **SearchCVars**(name*) — Rechercher toutes les variables de console qui contiennent un nom donne. [lecture | verifie]
- **SelectActors**(actors*) — Selectionne les acteurs specifies dans la scene actuelle. [ecriture | verifie]
- **SelectAssets**(assetPaths*) — Selectionner les ressources specifiees dans le navigateur de contenu. [ecriture | verifie]
- **SelectOutlinerFolders**(folderPaths*) — Selectionner les dossiers specifies dans chaque organisateur de scene ouvert. [ecriture | echec]
  - erreur : Folder(s) not found in any outliner: /Background
- **SetCameraTransform**(transform*) — Definir la position et la rotation de la camera du hublot de niveau. [ecriture | verifie]
- **SetContentBrowserPath**(path*) — Parcourir le navigateur de contenu actif jusqu'au chemin de dossier specifie. [ecriture | inconnu]
  - motif : Failed to navigate content browser to '/Engine/BasicShapes': ended up at ''.
- **SetEditorMode**(modeId*) — Activer le mode d'editeur specifie. [ecriture | verifie]
- **SetViewportViewMode**(viewMode*) — Definir le mode d'affichage du hublot actif de l'editeur de niveau (par ex. [ecriture | verifie]
- **ShowNotification**(message*,state,expireDuration) — Afficher une notification d'editeur transitoire (toast Slate, en bas a droite). [ecriture | inconnu]
  - motif : Toast Slate : aucun outil ne relit l'UI, verification seulement si le message est journalise.
- **WorldPosToScreenCoords**(position*) — Convertir une position dans l'espace du monde en espace-ecran normalise base sur la camera du hublot de l'editeur. [lecture | verifie]
- **CaptureEditorImage**() — Capturer une image de toute l'application de l'editeur telle que l'utilisateur la voit. [lecture | verifie]
- **CaptureViewport**(captureTransform,annotations,bShowUI) — Capturer le hublot de niveau avec des annotations facultatives. [lecture | verifie]
- **GetActiveEditorModes**() — Renvoyer les identifiants des modes d'editeur actuellement actifs. [lecture | verifie]
- **GetCameraTransform**() — Renvoyer la position et la rotation de la camera du hublot de niveau. [lecture | verifie]
- **GetContentBrowserPath**() — Obtenir le chemin actuel du navigateur de contenu actif. [lecture | inconnu]
  - motif : Le chemin a change entre deux lectures (racine du projet → /Fortnite/Meshes/BasicShapes), probablement par ...
- **GetOpenAssets**() — Obtenir la liste des ressources actuellement ouvertes dans les editeurs de ressources. [lecture | inconnu]
- **GetSelectedActors**() — Obtenir les acteurs actuellement selectionnes dans l'editeur de niveau. [lecture | verifie]
- **GetSelectedAssets**() — Obtenir la liste des ressources selectionnees dans le navigateur de contenu. [lecture | verifie]
- **GetSelectedOutlinerFolders**() — Obtenir les chemins d'acces aux dossiers selectionnes dans tous les organiseurs de scene ouverts. [lecture | inconnu]
- **GetVisibleActors**() — Renvoyer tous les acteurs du niveau actuel dont les limites se recoupent avec le frustum du hublot. [lecture | verifie]
- **ListCollections**() — Repertorier toutes les collections dans le navigateur de contenu. [lecture | verifie]
- **ListEditorModes**() — Repertorier les identifiants de tous les modes d'editeur enregistres (par ex. [lecture | verifie]
- **ListShowFlags**() — Repertorier chaque indicateur d'affichage du moteur avec son nom d'affichage et son groupe d'editeur. [lecture | verifie]
