# Producer_Orchestrator — traçabilité des recommandations

> **Épine dorsale du paquet.** Ce fichier liste **toutes** les recommandations des 5 White Papers
> Google + des docs `util/multi_agent/` qui concernent l'orchestrator, et **où** chacune est
> implémentée dans le paquet. Objectif : prouver qu'aucune n'a été oubliée, et permettre une
> re-vérification ligne à ligne.
>
> Légende des statuts : `✅` implémenté · `🔒` garde-fou déterministe (code, pas prompt) ·
> `[AM]` = adaptation maison (aucun équivalent littéral dans les WP).
>
> Fichiers du paquet : `persona.md` (P) · `SKILL.md` (S) · `skill/regles-engagement.md` (RE) ·
> `skill/long-term-memory.json` (LTM) · `skill/schema-de-sortie.json` (SCHEMA) ·
> `skill/outils.md` (OUT) · `skill/exemples/*` (EX) · `skill/tool-output/lecture-handoff.md` (TOOL).

---

## A · Cerveau du Chef — planification & routage (WP1)

| Réf | Recommandation | Implémentée dans | Statut |
|---|---|---|---|
| WP1 p.11-12 | Boucle 5 étapes : Get Mission → Scan Scene → Think → Act → Observe | P §3 ; SCHEMA `loop_step` | ✅ |
| WP1 p.12 | La boucle tourne jusqu'à plan complet / mission accomplie | RE §2 (condition d'arrêt n°1) | ✅ |
| WP1 p.9 | Raisonnement Chain-of-Thought / ReAct pour découper les objectifs | P §4 (décision studio : Orchestrator-Workers, pas ReAct brut) | ✅ `[AM]` |
| WP1 p.17 | Le chef ne fait pas le travail, il crée des Missions | P §1 ; OUT (`Agent`) ; RE §5 | ✅ |
| WP1 p.19-20 | Routage Frontier (planification) ↔ Flash (tâches volumineuses) | P §5 ; LTM (implicite phases) | ✅ |
| WP1 p.25 | Patterns Sequential (« assembly line ») + Coordinator/Orchestrator-Workers | P §4 ; LTM `dependency_graph` | ✅ |
| WP1 p.25 | Generator-Critic | P §4 ; RE §4 (restreint aux 3 pivots) ; LTM `pivot_roles` | ✅ `[AM: restreint]` |
| WP1 p.26 | Human-in-the-Loop (« deliberate pause to get approval ») | P §4 ; RE §3 ; SCHEMA `user_question.gate` | ✅ |
| WP1 p.35 | Garde-fous déterministes = « security chokepoint outside the model's reasoning » | RE §2 intro ; LTM `iteration_caps.comment` | 🔒 |
| WP1 p.38 | `before_tool_callback` : inspecter les paramètres avant exécution | RE §3 (allowlist avant dispatch) ; P §3 | 🔒 |
| WP1 p.38 | « Gemini as a Judge » / Flash-Lite : écran bon marché des sorties avant le Frontier | P §5bis ; RE §4bis ; SCHEMA `judge_screened` | ✅ |
| WP1 p.23-24 | Recette instruction système : persona, contraintes, schéma de sortie, règles d'engagement, ton, quand/pourquoi les outils, exemples | P (persona+contraintes+ton) ; SCHEMA (schéma sortie) ; RE (règles) ; OUT (outils) ; EX (exemples) | ✅ |
| WP1 p.25 | Division du travail → agents plus simples, testables | RE §5 (JAMAIS faire le travail des spécialistes) | ✅ |
| WP1 p.48 | Supervisor hiérarchique (Co-Scientist) — mais UN seul niveau | P §1 (hub unique) ; LTM (pas de sous-managers) | ✅ `[AM: 1 niveau]` |
| *(aucun WP)* | **Cap d'itérations anti-boucle** (les WP ne donnent AUCUN compteur) | RE §2 ; LTM `iteration_caps.per_phase_hard_stop=15` ; SCHEMA `iterations_this_phase max 15` | 🔒 `[AM]` |
| *(aucun WP)* | Interdits : Tree-of-Thoughts, Self-Consistency multiple | P §4 ; RE §1 | ✅ `[AM]` |

## B · Contexte, handoff & mémoire (WP3)

