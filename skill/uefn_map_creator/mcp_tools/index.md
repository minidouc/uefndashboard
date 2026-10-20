# Inventaire des outils MCP

Liste des **388 outils** des **30 toolsets** exposes par l'editeur UEFN, releves le 2026-10-19
dans le niveau `MCP_TestLevel` (UEFN 42.40-CL-59247843). Un outil = `call_tool(toolset_name,
tool_name, arguments)`. Les noms ici sont des donnees relees, pas des hypotheses.

## Lire une fiche

Chaque outil tient sur une ligne :

- `**Nom**(arguments)` : les arguments obligatoires portent une `*`.
- la description officielle renvoyee par `describe_toolset`, en anglais ou en francais selon le
  toolset, recopiee sans reformulation (seuls les accents ont ete retires) ;
- `[classe | statut]` : classe `lecture`, `ecriture` ou `DANGEREUX` ; statut `verifie` (appele puis
  relu dans l'editeur), `echec` (appele et refuse, la ligne suivante donne l'erreur) ou `inconnu`
  (jamais appele, la ligne suivante donne le motif quand il est connu).

Repartition : 182 verifies, 11 en echec, 195 inconnus ; 191 lectures, 59 ecritures, 138 DANGEREUX.
**Les 138 DANGEREUX sont tous inconnus : ils n'ont jamais ete appeles, et ne doivent pas letre.**
Un statut `inconnu` ne veut pas dire « ne marche pas », mais « on ne sait pas » : ne le presente
jamais comme une limite du MCP sans l'avoir teste.

## Sous-dossiers

| Dossier | Contenu | Quand l'ouvrir |
| --- | --- | --- |
| `scene-acteur/` | 63 outils : SceneTools, ActorTools, EntityToolset, PrimitiveTools (51 verifies) | poser, chercher, deplacer, supprimer un acteur ; calques, dossiers de scene |
| `objet-proprietes/` | 13 outils : ObjectTools, VerseFieldsToolset (6 verifies) | lire ou ecrire une propriete d'un acteur ou d'un objet |
| `devices/` | 9 outils : DeviceToolset (6 verifies) | cataloguer, poser, cabler un device |
| `verse/` | 10 outils : VerseToolset (4 verifies, 6 DANGEREUX) | lire, ecrire, compiler du Verse |
| `editor-session/` | 53 outils : EditorAppToolset, LogsToolset, SessionToolset, ProgrammaticToolset, ValkyriePythonToolset (37 verifies) | CVar, camera, capture, logs, etat de session, scripts en lot |
| `assets-ressources/` | 136 outils : AssetTools, meshes, textures, materiaux, tables, PhysicsAsset (40 verifies, 70 DANGEREUX, 1 seule ecriture) | mesurer ou inspecter un asset en lecture ; ne pas ecrire un asset |
| `effets-ui/` | 104 outils : Niagara, UMG, WidgetAnimation, MVVM, GameplayTags (38 verifies, 47 DANGEREUX) | hors perimetre du constructeur : deux outils sur trois y sont inconnus |
| `perso/` | vide : outils hors des 388 officiels | voir plus bas |

Point d'entree chiffres : [sommaire.md](sommaire.md) (un tableau par toolset avec les compteurs).

## Chercher sans ouvrir tout le dossier

32 fichiers markdown, plus de 80 ko de texte : ne charge jamais le dossier entierement, filtre.

```bash
grep -rn "PlaceDevice" mcp_tools/                     # un outil precis
grep -rn "DANGEREUX" mcp_tools/scene-acteur/          # ce qu'il ne faut pas appeler
grep -rn "\[lecture | verifie\]" mcp_tools/devices/   # lectures sures d'une famille
grep -rn "motif : Exige un creative_device" mcp_tools/  # ce qui bloque encore
```

## Actualiser la liste

La liste est un instantane d'une version de l'editeur. Apres une mise a jour d'UEFN, ou si un outil
annonce ici manque :

1. `list_toolsets`, puis `describe_toolset` pour chaque toolset, un appel a la fois, et ecrire chaque
   reponse dans `inventory/<nom_complet>.json` ;
2. enregistrer le statut de chaque outil appele dans un `capabilities.json` de meme forme ;
3. `python script/build_tools_index.py --inventory DIR --capabilities FICHIER --out mcp_tools`.

Le generateur recopie les donnees et ne decide rien : toute phrase d'interpretation reste dans les
`references/`, pas ici.

## `perso/` : outils personnalises

Dossier volontairement vide. Il accueilera une fiche par outil qui n'est pas dans les 388 officiels,
c'est-a-dire :

- un toolset maison expose par l'editeur (a declarer d'abord par `list_toolsets`, sinon il nexiste
  pas pour le MCP) ;
- un raccourci ajoute a `script/uefn_spatial_cli.py` pour une operation repatee.

Une fiche `perso/<nom>.md` doit porter : la signature reelle, ce quelle ecrit dans le niveau, les
outils officiels quelle appelle, et son propre statut `verifie` / `echec` / `inconnu` avec la preuve
de relecture. Ne pas y consigner un outil qui n'a pas ete relance depuis sa derniere modification.
