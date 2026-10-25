# 02 · Fondements — ce que disent les White Papers Google

> Source : les 5 White Papers Google « Agents » (nov. 2025), auteurs Alan Blount, Antonio
> Gulli, Shubham Saboo, Michael Zimmermann, Vladimir Vuskovic.
>
> - **WP1** — Introduction to Agents
> - **WP2** — Agent Tools & Interoperability with Model Context Protocol (MCP)
> - **WP3** — Context Engineering: Sessions & Memory
> - **WP4** — Agent Quality
> - **WP5** — Prototype to Production
>
> Ce fichier regroupe les passages **vérifiés mot à mot** contre le texte des PDF, avec la
> page exacte. Les éléments qui ne viennent **pas** des docs sont marqués `[adaptation maison]`.

---

## Q1 — Cerveau du Chef : planification & routage

- **Boucle de base = 5 étapes** (WP1 p.11-12) : *Get the Mission → Scan the Scene → Think It
  Through → Take Action → Observe and Iterate*, résumée en « *Think, Act, Observe* ». Elle
  tourne « *until the agent's internal plan is complete and the initial Mission is achieved* »
  (WP1 p.12). **Le doc ne donne aucun compteur d'itération ni garde-fou anti-répétition** →
  à coder soi-même. `[adaptation maison : cap 15 itérations/phase]`
- **Raisonnement** : la couche d'orchestration utilise « *Chain-of-Thought or ReAct … to break
  down complex goals into steps and decide when to think versus use a tool* » (WP1 p.9).
- **Le Chef ne fait pas, il missionne** : « *the Project Manager agent doesn't do the entire
  work itself. It Acts by creating new Missions for its team* » (WP1 p.17).
- **Patterns multi-agents nommés** (WP1 p.25-26) : **Sequential** (« *digital assembly line*
  … output → direct input du suivant »), **Coordinator / Orchestrator-Workers** (un manager «
  *segments the primary task* » et route chaque sous-tâche), **Generator-Critic**, **HITL**
  (« *a deliberate pause … to get approval* »), et le **Supervisor** hiérarchique de
  Co-Scientist (WP1 p.48).
- **Routage de modèles** (WP1 p.19-20) : « *use a frontier model like Gemini 2.5 Pro for the
  heavy lifting of initial planning and complex reasoning, but then … route simpler,
  high-volume tasks … to a much faster and more cost-effective model like Gemini 2.5 Flash* ».
- **Garde-fous déterministes** (WP1 p.35) : « *hardcoded rules that act as a security chokepoint
  outside the model's reasoning* » + **`before_tool_callback`** (WP1 p.38) pour inspecter les
  paramètres avant exécution.
- **Juge bon marché** (WP1 p.38) : « *Gemini as a Judge* … uses a fast, inexpensive model like
  Gemini Flash-Lite … to screen ».

> **Décision studio :** Orchestrator-Workers + Sequential, **pas** de ReAct brut ni de
> Tree-of-Thoughts. *Tree-of-Thoughts* n'est nommé nulle part dans les 5 docs (0 occurrence)
> et multiplierait les inférences → hors budget RAM. `[adaptation maison]`

---

## Q2 — Contrats de passage (handoffs) & contexte

- **Black box** (WP3 p.18) : « *an agent shares its final output, not its process* ».
- **History ≠ context** (WP3 p.16) : l'historique est le transcript permanent ; le contexte est
  « *the carefully crafted information payload sent to the LLM for a single turn* », un extrait
  choisi.
- **Events vs state** (WP3 p.12) : historique append-only d'un côté, mémoire de travail mutable
  (`state`, « *it may mutate the state* ») de l'autre.
- **output_key** (WP3 p.17) : le sub-agent écrit son résultat dans une clé d'état, pas dans le
  fil de discussion.
- **Réduire la taille transférée** (WP3 p.22) : « *reduce the size of the data transferred …
  filter or compact … remove old, irrelevant function call outputs* ».
- **Context rot** (WP3 p.9) : « *their ability to pay attention to critical information
  diminishes as context grows* ». Objectif : « *no more and no less than the most relevant
  information* » (WP3 p.8).
