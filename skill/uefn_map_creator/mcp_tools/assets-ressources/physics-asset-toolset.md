# PhysicsToolsets.PhysicsAssetToolset

Famille : `assets-ressources` | Alias CLI : aucun | Outils : 17 (verifie 2, echec 0, inconnu 15, dont 12 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **SetBox**(physicsAsset*,boneName*,shapeName*,center*,...) — Ajouter ou remplacer une primitive de collision de boite sur un corps. [DANGEREUX | inconnu]
  - motif : Modifie un asset PhysicsAsset
- **SetCapsule**(physicsAsset*,boneName*,shapeName*,center*,...) — Ajouter ou remplacer une primitive de collision de capsule sur un corps. [DANGEREUX | inconnu]
  - motif : Modifie un asset PhysicsAsset
- **SetSphere**(physicsAsset*,boneName*,shapeName*,center*,...) — Ajouter ou remplacer une primitive de collision de sphere sur un corps. [DANGEREUX | inconnu]
  - motif : Modifie un asset PhysicsAsset
- **AddConstraint**(physicsAsset*,bone1Name*,bone2Name*) — Ajouter une nouvelle contrainte entre deux corps. [DANGEREUX | inconnu]
  - motif : Modifie un asset PhysicsAsset
- **RemoveConstraint**(physicsAsset*,bone1Name*,bone2Name*) — Supprimer la contrainte entre deux corps. [DANGEREUX | inconnu]
  - motif : Modifie un asset PhysicsAsset
- **RemoveShape**(physicsAsset*,boneName*,shapeName*) — Supprimer une primitive de collision d'un corps par nom. [DANGEREUX | inconnu]
  - motif : Modifie un asset PhysicsAsset
- **SetBodyMassScale**(physicsAsset*,boneName*,massScale*) — Definir le multiplicateur d'echelle de masse du corps donne. [DANGEREUX | inconnu]
  - motif : Modifie un asset PhysicsAsset
- **SetBodyPhysicsMode**(physicsAsset*,boneName*,mode*) — Definir le mode de simulation physique du corps donne. [DANGEREUX | inconnu]
  - motif : Modifie un asset PhysicsAsset
- **AddBody**(physicsAsset*,boneName*) — Ajouter un nouveau corps vide pour l'os donne. [DANGEREUX | inconnu]
  - motif : Modifie un asset PhysicsAsset
- **CreateFromMesh**(meshPath*,bAssignToMesh*) — Creer une ressource physique a partir d'un maillage squelettique, en generant automatiquement des corps de collision pour chaque os. [DANGEREUX | inconnu]
  - motif : Cree un asset et peut modifier le mesh source
- **GetBodyMassScale**(physicsAsset*,boneName*) — Renvoyer le multiplicateur d'echelle de masse du corps donne. [lecture | inconnu]
- **GetBodyPhysicsMode**(physicsAsset*,boneName*) — Renvoyer le mode de simulation physique pour le corps donne. [lecture | inconnu]
- **GetBodyShapes**(physicsAsset*,boneName*) — Renvoyer toutes les formes de collision attribuees a un corps. [lecture | inconnu]
- **RemoveBody**(physicsAsset*,boneName*) — Supprimer le corps de l'os donne ainsi que toutes les contraintes qui y font reference. [DANGEREUX | inconnu]
  - motif : Modifie un asset PhysicsAsset
- **SetConstraintLimits**(physicsAsset*,info*) — Mettre a jour les limites angulaires d'une contrainte existante. [DANGEREUX | inconnu]
  - motif : Modifie un asset PhysicsAsset
- **GetBodyNames**(physicsAsset*) — Renvoyer le nom de l'os pour chaque corps rigide dans une ressource physique. [lecture | verifie]
- **GetConstraints**(physicsAsset*) — Renvoyer toutes les contraintes de la ressource physique avec leurs limites angulaires actuelles. [lecture | verifie]
