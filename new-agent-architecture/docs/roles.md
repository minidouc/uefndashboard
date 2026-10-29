# Des 21 agents de la v1 aux roles de la v2

Les dossiers d'origine sont conserves dans `agents/` (persona, skill, exemples). Les sous-agents
v2 les **lisent** comme reference metier. En cas de conflit, la v2 l'emporte.

| Agent v1 | Devient en v2 | Pourquoi |
|---|---|---|
| Producer_Orchestrator | **orchestrateur Claude** (`CLAUDE.md`) | un seul hub ; l'ecriture du state passe a `state.py` |
| Creative_Director | sous-agent `directeur-creatif` (sonnet) | jugement creatif |
| Game_Designer | sous-agent `game-designer` (sonnet) | jugement de conception |
| System_Designer, Economy_Designer, Mission_Content_Designer | fusionnes dans `game-designer` | meme livrable (GDD), moins de handoffs |
| Level_Designer | sous-agent `level-designer` (sonnet) | choisit les parametres d'un **generateur** (arene, parkour, ville...) ou en ecrit un nouveau |
| UX_UI_Designer | sous-agent `ux-ui-designer` (sonnet) | conception UI + generateurs d'assets |
| Narrative_Designer, Writer_Scenariste | sous-agent `narration` (haiku) | redaction a faible enjeu technique |
| Audio_Director, Composer, Sound_Designer, Voice_Designer | sous-agent `audio` (haiku) | brief audio ; pas d'outil de production audio |
| Gameplay_Programmer, AI_Programmer, UI_Programmer | sous-agent `programmeur-verse` (sonnet) | code Verse, sans acces a l'editeur |
| Engine_Programmer | **scripts** `preflight.py`, `pose_lot.py`, `mcp_gateway.py` | taches mecaniques : un script ne se trompe pas et ne triche pas |
| Physics_Programmer | **scripts** `check_plan.py` + validateurs `zero_overlap`, `zero_flottant`, `accessibilite` | l'audit physique est un calcul |
| Graphics_Programmer | **scripts** `capture.py`, `spike_capacite.py` + validateur `captures_visuelles` | mesures et preuves ; le gout passe au `critique` |
| Lead_Programmer | **orchestrateur** + `config/studio.json` (allowlist) | les decisions d'archi sont des decisions de config, prises par l'humain |
| *(nouveau)* | sous-agent `critique` (sonnet, lecture seule, une passe en fin de BUILD) | juge independant : Agent-as-a-Judge et LLM-as-a-Judge (WP4) |

**Bilan : 8 sous-agents + 1 orchestrateur + 16 scripts + 3 generateurs de map.** Un modele n'intervient que la ou il
faut du jugement.