- **Compaction** (WP3 p.23-24) : sliding window, « *Token-Based Truncation … (e.g., 4000
  tokens)* », recursive summarization. Métaphore du sac à dos : « *success hinges not on how
  much you can carry, but on carrying only what you need* » (WP3 p.23). `[adaptation maison :
  4000 tokens retenu comme budget dur par handoff — le doc le donne comme exemple]`
- **Offloading** (WP3 p.38) : mémoire externe « *purpose-built tool* » ; côté outils, passer un
  nom de table/fichier plutôt que le contenu (WP2 p.19).
- **Formats structurés** (WP3 p.34, p.45, p.46) : mémoires en « *dictionary or JSON* » (ex.
  `{"seat_preference":"Window"}`), extraction « *schema and template-based* » avec structured
  output, ou **few-shot** ; sortie en **faits atomiques**.
- **Stable vs transitoire** (WP3 p.61) : « *Use the system prompt for stable, global memories …
  Otherwise, use dialogue injection or memory-as-a-tool for transient, episodic memories* ».

> **Décision studio :** le schéma de handoff `uefn.handoff.v1` (voir `04-contrat-handoff.md`)
> est une **synthèse maison** de ces principes — Google ne publie aucun schéma de handoff
> tout fait. `[adaptation maison]`

---

## Q3 — Sécurisation des outils & grounding (0 hallucination)

- **Le schéma est le contrat** (WP2 p.10) : « *The tool definition declares a contract between
  the model and the tool … a clear name, parameters, and a natural language description* ».
- **inputSchema + outputSchema** (WP2 p.26) « *critical for ensuring correct usage* » ; le
  client « *should validate the tool results against the provided schema* » (WP2 p.29) ;
  l'implémenteur « *should always use the outputSchema capability* » (WP2 p.29).
- **Maths externalisées** (WP2 p.9) : « *mathematical capabilities … is not their strong suit
  and math computations are another area where it is generally best to call on an external
  function* ».
- **Allowlist + pinning** (WP2 p.41) : « *enforce an explicit allowlist of permitted MCP tools
  and servers* », « *Tool and Package Pinning* », flag `listChanged` → revalidation.
- **Deterministic Policy Enforcement** (WP2 p.43) : aux points « *before tool discovery, before
  tool invocation, before data is returned to a client* » ; **Input Validation** + **Output
  Sanitization** (WP2 p.44).
- **Human-in-the-Loop** (WP2 p.36, p.43) : « *obtain explicit user approval before invoking any
  tool* » ; « *Require Human-in-the-Loop (HIL): Treat all high-risk operations … as sensitive
  sinks* ». Aussi WP5 p.14 (sign-off) et p.18 (HITL Escalation).
- **Ne pas faire confiance aux hints du serveur** (WP2 p.27) : les annotations
  (`destructiveHint`…) « *are only hints … MCP clients should not rely on these properties from
  untrusted servers* ».
- **Least privilege** (WP2 p.47) : accès minimal, credentials à expiration courte, « *Secrets
  and credentials should be kept out of the agent context* ».
- **Erreurs descriptives** (WP2 p.29-30) : message d'erreur qui instruit le modèle ; `isError:true`
  avec cooldown (exemple du doc : « *Wait 15 seconds before calling this tool again* »).
  `[adaptation maison : cooldown généralisé]`

**Taxonomie d'échecs à surveiller** (WP4 p.20) — c'est LA grille de débogage :

1. **LLM Planning** : hallucinations, hors-sujet, *context pollution*, *repetitive output loops*.
2. **Tool Usage** : mauvais outil, outil oublié, « *hallucinating tool names or parameter
   names/types* », « *malformed JSON* », types/params manquants.
3. **Tool Response Interpretation** : « *not recognizing an error state returned by the tool …
   and proceeding as if the call was successful* ».
4. **RAG Performance** : retrieval irrelevant/obsolète, ou contexte ignoré.
5. **Trajectory Efficiency** : trop d'appels, latence, efforts redondants.
6. **Multi-Agent Dynamics** : « *misunderstandings or communication loops* », agents qui
  sortent de leur rôle.

Et WP4 p.21 : passer du **Black Box** au **Glass Box** (« *the final answer is wrong because…* »).

---