| Réf | Recommandation | Implémentée dans | Statut |
|---|---|---|---|
| WP3 p.8 | Payload = System Instructions / Tool Defs / Few-Shot / LTM / External Knowledge / Tool Outputs / Sub-Agent Outputs | S (ordre de chargement) ; mapping complet | ✅ |
| WP3 p.8 | « no more and no less than the most relevant information » | P §3 (Scan Scene minimal) ; RE §1 | ✅ |
| WP3 p.9 | Context rot : l'attention chute quand le contexte grossit | P §3 ; RE §3 ; EX (1 seul golden example) | ✅ |
| WP3 p.12 | Events (append-only) vs State (mutable) — séparer | RE §7 ; LTM `policy_cross_session.stateless_entre_tours` ; project-state.json `history[]` = events, reste = state | ✅ |
| WP3 p.16 | History ≠ context (ne pas repasser le transcript) | P §3 (Scan Scene) ; RE §3 ; TOOL §1 | ✅ |
| WP3 p.17 | `output_key` : le sub-agent écrit son résultat dans une clé d'état, pas dans le fil | RE §7 ; handoff = clé d'état ; project-state `roles.<X>.last_output` | ✅ |
| WP3 p.18 | Black box : « shares its final output, not its process » | RE §3 ; TOOL §1 ; EX (payload atomique) | ✅ |
| WP3 p.22 | Réduire la taille transférée, filtrer/compacter, purger vieux outputs d'outils | RE §8 (compaction) ; TOOL §3 | ✅ |
| WP3 p.23-24 | Compaction : sliding window / token-truncation (~4000) / recursive summarization | RE §8 ; LTM `context_budget_tokens=4000` ; SCHEMA (handoff ≤4000) | ✅ `[AM: 4000 dur]` |
| WP3 p.34/45/46 | Formats structurés : dictionary/JSON, schema-based extraction, few-shot, faits atomiques | SCHEMA (JSON strict) ; EX ; RE §4 | ✅ |
| WP3 p.38 | Offloading vers mémoire externe ; passer un nom de fichier, pas le contenu | RE §8 ; TOOL §3 | ✅ |
| WP3 p.61 | Stable (prompt système) vs transitoire (dialogue/fichier) | S (frontière stable/transitoire) ; P intro | ✅ |
| *(04-contrat)* | Schéma `uefn.handoff.v1` (synthèse maison) | EX `B_handoff_written` ; TOOL §1 ; LTM | ✅ `[AM]` |

## C · Outils, MCP & sécurité (WP2)

| Réf | Recommandation | Implémentée dans | Statut |
|---|---|---|---|
| WP2 p.9 | Maths externalisées : jamais de calcul de coordonnées par le LLM | RE §3 ; TOOL §4 ; OUT (Producer = aucun MCP) | 🔒 |
| WP2 p.10 | Le schéma est le contrat (name, params, description) | RE §3 (double schéma) | ✅ |
| WP2 p.15-18 | Noms clairs, params courts, défauts documentés, exemples | RE §3bis (rédaction des missions) | ✅ |
| WP2 p.17 | Ne pas dupliquer la doc outil, ne pas dicter le workflow, expliquer les effets de bord | RE §3bis (`next_step_hint`) | ✅ |
| WP2 p.18 | Publier des tâches, pas des API (`place_prop_from_grid`, pas `place_actor(x,y,z)`) | RE §3 ; TOOL §4 ; EX | ✅ |
| WP2 p.19 | Passer un nom de table/fichier plutôt que le contenu | RE §8 ; TOOL §3 | ✅ |
| WP2 p.19-20 | Erreurs descriptives qui instruisent le modèle suivant | RE §3 ; TOOL §3 | ✅ |
| WP2 p.26/29 | inputSchema + outputSchema, le CLIENT valide les résultats | RE §3 ; TOOL §1/§3 | 🔒 |
| WP2 p.27 | Ne pas faire confiance aux hints serveur (`destructiveHint`) | RE §3 ; TOOL §2 | ✅ |
| WP2 p.29-30 | `isError:true` + cooldown (« Wait 15 seconds ») | RE §3 ; TOOL §3 | ✅ `[AM: cooldown généralisé]` |
| WP2 p.36/43 | HITL : approbation explicite, high-risk = sensitive sinks | RE §3 ; P §4 ; SCHEMA `user_question.gate=ecriture_destructrice_uefn` | ✅ |
| WP2 p.41 | Allowlist explicite + Tool/Package Pinning + `listChanged` revalidation | RE §3 ; OUT (rappel mcp-inventory) | 🔒 |
| WP2 p.42 | Tool Shadowing : vérifier les collisions de noms d'outils | RE §3 (allowlist) ; OUT | ✅ |
| WP2 p.43 | Deterministic Policy Enforcement — **4 points** : before discovery / before invocation / before data returned / before outbound call | RE §3bis (les 4 checkpoints) | 🔒 |
| WP2 p.44 | Input Validation + Output Sanitization | RE §3 ; TOOL §3 | ✅ |
| WP2 p.45 | Sanitizer les descriptions d'outils avant injection ; ressources 3P via URLs allowlistées + consentement | RE §3bis ; OUT | ✅ |
| WP2 p.47 | Least privilege ; secrets hors contexte ; credentials courte durée | RE §3 ; OUT ; P §7 | ✅ |
| WP2 p.47 | Pas de support natif de limitation de portée → imposer côté client | RE §3 (périmètre dans `next_step_hint`) | ✅ |

