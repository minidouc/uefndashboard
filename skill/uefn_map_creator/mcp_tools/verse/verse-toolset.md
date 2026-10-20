# ValkyrieToolset.VerseToolset

Famille : `verse` | Alias CLI : `Verse` | Outils : 10 (verifie 4, echec 0, inconnu 6, dont 6 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **Copy**(sourcePath*,destPath*,bRecursive*) — Copy a .verse file, or a directory whose subtree contains only .verse files. [DANGEREUX | inconnu]
  - motif : Cree des fichiers dans le projet
- **Replace**(path*,oldString*,newString*,bReplaceAll) — Replace OldString with NewString in a .verse file. [DANGEREUX | inconnu]
  - motif : Modifie le code source Verse du projet
- **WriteFile**(path*,content*,span,bCreateIfMissing*) — Create, overwrite, or edit a region of a .verse file. [DANGEREUX | inconnu]
  - motif : Modifie le code source Verse du projet
- **Delete**(path*,bRecursive*) — Delete a .verse file, or a directory whose subtree contains only .verse files. [DANGEREUX | inconnu]
  - motif : Supprime des fichiers du projet
- **Grep**(pattern*,pathGlob*,maxResults) — Search .verse files for a pattern. [lecture | verifie]
- **ListFiles**(path*,bRecursive*) — List a directory's .verse files and subdirectories (other files are omitted). [lecture | verifie]
- **Move**(sourcePath*,destPath*) — Move/rename a .verse file, or a directory whose subtree contains only .verse files. [DANGEREUX | inconnu]
  - motif : Renomme des fichiers du projet
- **CreateDirectory**(path*) — Create a directory, including any missing parent directories. [DANGEREUX | inconnu]
  - motif : Cree un dossier dans le projet
- **ReadFile**(path*,span) — Read a .verse file. [lecture | verifie]
- **BuildAll**() — Compile all Verse code in the project. [ecriture | verifie]
