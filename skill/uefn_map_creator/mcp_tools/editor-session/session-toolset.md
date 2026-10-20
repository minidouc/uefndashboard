# ValkyrieToolset.SessionToolset

Famille : `editor-session` | Alias CLI : `Session` | Outils : 8 (verifie 2, echec 1, inconnu 5, dont 5 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **GetClientLogEntries**(pattern*,maxResults,startLine) — Search the launched client's log for a pattern, case-insensitively. [lecture | echec]
  - erreur : No client log was found; start a play-in-client session first.
- **GetGameState**() — Get the state of the in-game match on the connected server. [lecture | verifie]
- **GetSessionStatus**() — Get the connection status of the play-in-client session. [lecture | verifie]
- **PushChanges**(bVerseOnly) — Re-send modified project data to the connected server. [DANGEREUX | inconnu]
  - motif : Push Changes : interdit (regle 4)
- **StartGame**() — Start the in-game match on the connected server. [DANGEREUX | inconnu]
  - motif : Controle de match sur serveur connecte (interdit)
- **StartSession**(location,rotation) — Upload the open project and launch a play-in-client session. [DANGEREUX | inconnu]
  - motif : Upload du projet + lancement de session : interdit (a deja bloque le pont)
- **StopGame**() — Stop the running in-game match on the connected server. [DANGEREUX | inconnu]
  - motif : Controle de match sur serveur connecte (interdit)
- **StopSession**() — Disconnect from and tear down the active play-in-client session. [DANGEREUX | inconnu]
  - motif : Controle de session play-in-client (interdit, regle 4)
