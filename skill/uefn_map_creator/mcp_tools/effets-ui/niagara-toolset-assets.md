# NiagaraToolsets.NiagaraToolset_Assets

Famille : `effets-ui` | Alias CLI : aucun | Outils : 3 (verifie 1, echec 1, inconnu 1, dont 0 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **FindNiagaraScripts**(folderPath*,name*,usages*,visibilities*,...) — Recherche des ressources UNiagaraScript correspondant aux filtres donnes. [lecture | echec]
  - erreur : 3 AssetData renvoyes, 3 vides ({}) : serialisation des AssetData cassee
- **GetNiagaraScriptDigest**(objectPath*) — Renvoie les metadonnees de balise du registre des ressources decodees pour une ressource de script Niagara. [lecture | verifie]
- **GetAssetDiscoveryInfo**() — Renvoie les groupes de decouverte de ressources configures du projet. [lecture | inconnu]
  - motif : Renvoie [] (aucun groupe de decouverte) ; rien a recouper.
