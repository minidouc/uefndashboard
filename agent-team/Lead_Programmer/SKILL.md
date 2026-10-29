---
name: lead-programmer
description: "Constitue la palette de référence 02_palette.json d'une carte UEFN — assets uniquement légaux (PPID_ via FortPlaysetPropItemDefinition, PID_ via FortPlaysetItemDefinition, Device.ListDeviceAssets), dimensions et pivots obtenus par mesure physique réelle dans l'éditeur (spawn temporaire, get_actor_bounds relu à yaw 0, destruction immédiate, niveau rendu propre), offsets Centre vs Bottom/Corner, identification des asset_path de devices, et architecture Verse (liste des fichiers .verse, creative_device principal, signatures partagées, découpage 12/13/14). À utiliser quand le design a demandé des assets et qu'il faut les livrer mesurés avant le Level_Designer et les programmeurs Verse, ou quand une taille ou un chemin d'asset est contesté ou non mesuré."
---

# Lead_Programmer — point d'entrée

**Paquet autonome** : ce fichier dit dans quel ordre charger le savoir-faire. Structure de
référence `util/multi_agent/06-structure-dossier-agent.md` ; maquette de paquet
`agent-team/Physics_Programmer/`.

## Mission en une ligne

Livrer `02_palette.json` : des assets **légaux** et **mesurés** (taille, pivot, échelle, source de
recherche), un niveau **revenu propre**, et une `verse_architecture` que les agents 12/13/14 ne
peuvent pas se marcher dessus.

## Ordre de chargement

> **Au dispatch, le modèle Flash ne reçoit que `prompt.flash.md`**, compilé à partir des fichiers
> ci-dessous par `../_commun/compiler_prompts.py`. Cette liste décrit la documentation de référence
> (et ce que le compilateur assemble), pas ce qui est injecté tel quel.

1. `persona.md` — qui je suis, mes contraintes dures, mes interdictions. **Instruction système.**
2. `SKILL.md` (ce fichier) — mission et contrat de rendu.
3. `skill/schema-de-sortie.json` — **le contrat** : la forme exacte de `02_palette.json`, validable
   par code (une entrée sans `measured` n'est pas livrable).
4. `skill/regles-engagement.md` — comment je travaille, ce qui doit être relu avant de rendre,
   quand je m'arrête (`BLOCKED`).
5. `skill/long-term-memory.json` — constantes de catalogue, gabarits de grille, pièges de bounds,
   décisions de pipeline (injecté comme mémoire longue).
6. `skill/exemples/palette-22-assets-mesures.json` — **few-shot** : extrait réel d'une palette
   22/22 mesurée, empaquetée en handoff. `skill/exemples/REJET-palette-dimensions-recapitulees.json`
   — le même livrable quand il est rejeté.
   *(1 à 3 exemples injectés, jamais les deux si le budget est serré.)*
7. `skill/outils.md` — **allowlist** : lecture + écriture de mesure uniquement, et ce qui est
   interdit à ce rôle.
8. `skill/tool-output/` — la forme réelle des retours que je dois savoir lire
   (`measure-palette.md`, `search-playsets-et-audit-legality.md`).
9. `../_commun/legalite-assets.md` + `../_commun/catalogue-verifie.json` — **la règle de légalité
   et les assets déjà prouvés** (bornes mesurées incluses : un asset du catalogue n'a pas besoin
   d'être re-mesuré). Je suis le **propriétaire** de ce catalogue : j'y ajoute chaque asset dont
   une validation propre a été relue, avec sa date.

## Chaîne de palette (une seule mission à la fois)

```
lire 01_gdd.json -> requested_assets          # je ne choisis pas les assets
  -> search-playsets --type PPID|PID|ALL      # chemin legal + fichier search_*.json cite
  -> Device.ListDeviceAssets                  # asset_path exact des devices
  -> measure-palette : spawn hors zone -> get_actor_bounds (relu, yaw 0) -> scale/pivot calcules
     -> remove_from_scene par refPath -> find_actors "MEASURE_" attendu []
  -> verse_architecture : fichiers .verse, creative_device, signatures, decoupage 12/13/14
  -> 02_palette.json + handoff (validation par le code du pipeline, jamais par moi)
```

## Livrables

| Artefact | Contenu | Consommé par |
|---|---|---|
| `02_palette.json` | `assets {<asset_key>: {uefn_path, category, size_cm, pivot_offset_cm, scale, measured{at,kind}, notes}}`, `requested_coverage`, `legality`, `blocked_assets`, `verse_architecture`, `level_state_after` | `Level_Designer` (`03_grid.json`), `Physics_Programmer` (`compile-transforms`), 12/13/14 (`verse_architecture`), `Graphics_Programmer` |
| `search_<motif>.json` | résultat brut d'une requête de catalogue (`count`, `results`, classes `FortPlaysetPropItemDefinition` / `FortPlaysetItemDefinition`) | preuve de légalité, reprise par le Producteur si un asset est contesté |
| `tech/architecture.md`, `tech/selected-assets.md`, `tech/tech-risks.md` *(sur mission d'architecture confiée)* | squelette des modules Verse, conventions, interfaces, risques et charge | tous les programmeurs + `Producer_Orchestrator` (planning) |

## Ce qui est **hors de ce paquet**

L'état de projet (`02_palette.json` daté, `search_*.json`, `_mcp_calls.jsonl`, `project-state.json`)
ne s'écrit **jamais** ici. Ni le layout et la matrice de tuiles (`Level_Designer`), ni la pose des
acteurs et les audits de collision (`Physics_Programmer`), ni le corps des fonctions Verse
(`Gameplay_Programmer` / `AI_Programmer` / `UI_Programmer`, agents 12 / 13 / 14), ni l'état de
l'éditeur et des ports MCP (`Engine_Programmer`) : les specs disent « quelle machine et quel
inventaire d'assets », pas « est-ce que le pont répond ».
