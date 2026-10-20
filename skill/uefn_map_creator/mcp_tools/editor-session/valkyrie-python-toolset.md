# ValkyrieToolset.ValkyriePythonToolset

Famille : `editor-session` | Alias CLI : `Python` | Outils : 2 (verifie 0, echec 0, inconnu 2, dont 1 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **EnablePythonInUEFN**() — Enable Python for the active UEFN project. [DANGEREUX | inconnu]
  - motif : Modifie un reglage du projet (Python deja active)
- **IsPythonEnabledInUEFN**() — Whether the main UEFN project has Python enabled and the interpreter is initialized. [lecture | inconnu]
  - motif : Renvoie true, mais le bac a sable de ProgrammaticToolset.execute_tool_script n'expose que json, re, time, copy ...
