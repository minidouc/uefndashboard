# Lecons apprises (memoire procedurale du studio)

> WP3 (« procedural memory », consolidation) : ce que le studio a appris **en le payant**.
> La section « Regles actives » est injectee a chaque session par le hook de demarrage.
> Une regle = une ligne, avec sa preuve. Si deux regles se recouvrent, on les fusionne.

## Regles actives
- Une capture n'est une preuve que si l'image montre ce qu'elle annonce : mesures (`v_visuel`) + critique + humain. *(corpo-plaza : « nuit » de plein jour, captures de murs, toutes declarees PASS)*
- Un validateur ne lit jamais un champ declare : il remonte a la reponse MCP brute. *(corpo-plaza : `rc: 0` et « 24 preexistants » ecrits en dur, bornes inventees quand la relecture echouait)*
- Un validateur qui passe toujours est un validateur casse : l'auto-test golden tourne avant toute validation. *(corpo-plaza : test de chevauchement force a `True`, 344 chevauchements ignores)*
- L'agent evalue ne touche jamais son juge : hooks + empreinte MANIFEST. *(corpo-plaza : validateurs modifies pendant le BUILD)*
- Cube plus fin que 256 uu : une SURFACE s'epaissit vers le bas (son dessus reste a la cote), un OBJET pose dessus s'epaissit vers le haut (sa base reste au sol). *(corpo-plaza : sols rehausses de ~125 uu, spawn enterre ; generateur arene : couverts enfonces dans le sol)*
- Une rampe touche par nature ce qu'elle relie : le generateur declare le raccord (`relie=`) avec sa justification.
- A CONFIRMER a la premiere rampe posee (capture) : convention de pitch Unreal (positif = l'avant monte). Les AABB ne voient pas le sens d'une pente.
- Parkour : les distances de saut ne sont pas inventees. Par defaut, ce sont celles de la marche ; les vraies valeurs se mesurent en playtest.
- Le cout vient des tours de modele : un script par tache repetitive, `build_complet.py` pour tout le BUILD, critique une seule fois.
- Le spawn est declare a part dans `placements.json` (cle `spawn`) : les scripts l'ajoutent explicitement. *(corpo-plaza : jamais pose par le plan)*
- Decoupe des grandes primitives : grille ceil(dim/3900) en X et Y, tournee selon le yaw ; jamais 2x2 fixe. *(corpo-plaza : segments encore > portee)*
- Verifier le plan (`check_plan.py`) AVANT de poser : un defaut coute 0 appel MCP au lieu d'un lot. *(corpo-plaza : escalier C2 a 900 uu de toute surface)*
- Une relecture groupee `find_actors` par lot remplace 60 `get_actor_bounds` : meme preuve, beaucoup plus rapide.
- La jauge RAM se mesure en cache de 20 s, et seule la memoire libre machine compte : le working set de l'editeur grossit avec le niveau. *(corpo-plaza : 17 min d'attente sur un critere qui mesurait la machine, pas le risque)*
- `bAutoUpdateBounds=true` sur LevelBounds : les bornes peuvent revenir en arriere ; elles sont relues apres CHAQUE save. *(corpo-plaza lot 0 : Z_max revenu a 256)*
- Un import se fait sous la racine du projet (`/<guid>/...`), jamais sous `/Game`. *(corpo-plaza T6)*
- Accelerer = presenter la liste de ce qu'on sacrifie et la faire confirmer ; jamais en silence. *(corpo-plaza : consignes reinjectees en cours de session, DA perdue)*
- Une seule session ecrit dans l'editeur ; la reprise par un modele exterieur suit `docs/reprise-externe.md`. *(corpo-plaza : modele exterieur hors architecture, lots non valides)*
- Le state reste petit (< 20 Ko) ; l'historique va dans `events.jsonl`, jamais relu en entier. *(corpo-plaza : state de 147 Ko, perime)*
- `set_actor_folder` rend rc=0 sans effet (`folderPath` relu = "None") : `rollback --lot` cible donc aussi les `refPath` enregistres dans `lots/lot_NN.json`. *(corpo-plaza lot 1, 2026-10-27 : 60 appels rc=0, 0 acteur range)*
- Retirer un spawner retire aussi son `PlayerStartCreative` : le second retrait echoue « not valid Actor ». `rollback.py` tolere cette erreur et verifie l'absence par la relecture `find_actors`. *(corpo-plaza rollback, 2026-10-27, 2 fois)*
- Une archive de lot ne finit jamais en `.json` : les validateurs lisent `lots/lot_*.json` et comptent l'ancien lot (`lot_NN.json.annule_<run>`). *(corpo-plaza lot 1, 2026-10-27 : SE_LUM_2 « a 450 uu » alors que pose exacte)*
- L'editeur ne pose pas les dimensions declarees : primitive >= 256 uu par axe (cube X/Y centres, cylindre Z centre), devices a taille fixe (Billboard 358x28x162 base au pivot...). `check_plan` lit `config/bornes_devices.json` ; un nouveau device y entre avec sa preuve relue. *(corpo-plaza lots 1-2 : 0 ecart plan/pose apres correction, 69 chevauchements jusque-la invisibles)*
- Un volume d'environnement (ciel, light rig) touche tout : il ne compte jamais comme appui. `check_plan` l'exclut des flottants ; le validateur, lui, l'accepte encore (signale a l'humain). *(corpo-plaza : 14 enseignes/fleches « posees » sur DELTA_SKY_NUIT)*
- Les lots sont tries par z_min reel : un appui commence plus bas que ce qu'il porte, il est donc pose avant. *(corpo-plaza lot 2 : 11 flottants dont les sols etaient au lot 3)*
- Sous Git Bash, un chemin d'asset `/CRP_...` passe en `C:/Program Files/Git/CRP_...` : prefixer `MSYS_NO_PATHCONV=1`. *(corpo-plaza spike poser-asset, 2026-10-27 : « Could not load asset »)*
- Poser un Skydome / Light Rig ne fait pas la nuit. `set_properties` sur le Skydome est PROUVE (lightSource Moon 1, intensites 1, ciel bleu nuit : relus apres save) mais le viewport editeur n'en montre rien : les captures `nuit_*` se prennent en session, pas dans l'editeur. *(corpo-plaza 2026-10-27 : luminance 123/197 avant et apres reglage)*
- Le Verse se compile par `spike_capacite.py compiler-verse` (`VerseToolset.BuildAll`) : rc=0 veut dire « compilation lancee », le code n'est bon que si aucun diagnostic `Error`. `customizable_light_device` n'a ni couleur ni intensite en Verse : ce sont des proprietes du device. *(corpo-plaza 2026-10-28 : 10 erreurs vErr 3506 puis 0)*
- Un rollback en serie peut s'arreter sur la jauge RAM au milieu : relire le preflight (acteurs restants) AVANT `plan --refaire`, puis relancer `rollback --lot N` sur le lot reste. *(corpo-plaza 2026-10-28 : lot 5 laisse en place, 60 acteurs)*
- Les assets BP du pack Sunburst renvoient une boite ~1200^3 (composant invisible) : ils n'entrent que la ou cette boite tient. *(corpo-plaza : 13 items sur 23 integres)*
- L'import de texture marche sous `<content_root>/CorpoPlaza` (`import-texture` PROUVE). L'appliquer demande `MaterialInstanceTools.create` + `set_texture_parameter` (non prouves), puis `set_properties` sur le COMPOSANT du cube : l'acteur n'expose que `rootComponent`. *(corpo-plaza 2026-10-28)*
- Chaine materiau PROUVEE : `MaterialInstanceTools.create` (parent du pack), `set_texture_parameter`, `set_scalar_parameter`, save de l'instance rc=0, puis `set_properties` `OverrideMaterials` sur le COMPOSANT `<acteur>.CP_<id>_cube`. Relecture par `get_properties` (`get_texture_parameter` est INCONNU). Le rendu, lui, reste a confirmer a l'image. *(corpo-plaza 2026-10-28 : sol S0 toujours blanc sur un seul segment)*
- `build_complet.py` lance `check_plan.py` apres le preflight et s'arrete s'il est en FAIL : un plan en FAIL ne se pose plus. *(corpo-plaza lot 1 : check_plan 1038 chevauchements, lot REJETE)*

## Historique des consolidations
- 2026-10-27 : creation a partir de l'audit corpo-plaza.
