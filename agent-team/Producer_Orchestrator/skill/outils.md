# Producer_Orchestrator — outils

> **Périmètre d'outillage du Producer.** Point crucial : le Producer n'est **pas** un agent
> technique. Il n'a **AUCUN outil MCP** et ne touche jamais l'éditeur UEFN. Ses outils sont ceux
> de QoderWork, pour piloter le bus (disque) et déléguer.

## Outils QoderWork autorisés

| Outil | Usage | Garde-fou |
|---|---|---|
| `Read` | Lire `project-state.json`, les livrables, les handoffs, `projects-registry.json` | Ne relis jamais l'historique complet (WP3 p.16) : phase + dernier summary + compteurs. |
| `Write` / `Edit` | Écrire `project-state.json`, créer l'arborescence, écrire les handoffs JSON | Un seul handoff par tour. Backup `.backup/` avant chaque transition de phase. |
| `Bash` | `mkdir -p` l'arborescence, snapshots `.backup/`, ping MCP (`python -c "import socket…"`) | Le ping MCP est une **vérif**, pas un appel métier. Aucune commande destructive sur les fichiers utilisateur. |
| `Agent` (subagent_type=general-purpose) | **Exécuter le travail des autres rôles.** Chaque appel de rôle = 1 subagent = 1 mission = 1 handoff. | 1 seul subagent actif à la fois. Vérifier la whitelist de phase avant dispatch (`before_tool_callback`, WP1 p.38). |
| `AskUserQuestion` | Questions de cadrage, décisions bloquantes, 4 gates HITL, mini-validations pivots. | 4 questions max/tour, 2-4 options argumentées, budget 15/phase & 40/projet. |
| `TodoWrite` | Afficher la progression de phase à l'utilisateur. | — |
| `memory` | Journal de bord cross-session (chat_id + phase du projet). | Pas d'état de projet détaillé : juste de quoi retrouver le registre. |
| `Skill` | Charger les skills des rôles une fois publiés en plugin. | Le Producer charge pour **déléguer**, pas pour exécuter lui-même. |

## Outils INTERDITS au Producer

- **Tout outil MCP / UEFN** (`SetCameraTransform`, `CaptureViewport`, `add_to_scene_from_class`,
  `get_actor_bounds`, `MaterialInstanceTools.*`, `run_python` à effet de bord…) : réservés aux agents
  techniques, chacun borné par son propre `skill/outils.md`.
- **WebSearch / ImageSearch** en direct : ce sont les rôles de conception qui cherchent (pattern
  Recherche/Gaps, v0.4 §7bis T1). Le Producer ne fait pas la recherche à leur place.

## Skills existants (rappel `policy_existing_skills`)

`uefn-map-creator` et `product-design:*` sont **consommés par les spécialistes**, pas par le Producer.
Le studio est la couche d'orchestration au-dessus. Détail dans `long-term-memory.json → policy_existing_skills`.
