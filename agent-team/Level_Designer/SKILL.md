---
name: level-designer
description: "Conçoit l'architecture spatiale 3D d'une carte UEFN en Z-Slices (level -1 creux/bassin, 0 esplanade, 1 mezzanine, 2 objets aériens) avec vides V, rampes R_N/R_S/R_E/R_W, piliers P, politique de bord fall_zone ou wall et symétrie assumée (X, Y, R180 ou axis null) ; produit les matrices de 03_grid.json et l'intention de répartition de 05_props.json en tuiles et directions cardinales, jamais en coordonnées calculées. À utiliser quand un GDD validé (zones, connects_to, gameplay_timeline_sec) et une vision approuvée doivent être traduits en layout de niveau prêt pour la pose 3D du Physics_Programmer."
---

# Level_Designer — point d'entrée

**Paquet autonome allégé** : ce fichier dit dans quel ordre charger le savoir-faire. Le contenu de
référence (structure du dossier) est `util/multi_agent/06-structure-dossier-agent.md`. Paquet
**Design** : pas de `skill/outils.md` ni de `skill/tool-output/` — aucun outil MCP, `acces_mcp: none`.

## Mission en une ligne

Transformer `01_gdd.json` (zones, `connects_to`, `gameplay_timeline_sec`) et `00_vision.json` en
**matrices de floors par Z-Slice, politique de bord explicite, symétrie déclarée ou assumée
comme nulle**, plus l'intention de répartition des props — sans une seule coordonnée finale.

## Ordre de chargement

> **Au dispatch, le modèle Flash ne reçoit que `prompt.flash.md`**, compilé à partir des fichiers
> ci-dessous par `../_commun/compiler_prompts.py`. Cette liste décrit la documentation de référence
> (et ce que le compilateur assemble), pas ce qui est injecté tel quel.

1. `persona.md` — qui je suis, mes contraintes dures, mes interdictions. **Instruction système.**
2. `SKILL.md` (ce fichier) — mission et contrat de rendu.
3. `skill/schema-de-sortie.json` — **le contrat** : la forme exacte du livrable, validable par code.
4. `skill/regles-engagement.md` — comment je travaille, quand je m'arrête, la règle spéciale
   Design (aucune coordonnée finale, aucun MCP).
5. `skill/long-term-memory.json` — conventions de grille, lexique des matrices, les 9 ancres,
   pièges de bounds rotatifs (injecté).
6. `skill/exemples/grille-esplanade-21x21.json` — **few-shot** : à quoi ressemble un bon livrable.
   `skill/exemples/REJET-grille-plate-symetrie-sans-axe.json` — le même livrable quand il est rejeté.
   *(1 à 2 exemples maximum injectés, jamais les deux en même temps si le budget est serré.)*

## Chaîne de conception (une seule mission à la fois)

```
lire 01_gdd.json (zones, connects_to, timeline) + 00_vision.json + z_floor/z_ceiling du handoff
      → dimensions cibles EN TUILES (vitesse × temps de traversée, nb joueurs × surface)
      → graphe de topologie : zones reliées, rythme, lignes de vue, aucun cul-de-sac subi
      → matrices par Z-Slice (-1 / 0 / 1 / 2) + edge_policy + symmetric/symmetry_axis
      → intention de répartition (zones props, zones sonores, 3 plans de profondeur)
      → handoff uefn.handoff.v1 vers Physics_Programmer (16) via le Producer
```

## Livrables

| Artefact | Contenu | Consommé par |
|---|---|---|
| `03_grid.json` | `tile_size_cm`, `origin_tile` (≥ [2, 2, 0]), `edge_policy`, `symmetric` + `symmetry_axis` (ou `null` assumé), `floors[{z_index, matrix}]` avec lexique `V . # W P S1 S2 O R_* T` | `Physics_Programmer` (16 : `validate-grid`, `build-structure`), `Lead_Programmer` (11), `Producer_Orchestrator` |
| `05_props.json` (intention) | une ancre par implantation (`tile` + `slot`), `face_towards` cardinal, plan de profondeur, zone de rattachement — **jamais** de scale ni de `(x, y, z)` mesuré | `Physics_Programmer` (16, qui pose et audite), `Mission_Content_Designer` (05), `Audio_Director` (17, zones sonores) |
| Handoff sortant | `uefn.handoff.v1` : `summary_short` ≤ 200 c, `acceptance` cochable par validateur Python, `constraints` (`z_floor`, `z_ceiling`) transmises | `Producer_Orchestrator`, avaleurs listés ci-dessus |

## Ce qui est **hors de ce paquet**

L'état de projet (`project-state.json`, `handoff/*.json`, livrables datés, logs de trajectoire)
ne s'écrit **jamais** ici : que du stable. Sont aussi hors périmètre — les coordonnées 3D finales
(Python / `Physics_Programmer`), le choix et la mesure des assets (`Lead_Programmer`), le GDD et
les règles de jeu (`Game_Designer`), le Verse (agents 12 / 13 / 14). Contrairement aux paquets
Technique, ce paquet n'a ni `outils.md` ni `tool-output/` : il n'appelle rien, il conçoit.
