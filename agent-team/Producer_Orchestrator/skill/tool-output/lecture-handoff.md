# Producer_Orchestrator — lecture des retours (tool-output)

> Le Producer n'appelle **jamais** MCP. Mais il **lit** ce que les agents techniques lui
> renvoient via leurs handoffs, et il doit savoir reconnaître un retour sain d'un retour
> empoisonné. Ce fichier est le mode d'emploi de cette lecture (composant « Tool Outputs »,
> WP3 p.8). Règle d'or : **sur UEFN, la vérité vient de l'éditeur, jamais du modèle.**

---

## 1. Lire un handoff de retour (`uefn.handoff.v1`)

À chaque `Observe & Iterate`, tu lis le handoff écrit par le rôle destinataire. Ordre :

1. **`summary_short` d'abord** — c'est le seul champ que tu lis mot à mot (< 200 c).
2. **`acceptance[]`** — tu coches chaque case de façon **déterministe** (schéma + validateur),
   jamais en demandant au Flash de s'auto-valider (WP4 p.20).
3. **`payload`** — vérifié par schéma, pas par lecture intégrale (économie de contexte).
4. Tu ne lis **jamais** le transcript de l'agent : black box, output only (WP3 p.18).

Si une case `acceptance` n'est pas cochable ou manque → `REJECT` avec `rejection_reason`, `attempt++`.

## 2. Lire un `preflight_ok.json` (retour `Engine_Programmer`)

Avant toute phase BUILD/POLISH qui écrit dans l'éditeur, `Engine_Programmer` doit produire un
`preflight_ok.json` frais. Tu vérifies :

| Champ | Attendu | Si absent / faux |
|---|---|---|
| `mcp_ping` | `"OK"` (socket 127.0.0.1:8000/8001 répond) | Statut `UNKNOWN`, escalade : « plugin MCP non démarré dans UnrealEditorFortnite ». |
| `editor_pid` | PID du process `UnrealEditorFortnite-Win64` vivant | Escalade : éditeur fermé. |
| `tools_available[]` | liste d'outils réellement présents | Croise avec `tech/mcp-inventory.json`. Outil attendu absent = `UNKNOWN_TOOL_BLOCKED`. |
| `generated_at` | timestamp récent (< ce tour) | Un preflight périmé n'est pas un preflight. Tu en redemandes un. |

**Règle absolue** : un `preflight_ok.json` manquant, vide, ou non-JSON parsable = `UNKNOWN`,
**pas** `SUCCESS`. Tu ne lances AUCUNE écriture dans l'éditeur sur cette base (WP4 p.20 n°3 :
les modèles « ne reconnaissent pas un état d'erreur et continuent comme si le call avait réussi »).

## 3. Reconnaître un retour MCP empoisonné (lu via le handoff technique)

Quand un agent technique te remonte le résultat brut d'un appel MCP, tu le traites comme **échec** si :

- `isError: true` présent (WP2 p.30) ;
- code JSON-RPC/HTTP ∈ {4xx, 5xx, `-32601 Unknown tool`} ;
- payload vide, tronqué, ou non-JSON ;
- message de type « Wait 15 seconds » → cooldown à appliquer, pas de retry immédiat.

Dans tous ces cas : **tu n'itères pas**. `UNKNOWN` dans le state + escalade ou re-demande de preflight.

## 4. Lire un retour géométrique (`get_actor_bounds`, batch Python)

C'est ta seule source de vérité spatiale. Tu ne calcules **jamais** une coordonnée toi-même (WP2 p.9).
Tu vérifies que les valeurs proviennent bien :

1. d'un `get_actor_bounds` lu dans l'éditeur, OU
2. d'un batch Python déterministe (qui lit `03_grid.json` / `placement-plan.json` et retourne les transforms).

Un livrable technique qui contient des positions « au pif » sans provenance = `REJECT` immédiat.
La validation finale d'un build passe par la boucle **save → `get_actor_bounds` → `CaptureViewport`
→ validateur Python**, jamais par l'avis du modèle.

## 5. Ce que tu fais du retour, concrètement

| Retour | Décision schema-de-sortie | Écritures state |
|---|---|---|
| Sain + acceptance complète | `VALIDATE` | `roles.<X>.status=VALIDATED`, `artifacts_index` mis à jour |
| Sain mais acceptance incomplète | `REJECT` | `attempt++`, `rejection_reason`, retour `IN_PROGRESS` |
| `isError` / UNKNOWN / vide | `ESCALATE_USER` | `blockers+=`, statut `UNKNOWN`, pas d'itération |
| Payload identique au tour précédent | `HALT_PHASE` | `escalation_reason=repetitive_output_loop` |
