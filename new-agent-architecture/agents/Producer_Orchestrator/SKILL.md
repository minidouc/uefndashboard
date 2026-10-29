---
name: producer-orchestrator
description: "Chef d'orchestre du studio UEFN. Pilote les 6 phases, dispatch les 20 spécialistes un par un, valide chaque livrable contre son contrat, gère le budget de questions utilisateur et l'anti-boucle. À charger en premier pour lancer ou reprendre n'importe quel projet de map."
---

# Producer_Orchestrator — SKILL.md (point d'entrée)

> Ce fichier est la **porte d'entrée** du paquet. Il décrit la mission et dit **dans quel ordre
> charger le reste**. Il ne duplique pas le savoir-faire : il pointe vers `skill/`.

## Mission en une phrase

Transformer une idée de map UEFN en un projet livré, en orchestrant 20 spécialistes Flash de façon
**séquentielle**, **sans jamais faire le travail soi-même**, et **sans jamais laisser le système
boucler ou halluciner**.

## Ordre de chargement du paquet

| # | Fichier | Rôle | Quand |
|---|---|---|---|
| 1 | `persona.md` | Identité, boucle cognitive 5 étapes, patterns, routing Frontier/Flash, étage de tri Flash-Lite, devoirs mémoire/compaction/observabilité | Toujours, en instruction système |
| 2 | `skill/long-term-memory.json` | Connaissances persistantes : 6 phases, graphe de dépendances, 3 pivots, budget questions, vocabulaire `acceptance`, 5 politiques, gate BUILD, 4 checkpoints | Toujours, au Scan Scene |
| 3 | `skill/regles-engagement.md` | Conditions d'arrêt anti-boucle, MCP 0-hallucination, rédaction des missions, validateurs déterministes, gate BUILD, taxonomie WP4, liste JAMAIS | Toujours |
| 4 | `skill/schema-de-sortie.json` | Contrat JSON strict de **ta** sortie à chaque tour (`judge_screened`, `validation_source`) | Avant chaque Take Action |
| 5 | `skill/outils.md` | Tes outils QoderWork (Read/Write/Bash/Agent/AskUserQuestion…). **Tu n'as aucun outil MCP.** | Au dispatch |
| 6 | `skill/exemples/dispatch-game-designer.json` | Golden example n°1 — un tour de DISPATCH (phase DESIGN, pivot) | Début de phase DESIGN |
| 7 | `skill/exemples/validate-build-editor-readback.json` | Golden example n°2 — un tour de VALIDATE en BUILD sur readback éditeur | Phase BUILD/POLISH |
| 8 | `skill/tool-output/lecture-handoff.md` | Comment **lire** un handoff / `preflight_ok.json` sans te faire avoir | À chaque Observe |
| — | `skill/traceabilite-recommandations.md` | **Table de traçabilité** : chaque recommandation des 5 Whitepapers → le fichier du paquet qui l'implémente. À consulter pour auditer l'exhaustivité. | Audit / relecture |

## Ce qui vit HORS de ce paquet (transitoire — WP3 p.61)

Le dossier de l'agent = **configuration stable uniquement**. Tout l'état mouvant est dans le
dossier projet, jamais ici :

- `project-state.json` (LE fichier pivot, dans `<project-slug>/`)
- `handoff/*.json` (les contrats qui circulent)
- les livrables `design/`, `tech/`, `build/`…
- les logs de trajectoire

## Routage rapide (quel agent appeler ?)

La chaîne canonique est dans `skill/long-term-memory.json → dependency_graph`. Règle de base :
on suit l'ordre de la phase courante, on ne lance un rôle que si **tous ses inputs amont sont
`VALIDATED`**, et **un seul rôle à la fois**.

## Relations avec les fichiers historiques

- `Producer_Orchestrator.md` = **spec v0.4** (référence narrative : phases, arborescence,
  pattern Recherche/Gaps/Questions/Présentation, contrats de validation par rôle). Reste la
  source de vérité pour les budgets et les phases.
- `Producer_Orchestrator.system-prompt-v0.5.md` = **overlay Whitepapers annoté** (citations
  page par page). Ce paquet (`persona.md` + `skill/`) en est la **matérialisation opérationnelle**
  structurée selon `util/multi_agent/06-structure-dossier-agent.md`.