## Q4 — Ce qui relève de l'adaptation maison (honnêteté)

Ces éléments **ne sont pas** des prescriptions littérales de Google ; ce sont nos calibrages
pour le studio :

| Élément | Statut | Base |
|---|---|---|
| Schéma `uefn.handoff.v1` | `[adaptation maison]` | synthèse de WP3 p.18/34/45 |
| Budget « 4000 tokens » par handoff | `[adaptation maison]` (valeur = exemple WP3 p.24) | WP3 p.23-24 |
| Cap « 15 itérations/phase » | `[adaptation maison]` | aucun compteur dans les WP ; calé sur le budget questions du studio |
| Cooldown « 15 s » sur erreur | `[adaptation maison]` (chiffre = exemple WP2 p.30) | WP2 p.30 |
| « ToT explose la RAM » | `[adaptation maison]` (inférence) | ToT absent des WP |
| 3 rôles pivots + Generator-Critic restreint | `[adaptation maison]` | pattern Generator-Critic WP1 p.25 |

---

## Table de citations rapide (pour vérification)

| Réf | Sujet | Citation-clé |
|---|---|---|
| WP1 p.9 | raisonnement | « Chain-of-Thought or ReAct … decide when to think versus use a tool » |
| WP1 p.11-12 | boucle 5 étapes | « until the agent's internal plan is complete and the initial Mission is achieved » |
| WP1 p.17 | délégation | « the Project Manager agent doesn't do the entire work itself » |
| WP1 p.19-20 | routage modèles | « frontier model … route simpler, high-volume tasks … to … Gemini 2.5 Flash » |
| WP1 p.24 | instruction système | « constraints, desired output schema, rules of engagement … tone of voice » |
| WP1 p.25 | patterns | « digital assembly line » ; « simpler, more focused, easier to build, test, maintain » |
| WP1 p.26 | HITL | « a deliberate pause in the workflow to get approval » |
| WP1 p.35 | garde-fous | « a security chokepoint outside the model's reasoning » |
| WP1 p.38 | callback / judge | « before_tool_callback » ; « Gemini as a Judge » |
| WP1 p.48 | supervisor | Co-Scientist « Supervisor agent … delegating tasks » |
| WP2 p.9 | maths | « not their strong suit … best to call on an external function » |
| WP2 p.10 | contrat outil | « declares a contract between the model and the tool » |
| WP2 p.15-18 | doc outils | noms clairs, params courts, exemples, défauts, « tasks, not API calls » |
| WP2 p.26/29 | schémas | « inputSchema and outputSchema fields are … critical » |
| WP2 p.27 | hints | « clients should not rely on these properties from untrusted servers » |
| WP2 p.36/43 | HIL | « Require Human-in-the-Loop … sensitive sinks » |
| WP2 p.41 | allowlist | « explicit allowlist of permitted MCP tools » ; « Tool and Package Pinning » |
| WP2 p.44 | sanitisation | « Output Sanitization » ; « Input Validation » |
| WP2 p.47 | moindre privilège | « Secrets and credentials should be kept out of the agent context » |
| WP3 p.8 | payload agent | System Instructions / Tool Definitions / Few-Shot Examples / … |
| WP3 p.9 | context rot | « ability to pay attention … diminishes as context grows » |
| WP3 p.12 | events vs state | « it may mutate the state » |
| WP3 p.16/22 | history vs context | « reduce the size of the data transferred » |
| WP3 p.18 | black box | « an agent shares its final output, not its process » |
| WP3 p.23-24 | compaction | « carrying only what you need » ; « e.g., 4000 tokens » |
| WP3 p.34/45 | structuré | « dictionary or JSON » ; « schema and template-based extraction » |
| WP3 p.38 | offloading | « purpose-built tool » |
| WP3 p.61 | stable/transitoire | « system prompt for stable, global memories » |
| WP4 p.20 | taxonomie échecs | « hallucinating tool names » ; « repetitive output loops » ; « communication loops » |
| WP4 p.21 | glass box | « the final answer is wrong because … » |
| WP5 p.14/18 | HITL prod | sign-off ; « HITL Escalation » |
| WP5 p.19-20 | ops loop | Observe → Act → Evolve |
