# EditorToolset.LogsToolset

Famille : `editor-session` | Alias CLI : `Logs` | Outils : 4 (verifie 4, echec 0, inconnu 0, dont 0 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **SetVerbosity**(category,verbosity*) — Definir le niveau de verbosite d'une categorie de journal. [ecriture | verifie]
- **GetLogCategories**(filter) — Renvoyer une liste triee des categories de journaux enregistrees. [lecture | verifie]
- **GetLogEntries**(category,pattern,maxEntries) — Renvoyer les entrees de journal du fichier de registre de la session actuelle. [lecture | verifie]
- **GetVerbosity**(category) — Renvoyer le niveau de verbosite actuel pour une categorie de journal. [lecture | verifie]
