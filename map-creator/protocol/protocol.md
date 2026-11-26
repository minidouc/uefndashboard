# Map Creator — App Server JSON Protocol (v1)

Inspiré de l'App Server de Codex : un **protocole JSON-RPC 2.0 + flux d'événements** découple complètement le **Cœur Rust** (`map-creator-core`) des clients :
- **Interface Svelte** (`map-creator/ui`)
- **CLI** (`map-creator-core`)
- **IslandForge** ou tout client externe futur

---

## Transports supportés

1. **HTTP JSON-RPC 2.0** : `POST http://127.0.0.1:4310/rpc`
2. **WebSocket bidirectionnel** : `GET ws://127.0.0.1:4310/ws`
   - Le client envoie des requêtes JSON-RPC 2.0 (`{"jsonrpc":"2.0","id":1,"method":"...","params":{...}}`).
   - Le serveur répond avec `{"jsonrpc":"2.0","id":1,"result":...}` ou `{"jsonrpc":"2.0","id":1,"error":{...}}`.
   - Le serveur pousse en temps réel des **événements** (sans `id`) :
     ```json
     {
       "jsonrpc": "2.0",
       "method": "event",
       "params": {
         "type": "agent.tool_call | permission.requested | outbox.updated | validation.completed | state.changed",
         "ts_utc": "2026-11-26T18:00:00Z",
         "payload": {}
       }
     }
     ```

---

## Méthodes RPC disponibles

### 1. Système & Configuration
| Méthode | Description |
|---|---|
| `system.health` | Santé du cœur, projet actif, version UEFN, statut MCP, taille state |
| `config.get` | Retourne `app.toml`, `permissions.toml`, `mcp_servers.toml`, `circuit_breakers.json` |
| `config.update_app` | Met à jour `config/app.toml` (thème CSS, raccourcis, modèles, prompts, outils) |
| `config.update_permissions` | Met à jour `config/permissions.toml` (action humaine uniquement) |
| `config.update_mcp` | Met à jour `config/mcp_servers.toml` (ajout/édition d'extensions MCP) |
| `config.update_circuit_breakers` | Active/désactive un coupe-circuit MCP à chaud |

### 2. Pipeline & État (Phases 0 → 9)
| Méthode | Description |
|---|---|
| `project.list` | Liste tous les projets dans `workspace/projects/` |
| `project.create` | Crée un projet neuf (Phase 0, mode `production` ou `prototype`) |
| `project.select` | Bascule le projet actif |
| `pipeline.state` | État complet (< 20 Ko), phases 0→9, portes, verrous, compteurs |
| `pipeline.advance` | Tente une transition vers la phase cible (vérifie portes + validateurs) |
| `pipeline.approve_gate` | Enregistre une porte humaine avec **citation exacte obligatoire** |
| `pipeline.lock_deliverable` | Verrouille un livrable validé (immuable sans Change Request humaine) |
| `pipeline.change_request` | Ouvre/approuve une demande de changement humaine sur un livrable verrouillé |
| `pipeline.set_mode` | Bascule `production` / `prototype` (sans jamais toucher aux invariants) |
| `pipeline.derogation` | Enregistre une dérogation encadrée (liste explicite sacrifiable + citation) |
| `pipeline.events` | Retourne les N derniers événements avec filtrage par provenance |

### 3. Plans 2D (4 couches + Coupe)
| Méthode | Description |
|---|---|
| `plan.list` | Liste les plans de quartiers du projet actif |
| `plan.get` | Retourne un plan 4 couches (`a_scene`, `b_fonds`, `c_details`, `d_effets` + coupe) |
| `plan.check` | Exécute tous les contrôles géométriques (collisions, flottants, accessibilité, raisons, budget mémoire) |
| `plan.render_svg` | Génère le rendu SVG 2D (avec masque de couches) et le rendu SVG en coupe |
| `plan.upsert_item` | Ajoute ou met à jour un élément du plan (re-vérifie automatiquement) |

### 4. Dossier d'envoi (Outbox asynchrone)
| Méthode | Description |
|---|---|
| `outbox.list` | Liste tous les jobs par statut (`pending`, `sent`, `validated`, `failed`) |
| `outbox.submit_from_plan` | Découpe un plan validé en lots et les écrit dans `outbox/pending/` |
| `outbox.dispatch` | Envoie un job `pending` vers MCP (live ou simulateur), capture la réponse brute et relit l'éditeur |
| `outbox.get_raw_response` | Lit la preuve brute immuable stockée dans `outbox/responses/` |

### 5. Mémoire 3 niveaux
| Méthode | Description |
|---|---|
| `memory.lessons_list` | Liste les leçons apprises (Niveau 2) |
| `memory.lessons_add` | Ajoute une leçon prouvée (règle + incident + provenance) |
| `memory.library_search` | **Recherche avant de produire** (script 0 token) dans la bibliothèque (Niveau 3) |
| `memory.library_add` | Ajoute une entrée validée dans la bibliothèque (refuse `agent_claim`) |
| `memory.library_check_staleness` | Marque `suspect` les entrées liées à une ancienne version d'UEFN |

### 6. Validateurs protégés & Compatibilité Agent PC
| Méthode | Description |
|---|---|
| `validators.run` | Exécute dans l'ordre immuable : Intégrité SHA-256 `MANIFEST.json` → Golden Set (20 cas) → Règles réelles |
| `validators.status` | Retourne l'état du MANIFEST et le dernier rapport |
| `compat.status` | Retourne la matrice de compatibilité Agent PC (`compat/COMPAT_STATUS.md`) et les fixtures disponibles |
| `compat.ingest_fixture` | Ingère une réponse JSON brute collectée par l'Agent PC et met à jour le statut de l'outil |

### 7. Boucle d'Agent & Permissions (style Codex)
| Méthode | Description |
|---|---|
| `agent.run` | Lance une mission sur l'un des 10 rôles (boucle modèle → outil → permission → résultat) |
| `agent.history` | Retourne l'historique des sessions d'agent |
| `permissions.pending` | Liste les demandes d'approbation humaine en attente |
| `permissions.resolve` | Résout une demande (`allow_once` / `deny`) en direct |
| `mcp.servers` | Liste les extensions MCP configurées et leur état |
| `mcp.ping` | Teste la connectivité d'une extension MCP |
