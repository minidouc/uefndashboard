# Rubrique visuelle generique (utilisee par le sous-agent `critique`)

Methode LLM-as-a-Judge (WP4 p.23-24) : rubrique explicite, constats factuels, comparaison par
paires des que deux versions existent.

Elle fonctionne pour **tout type de map**. Le style propre a un projet vient de son fichier
`<projet>/design/rubrique-da.md`, ecrit par le `directeur-creatif` a partir du brief : palette,
ambiance, motifs, interdits IP. Le critique lit les deux.

Note de 0 a 3 par critere :
- **0** : absent ;
- **1** : faible ;
- **2** : conforme ;
- **3** : remarquable.

## Criteres communs a toutes les maps
| # | Critere | Ce qu'on doit VOIR | Bloquant si < |
|---|---|---|---|
| 1 | Lisibilite de la capture | la camera montre la zone de son `intention`, pas un mur ou le vide | 2 |
| 2 | Lisibilite du jeu | on comprend ou aller : chemins, objectifs, spawns, couverts selon le type | 2 |
| 3 | Echelle | proportions coherentes avec un joueur (portes, marches, garde-corps) | 1 |
| 4 | Finition | autre chose que le damier par defaut ; la dette `degrade` est visible | 1 a partir de POLISH |
| 5 | DA du projet | chaque critere de `rubrique-da.md` est verifie un par un | selon `rubrique-da.md` |
| 6 | IP | aucun logo ni marque deposee non autorises | 3 (sinon FAIL) |

## Verdicts
- **PASS** : aucun critere bloquant sous son seuil.
- **FAIL** : au moins un critere bloquant sous son seuil. Donner LA correction la plus utile.
- **INCERTAIN** : l'image ne permet pas de juger. Demander une autre camera, ne pas deviner.

## Comparaison par paires (prioritaire)
« Laquelle des deux captures prouve le mieux l'intention ? » La reponse est A, B ou egalite, avec
les criteres qui departagent (WP4 p.24).

## Modele de `rubrique-da.md` (a remplir par le directeur creatif)
```markdown
| Critere DA | Ce qu'on doit voir | Bloquant si < | Mesurable ? (cle visuel.captures) |
|---|---|---|---|
| Ambiance | ex. nuit froide / plein soleil / brume | 2 | luminance_max / luminance_min |
| Palette  | ex. #22E6FF + #FF2BD6 en accents | 1 | couleurs_min |
```
Tout ce qui est mesurable va AUSSI dans la config du projet (`visuel.captures`). C'est alors
verifie gratuitement par le code, avant meme le critique.
