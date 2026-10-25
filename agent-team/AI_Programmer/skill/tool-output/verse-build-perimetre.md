# Tool output — `verse-build` et la question du **périmètre**

> **Tool Outputs** (WP3 p.8). Sortie **réelle** de `09_verse_report.json` (run documenté
> `night_city_corpo_plaza`, 2026-10-24, niveau `/dc587e05-5351-4d88-b9bd-dc21fbb17a81/claudtest`)
> et de `references/verse-qa-standard.md` §6. À savoir lire avant d'annoncer quoi que ce soit.

## 1. Sortie brute réelle (extraite de `09_verse_report.json`, troncature 15 → 3 lignes de log)

```json
{
  "timestamp": "2026-10-23T22:52:27.448400+00:00",
  "command": "verse-build",
  "session": "Disconnected",
  "status": "PASSED",
  "diagnostics_count": 0,
  "error_diagnostics": [],
  "warnings": [],
  "build_log_lines": [
    "[2026.10.23-20.14.27:123][396]VerseBuild: Compilation terminée.",
    "[2026.10.23-20.14.59:668][431]VerseBuild: SUCCÈS -- Version terminée.",
    "[2026.10.23-22.52.32:067][154]VerseBuild: Liaison terminée."
  ],
  "success_lines": [
    "[2026.10.23-22.52.32:067][154]VerseBuild: Compilation terminée."
  ],
  "scope": "une liste de diagnostics vide ne suffit PAS : il faut aussi une ligne de succes recente dans VerseBuild. Les lignes sont localisees et le log garde les builds precedents : comparer l'horodatage a 2026-10-23T22:52:27.448400+00:00"
}
```

**Lecture, dans cet ordre :**

1. `session` = `Disconnected` : `GetSessionStatus` est appelé **avant** `BuildAll`.
2. `diagnostics_count: 0` **et** `error_diagnostics: []`. Le `BuildAll` réel renvoie
   `{"returnValue":[]}` : une liste vide ne dit **rien d'autre**.
3. `success_lines` **non vide** et horodatée **après** le `timestamp` de l'appel. Le fichier ci-dessus
   contient 5 blocs de 3 lignes (20.14.27, 20.14.49, 20.14.59, 21.12.26, 22.52.32) : appel à
   `22:52:27`, seule la ligne `[2026.10.23-22.52.32:067]` suit. Les quatre autres sont des **restes**
   et ne prouvent rien.
4. Les libellés sont **localisés** (`terminée`, `SUCCÈS`) : en console Windows (cp1252) ils
   s'affichent `Compilation termin?e.` Le fichier est en UTF-8, c'est l'**affichage** qui dégrade les
   octets. **Je ne « corrige » jamais un libellé** et je compare les octets du fichier, pas le
   terminal.

## 2. Ce que renvoie une compilation quand **un sous-ensemble seulement** est stageable

`BuildAll` n'a **pas** de paramètre de fichiers : il compile **tout** le Verse présent dans le
projet, et le rapport ne nomme que des diagnostics — jamais une liste de fichiers compilés. Quand
`workspace/verse/` ne contient que mes fichiers (ou aucun), la sortie reste identique à un succès
total. D'où les trois lectures obligatoires :

- **La preuve de mon périmètre n'est pas dans le rapport de build**, elle est dans
  `payload.files` : chaque fichier écrit, `read_back_matches: true` et `bytes` mesurés
  (`_verse_written.json`). Une compilation `PASSED` sans relecture de **mes** fichiers n'affirme
  rien sur **mes** mécaniques.
- Un diagnostic qui pointe un fichier d'un **autre** rôle (`game_manager_device.verse`,
  `ui_hud.verse`) est **signalé**, jamais corrigé par moi : le gatekeeper est global, la
  responsabilité ne l'est pas.
- Si rien n'est stageable, `list-editables` rend le type exact (ANNEXE B n°8, `2026-10-24`, code
  `1`) :
  ```json
  {"type": "NO_VERSE_STAGED", "detail": "aucun .verse dans workspace/verse/"}
  ```
  Ce n'est **pas** un échec de compilation : c'est l'absence de matière. Le rapport le dit
  explicitement (`scope`, `live.tool_result`) au lieu de le taire, et `--apply` n'est jamais lancé.

