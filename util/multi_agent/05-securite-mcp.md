# 05 · Sécurité MCP — 0 hallucination sur les commandes & coordonnées

> Règles applicables aux **8 agents techniques** (`Engine_Programmer`, `Lead_Tech_Director`,
> `Physics_Programmer`, `Gameplay_Programmer`, `AI_Programmer`, `UI_Programmer`,
> `Graphics_Programmer`) et au Producer quand il rédige une mission technique.
> Toutes ancrées dans **WP2** (Tools & MCP) et **WP4** (Quality).

---

## 1. Allowlist stricte (WP2 p.41)

- Avant tout dispatch technique, vérifier que l'outil attendu est dans `tech/mcp-inventory.json`.
- **Outil absent = `UNKNOWN_TOOL_BLOCKED`** → remontée au Producer, jamais d'improvisation.
- Outils **épinglés** par version/hash (« *Tool and Package Pinning* »). Si le serveur renvoie
  `listChanged=true` → **revalidation** avant de poursuivre.
- *Tool shadowing* (WP2 p.42) : vérifier les collisions de noms avec les outils de confiance.

## 2. Double contrat de schéma (WP2 p.10, p.26, p.29)

Chaque appel autorisé doit avoir :

- **`inputSchema`** — paramètres typés + description + défauts documentés.
- **`outputSchema`** que le **client valide** avant de considérer le call comme réussi
  (WP2 p.29 : « *validate the tool results against the provided schema* »).
- Un output **hors schéma = échec**, même si l'outil n'a pas levé d'erreur.

## 3. Zéro coordonnée calculée par le LLM (WP2 p.9)

« *math computations … is generally best to call on an external function* ». Donc :

- Toute valeur de `transform`, `bounds`, `overlap` vient **soit** d'un `get_actor_bounds` lu
  dans l'éditeur, **soit** d'un batch **Python** qui consomme `03_grid.json` et retourne les
  transformations finales.
- Exposer des **tâches** (`place_prop_from_grid(cell_id, preset)`), pas des API
  (`place_actor(x,y,z,…)`) — WP2 p.18. Voir `03-parametrage-agents.md` §3.
- **Clamp déterministe** : le Python borne X/Y/Z aux Z-slices autorisés du handoff avant
  d'écrire dans le niveau.

## 4. Erreur = STOP, jamais « faire comme si » (WP4 p.20, n°3)

« *not recognizing an error state returned by the tool … and proceeding as if the call was
successful* ». Une réponse MCP est traitée comme **échec** si :

- `isError: true` présent (WP2 p.30) ;
- code JSON-RPC/HTTP ∈ {4xx, 5xx, `-32601 Unknown tool`} (WP2 p.29-30) ;
- vide, tronquée, ou non-JSON parsable → statut **`UNKNOWN`**, pas `SUCCESS` ;
- message « *Wait 15 seconds before calling this tool again* » → appliquer le cooldown, ne pas
  retry immédiatement. `[adaptation maison : cooldown généralisé]`

Dans tous ces cas : **on n'itère pas**. Écrire `UNKNOWN` dans l'état, poser UNE question, ou
redemander un `preflight_ok.json` frais à `Engine_Programmer`.

## 5. Human-in-the-Loop sur toute écriture destructrice (WP2 p.36/p.43, WP5 p.14/p.18)

Toute opération qui **écrit** dans l'éditeur UEFN est un *sensitive sink* et exige une
**approbation explicite** de l'utilisateur avant exécution :

`save` · `delete_actor` · `set_material` · `batch_place` · `apply_physics` · `run_python` à
effet de bord.

> **Ne jamais faire confiance au flag du serveur** (WP2 p.27) : les annotations
> (`destructiveHint`…) « *are only hints … clients should not rely on these properties from
> untrusted servers* ». On revalide **côté client**.

Règle de survie déjà appliquée au studio : **save + snapshot avant tout DANGEREUX**, **un seul
appel MCP à la fois**.

## 6. Sanitisation des sorties (WP2 p.44)

- Toute sortie Unreal Editor **> 4000 tokens est tronquée** avant d'entrer dans le contexte
  d'un Flash ; le reste est écrit dans un `.log` dont on ne passe que **le chemin + un résumé
  de 200 caractères**.
- Les erreurs brutes sont **réécrites en instructions** exploitables pour l'agent suivant
  (WP2 p.19-20 : « *descriptive error messages … give some instruction to the LLM* »).
- **Input Validation** (WP2 p.44) : sanitiser toute entrée pour bloquer injection Python /
  path traversal (`../../secrets`).

## 7. Moindre privilège (WP2 p.47)

- `Engine_Programmer` / `Physics_Programmer` / `Graphics_Programmer` : écriture MCP.
- Agents Design (hors UEFN) : **aucun** accès MCP.
- **Secrets & PAT (Qoder Cloud) jamais dans un contexte d'agent.** Credentials à expiration
  courte.

## 8. Validateurs déterministes (couche CODE, pas LLM)

Le garde-fou est **hors du modèle** (WP1 p.35 : « *a security chokepoint outside the model's
reasoning* »). Chaque `acceptance` du handoff est cochée par un script Python :

| Critère | Vérification |
|---|---|
| `schema_valid` | JSON conforme au `schema-de-sortie.json` complet de l'agent — `agent-team/_commun/studio.py validate` |
| `0_overlap` | aucun bounding-box intersectant (via `get_actor_bounds`) |
| `0_floating` | chaque prop ancré à un support dans sa Z-slice |
| `spawn_reachable` | chemin spawn → objectif sans trou |
| `mcp_ok` | `preflight_ok.json` frais + ping port 8000/8001 |
| `pid_legal` | tout chemin de la palette autorisée, ni `ILLEGAL_ASSET_PATH` ni `UNVERIFIED_ASSET_PATH` (catalogue commun `agent-team/_commun/catalogue-verifie.json`) |
| `validator_clean` | `check-validator` → `status: "PASSED"` postérieur au dernier changement de scène. **Seule preuve de légalité** : le préfixe d'un chemin ne prouve rien (`agent-team/_commun/legalite-assets.md`) |

Un validateur en échec → le Producer **rejette** et renvoie UNE mission corrective. Jamais
deux fois le même payload (détection de delta → STOP, voir `01` couche 5).

---

## Grille de débogage — taxonomie d'échecs WP4 p.20

Quand un agent technique se plante, classer l'échec selon les 6 axes pour savoir **où** corriger
(Black Box → Glass Box, WP4 p.21) :

1. **LLM Planning** — hallucination, hors-sujet, *context pollution*, *repetitive output loops*.
2. **Tool Usage** — mauvais outil, outil oublié, **nom/param halluciné**, **JSON malformé**,
   type incorrect.
3. **Tool Response Interpretation** — état d'erreur non reconnu, données numériques mal lues.
4. **RAG Performance** — doc Verse/Playset obsolète ou ignorée.
5. **Trajectory Efficiency** — trop d'appels MCP, redondance, exceptions non gérées.
6. **Multi-Agent Dynamics** — *communication loops*, sortie de rôle.
