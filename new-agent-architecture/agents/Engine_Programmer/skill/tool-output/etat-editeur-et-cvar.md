# Tool output — état de l'éditeur, niveau actif et pagination (CVar)

> **Tool Outputs** (WP3 p.8). Sorties **brutes réelles** du run UEFN documenté (2026-10-24),
> telles qu'elles figurent dans le journal `_mcp_calls.jsonl`, puis la lecture que j'en fais.

## 1. Nom réel du niveau chargé

```json
// outil : Scene.get_current_level   arguments : {}
{"returnValue": "/dc587e05-5351-4d88-b9bd-dc21fbb17a81/claudtest"}
// isError: false   duration_ms: 316   (second appel identique : 182 ms)
```

**Lecture :**

- Le nom **interne** du niveau est le dernier segment : `claudtest`. C'est la valeur qui va dans
  `active_level_name` ; le `returnValue` complet va dans `active_level_path`.
- Le nom affiché dans l'UI de l'éditeur peut différer : **jamais** de niveau « deviné » à partir d'un
  titre d'onglet ou d'un nom de projet.
- Ce champ ne suffit pas : la confirmation que c'est **bien le niveau attendu** vient de
  `Producer_Orchestrator` (donc de l'utilisateur) → `level_confirmed_by`.

## 2. Pagination : lire, écrire, **relire**

```json
// outil : ProgrammaticToolset.GetCVarValue
// arguments : {"name": "ModelContextProtocol.PaginationPageSize"}
{"returnValue": "0"}          // isError: false   duration_ms: 332

// outil : ProgrammaticToolset.SetCVarValue
// arguments : {"name": "ModelContextProtocol.PaginationPageSize", "value": "200"}
{"returnValue": null}         // isError: false   duration_ms: 331

// relecture : ProgrammaticToolset.GetCVarValue (memes arguments qu'au premier appel)
{"returnValue": "200"}        // isError: false   duration_ms: 329
```

**Lecture :**

- Les valeurs sont des **chaînes** (`"0"`, `"200"`), pas des nombres.
- `SetCVarValue` renvoie `null` **sans** `isError` : ce null ne prouve rien. La preuve est la
  **troisième** ligne (relecture). Écrire `200` sans relecture = case `FAILED`, pas `OK`.
- `0` est un état dangereux : les listes sortent tronquées **sans message d'erreur**. Un inventaire
  obtenu avec `0` est incomplet et silencieusement faux.

## 3. État de session

```json
// outil : ValkyrieToolset.SessionToolset.GetSessionStatus   arguments : {}
{"returnValue": "Disconnected"}   // isError: false   duration_ms: 332
```

**Lecture :** `Disconnected` au moment du préflight est un fait, pas une anomalie à cacher : les
outils de lecture d'état répondent, l'éditeur est joignable, mais aucune session créative n'est
ouverte. Le handoff porte `session_status: "Disconnected"` et la case `etat_session` en
`NON_BLOQUANT`, avec l'indication que l'ouverture de session relève du Producteur (gate HITL).

## 4. RAM : mesure instantanée, jamais héritée

```
$ python -c "import ctypes; ... GlobalMemoryStatusEx()"
Total_MB=15515   Free_MB=3247   -> utilise ~12268 Mo (79,1 %)
$ tasklist | grep -i unreal
(aucun process Unreal/FortniteCreative au moment de la mesure)
```

**Lecture :** 12 268 Mo sur 15 515 = **79 %**, sous le seuil d'alerte (85 %) mais au-dessus du seuil
de prudence : la case `processus_et_ram` est rendue `OK` avec la mesure horodatée, et l'absence de
process éditeur nommément retrouvé est signalée en `detail`. Le journal `_mcp_calls.jsonl` ne
contient **aucun** chiffre de RAM : une valeur de RAM recopiée de mémoire serait `UNKNOWN`, pas un
chiffre plausible.

## 5. Échecs reconnus, avec leur code

| Sortie brute | Code | Ce que je rends |
|---|---|---|
| `OFFLINE` / `editeur injoignable sur http://127.0.0.1:8000/mcp` | 2 | `mcp_ports_tested` avec `OFFLINE` ; rien n'accuse l'éditeur d'être cassé |
| `McpTimeout: timeout 60.0s : timed out` sur `ValkyrieToolset.SessionToolset.StartSession` | 3 | `TIMEOUT_OUTCOME_UNKNOWN` : état inconnu, **pas** de relance en boucle |
| `WinError 10054` (connexion réinitialisée) | 3 | arrêt, relecture de l'état réel avant tout nouvel appel |
| `McpError: Logs.GetLogEntries : "Log category 'Valkyrie' not found."` | 1 | erreur d'**appel** (catégorie inexistante), pas un état de l'éditeur |
| `Output too large (790.8 KB)` + chemin de fichier | 0 | sortie conservée sur fichier, seul le chemin passe dans le handoff |

**Règle transversale :** un seul appel MCP à la fois, `inputSchema` et `outputSchema` validés côté
client, `isError` ou sortie vide = STOP et statut `UNKNOWN`.