## D · Qualité & débogage (WP4)

| Réf | Recommandation | Implémentée dans | Statut |
|---|---|---|---|
| WP4 p.20 | Taxonomie d'échecs en 6 axes (planning, tool usage, tool response, RAG, trajectory, multi-agent) | RE §9 (grille) ; TOOL §3/§5 | ✅ |
| WP4 p.20 n°3 | Ne pas « faire comme si » un call avait réussi quand il y a erreur | RE §3 ; TOOL §2/§3 | 🔒 |
| WP4 p.20 n°1/6 | Repetitive output loops + communication loops → couper | RE §2 (payload identique = HALT) ; P §1 (hub unique) | 🔒 |
| WP4 p.20 | Ne jamais demander à un modèle de s'auto-valider | RE §4 ; TOOL §1 | 🔒 |
| WP4 p.21 | Black Box → Glass Box (« wrong because… ») via la trace | RE §9 ; outil 04 (handoff commité = log de trajectoire) | ✅ |
| WP4 p.20 | Validateurs déterministes (couche CODE) : schema_valid, 0_overlap, 0_floating, spawn_reachable, mcp_ok, pid_legal | RE §4bis (table) ; LTM `acceptance_vocabulary` ; TOOL §5 | 🔒 |

## E · Production & opérations (WP5)

| Réf | Recommandation | Implémentée dans | Statut |
|---|---|---|---|
| WP5 p.14 | Sign-off humain avant mise en prod | RE §3 ; SCHEMA `user_question.gate` | ✅ |
| WP5 p.18 | HITL Escalation | RE §2/§3 ; LTM `policy_escalation` | ✅ |
| WP5 p.19-20 | Boucle ops Observe → Act → Evolve ; journaliser chaque handoff + appel MCP + résultat | RE §10 (observabilité) ; TOOL ; outil 04 (commit) | ✅ |

## F · Architecture studio (docs `01` — 6 couches) `[AM]`

| Couche | Recommandation | Implémentée dans | Statut |
|---|---|---|---|
| 1 Topologie | Hub-and-spoke, UN seul supervisor, pas de mesh ; séquentiel pas parallèle (16 Go) | P §1/§4 ; RE §1 ; LTM `dependency_graph` | ✅ |
| 2 Comm & état | Disque comme bus ; state mutable vs events append-only ; orchestrateur quasi-stateless entre tours ; contexte lourd offloadé sur disque | RE §7 ; LTM `policy_cross_session` ; TOOL | ✅ |
| 3 Outils | Gateway MCP unique, task-level, maths externalisées, double schéma, allowlist | RE §3 ; OUT | 🔒 |
| 4 Modèles | Frontier = Producer ; Flash = les 20 ; étage Flash-Lite « as a Judge » | P §5/§5bis ; SCHEMA `judge_screened` | ✅ |
| 5 Contrôle | Anti-boucle = CODE ; before_tool_callback ; validateurs Python ; Generator-Critic sur 3 pivots ; 4 gates HITL | RE §2/§3/§4/§4bis ; LTM `iteration_caps`/`policy_escalation` | 🔒 |
| 6 Observabilité | Loguer handoff + MCP + résultat (version jam allégée) | RE §10 ; TOOL ; projet `handoff/` commité | ✅ |
| *(05 §3)* | Clamp déterministe Python des X/Y/Z aux Z-slices avant écriture | RE §3 ; missions techniques | 🔒 |
| *(crucial studio)* | **Gate BUILD : le Producer ne VALIDE un livrable de phase BUILD que sur readback éditeur (get_actor_bounds + CaptureViewport + validateur Python), jamais sur l'auto-déclaration du Flash** | RE §4ter ; SCHEMA `validation_source` ; TOOL §4 | 🔒 `[AM]` |

---

## Synthèse — les 5 questions « à creuser » de la spec v0.4

Toutes résolues dans `long-term-memory.json` : `policy_folder_creation`, `policy_dispatch_granularity`,
`policy_cross_session`, `policy_escalation`, `policy_existing_skills`.

## Ce qui n'est PAS dans les WP (honnêteté — `[AM]`)

Cap 15 itérations/phase · budget 4000 tokens dur · cooldown 15 s généralisé · interdiction
Tree-of-Thoughts · restriction du Generator-Critic aux 3 pivots · schéma `uefn.handoff.v1` ·
registre multi-projets · gate BUILD sur readback éditeur. Tous marqués `[AM]` dans les tableaux
ci-dessus et dans `02-principes-whitepaper.md §Q4`.
