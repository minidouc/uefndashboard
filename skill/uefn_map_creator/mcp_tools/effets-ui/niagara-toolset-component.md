# NiagaraToolsets.NiagaraToolset_Component

Famille : `effets-ui` | Alias CLI : aucun | Outils : 4 (verifie 3, echec 0, inconnu 1, dont 0 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **SetSystem**(niagaraComponent*,system*,bResetExistingOverrideParameters*) — Definit le systeme Niagara pour un composant. [ecriture | verifie]
- **GetVariable**(component*,var*) — Obtenir la valeur actuelle d'une variable utilisateur specifique sur le composant. [lecture | verifie]
- **SetVariable**(component*,variable*) — Definit la valeur d'une variable utilisateur sur le composant. [ecriture | verifie]
- **GetUserVariables**(component*) — Renvoyer toutes les valeurs de variables d'utilisateur actuellement definies sur le composant. [lecture | inconnu]