## 3. Refus avant appel — `SESSION_CONNECTED` (code `1`, rien n'a tourné)

```json
{
  "status": "FAILED",
  "command": "verse-build",
  "error_kind": "SESSION_CONNECTED",
  "session": "InProgress",
  "detail": "BuildAll n'est prouve qu'avec une session Disconnected. Son comportement session connectee n'a jamais ete teste : ne pas lancer."
}
```

**Lecture :** le comportement de `BuildAll` en session connectée est **`UNKNOWN`**, pas « risqué ».
Aucun `09_verse_report.json` n'est écrit, rien n'est compilé, et **je ne demande pas l'arrêt de la
session** : c'est une décision du Producteur (gate HITL). J'attends, ou je rends un handoff
`BLOCKED`.

## 4. Les trois échecs d'appel que je sais lire

| Sortie brute | Code | Ce que ça veut dire | Conduite |
|---|---|---|---|
| `{"error_kind":"OFFLINE","error":"…connection refused…"}` | `2` | l'éditeur n'a **pas reçu** l'appel | vérifier UEFN ouvert et le port (`8000` par défaut, pont observé sur `8001`, `UEFN_MCP_URL`) ; rejouable |
| `{"status":"FAILED","command":"verse-build","error_kind":"TIMEOUT_OUTCOME_UNKNOWN","error":"timeout 60.0s : timed out","next":"Relire l'etat (find_actors, get_actor_transform) avant de rejouer."}` | `3` | **état inconnu** : le build a peut-être tourné | relire `BuildAll` suivant + log `VerseBuild` ; **jamais** de relance à l'aveugle |
| `{"error_kind":"TOOL_ERROR","error":"…","next":"L'appel a ete traite : relire l'etat (_placed.json, find_actors) avant de rejouer."}` | `1` | l'appel a été **traité** | lire les diagnostics et le log avant toute décision |

## 5. Autour du build : les échecs réellement documentés de la run de référence

- **`launch-session … --stop-after-verify`** (ANNEXE B n°9, 2026-10-24T00:56:11) :
  `{"status":"FAILED","error_kind":"TIMEOUT_OUTCOME_UNKNOWN","error":"timeout 60.0s : timed out"}`,
  trace `McpTimeout: timeout 60.0s : timed out` sur `SessionToolset.StartSession`, **code `3`**.
  Cause : `StartSession` bloque le pont plus de 60 s pendant l'upload/cook. Conduite appliquée :
  **aucune relance**, état relu par `Session.GetSessionStatus` (`UpdatingContent`), puis journaux.
- **`12_session_report.json`** (ANNEXE B n°10) : `Error: File does not exist.` — le CLI a timeouté
  **avant d'écrire** le rapport. Donc : **aucun comportement de mes mécaniques ne peut être annoncé
  observé en jeu** dans un tel état, et mon handoff le dit (`playtest: "AUCUNE_SESSION"`).
- **`Logs.GetLogEntries {"category":"Valkyrie"}`** (ANNEXE B n°11) :
  `McpError: Logs.GetLogEntries : "Log category 'Valkyrie' not found."` → la catégorie réelle est
  `LogValkyrie` / `LogValkyrieValidation` (à découvrir par `GetLogCategories {"filter":"Valkyrie"}`).
  Pour la compilation, la catégorie est `VerseBuild`.
- **Sortie huge** (ANNEXE B n°12) : `list_toolsets` → 790,8 Ko, « Output too large ». Redirection
  sur fichier et lecture ciblée ; rien de tel ne va dans un handoff.

## 6. Une compilation qui « passe » ne dit toujours rien

Le `BuildAll` des runs documentés n'a **jamais** rendu de diagnostic d'erreur : la forme exacte d'un
`{"severity":"error", …}` est donc **`UNKNOWN`** — je ne l'invente pas dans un handoff, je cite le
log `VerseBuild` relu. Et `GetClientLogEntries` hors session renvoie
`No client log was found; start a play-in-client session first.` : « ça compile » ≠ « ça marche ».
