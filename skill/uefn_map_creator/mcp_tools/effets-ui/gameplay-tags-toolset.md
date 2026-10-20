# GameplayTagsToolset.GameplayTagsToolset

Famille : `effets-ui` | Alias CLI : aucun | Outils : 4 (verifie 3, echec 0, inconnu 1, dont 0 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **FindReferencersByTag**(tagName*) — Renvoyer les ressources qui font reference a une balise de jeu. [lecture | inconnu]
  - motif : Pour "Creative" : un seul referent (/CRD_DBNO/Device_DBNO_V2.Device_DBNO_V2_C) ; aucun outil sur ne permet de recouper.
- **GetTagInfo**(tagName*) — Renvoyer des informations detaillees sur une balise de jeu en particulier. [lecture | verifie]
- **ListTags**(parentTag*) — Renvoyer les balises de jeu enregistrees dans le projet. [lecture | verifie]
- **ListTagsInSource**(tagSource*) — Renvoyer toutes les balises de jeu definies dans une source de balises specifique. [lecture | verifie]
