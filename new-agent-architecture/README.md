# Studio UEFN v2 : Claude orchestre, des scripts executent, du code verifie

Studio de creation de maps UEFN pilote par Claude Code. Il remplace l'architecture Qoder a
21 agents, dont le run corpo-plaza a montre les limites. Fonde sur les 5 white papers Google
« Agents ».

| Document | Contenu |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | conception, justification par les white papers, limites connues |
| [CLAUDE.md](CLAUDE.md) | instructions de l'orchestrateur (chargees automatiquement) |
| [docs/runbook.md](docs/runbook.md) | commandes pas a pas, dont le redemarrage de corpo-plaza |
| [docs/roles.md](docs/roles.md) | correspondance entre les 21 agents v1 et les roles v2 |
| [docs/lecons.md](docs/lecons.md) | memoire procedurale (injectee a chaque session) |
| [docs/rubrique-visuelle.md](docs/rubrique-visuelle.md) | grille du sous-agent `critique` |
| [docs/reprise-externe.md](docs/reprise-externe.md) | protocole si un autre modele reprend le travail |

## Arborescence
```
new-agent-architecture/
├── CLAUDE.md, ARCHITECTURE.md, README.md
├── .claude/
│   ├── settings.json        permissions (ask/deny) + hooks
│   ├── hooks/               garde.py (PreToolUse), demarrage.py (SessionStart)
│   └── agents/              8 sous-agents
├── agents/                  les 21 dossiers metier v1 (persona, skill, exemples), en reference
├── config/                  studio.json (allowlist MCP), projects/<slug>.json, supports.json,
│                            tool_schemas.json, mcp-inventory.snapshot.json, circuit_breakers.json
├── scripts/                 scripts-taches + uefn/ (passerelle MCP, jauge RAM, config)
├── validators/              PROTEGE : regles, golden set (20 cas), MANIFEST.json
├── tools/                   lock_validators.py, make_golden.py (humain), test_garde.py
├── templates/               schemas (cameras.json, ...)
└── docs/
```

## Verification rapide
```bash
python tools/test_garde.py
python validators/run_all.py --golden-seulement
python scripts/check_plan.py
python scripts/pose_lot.py simuler 1
```
