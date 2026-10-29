# Tool output — `verse-scan`, `verse-grep`, `verse-write`, `verse-build`

> **Tool Outputs** (WP3 p.8). Forme **réelle** des retours du harnais pour la chaîne Verse
> (extraite du run UEFN documenté, 2026-10-24, et du code `script/uefn_spatial_cli.py`).
> À savoir lire **avant** d'annoncer une compilation.

## 1. `verse-scan` — l'inventaire, point de départ obligatoire

```json
{
  "status": "PASSED",
  "command": "verse-scan",
  "root": "",
  "recursive": true,
  "count": 606,
  "files": ["… 200 entrées sur 606 …"],
  "warning": null
}
```

**Lecture :** `Verse.ListFiles` rend les 606 entrées du projet monté, **tronquées à 200** dans la
sortie console ; l'inventaire complet est persisté dans `_verse_files.json` (clé `files`). Un
`count` ne se confond **pas** avec `len(files)` affiché. Dans le run de référence, aucun fichier
n'est créé sous `workspace/verse/` : le scan sert à découvrir l'arborescence réelle et les modules
déjà écrits par les agents 12/13, pas à prouver une absence.

## 2. `verse-grep` — vérifier une signature avant de l'appeler

```json
{
  "timestamp": "…",
  "command": "verse-grep",
  "pathGlob": "**/*.verse",
  "status": "FAILED",
  "resolved": { "GetScore": [ "…/gameplay_score.verse:41: GetScore() : int" ] },
  "not_found": ["GetGoldBalance", "OnPlayerEliminated"],
  "scope": "un Grep vide ne prouve PAS que l'API n'existe pas : verifier le motif sur un nom connu avant de conclure. Une signature trouvee doit etre lue dans son contexte (verse-scan puis ReadFile)."
}
```

**Lecture :** sortie code `1` dès qu'un symbole manque. `not_found` ≠ « la fonction n'existe pas » :
≠ un motif mal orthographié, ≠ un fichier hors `pathGlob`. Sur un `not_found`, je relis le digest
`_verse_files.json`, je retente avec un sous-motif connu, et si la signature reste introuvable
→ `UNKNOWN` + handoff `BLOCKED`. **Je n'invente jamais un nom de fonction pour remplir le payload.**

## 3. `verse-write` — l'écriture, puis la relecture

Refus sans consentement explicite (jamais contournable, `CONSENT_REQUIRED`, code `1`) :

```json
{
  "status": "FAILED",
  "command": "verse-write",
  "error_kind": "CONSENT_REQUIRED",
  "local_file": "C:\\…\\ws_corpo_plaza\\ui_hud.verse",
  "verse_path": "…/ui_hud.verse",
  "bytes": 4211,
  "detail": "VerseToolset.WriteFile est classe DANGEREUX et n'a jamais ete execute : il modifie le code source du projet. Montrer le code a l'utilisateur, obtenir son accord explicite, puis rejouer avec --i-agree-to-modify-project. Sans accord : donner le code a coller."
}
```

Succès (record ajouté à `_verse_written.json`, `next` = la chaîne à enchaîner) :

```json
{
  "timestamp": "…",
  "verse_path": "claudtest/ui_hud.verse",
  "local_file": "C:\\…\\ws_corpo_plaza\\ui_hud.verse",
  "bytes": 4211,
  "read_back_matches": true,
  "status": "PASSED",
  "next": "verse-build : Session.GetSessionStatus doit etre Disconnected"
}
```

**Lecture :** `read_back_matches` vient de `Verse.ReadFile` **après** l'écriture, pas de mon souvenir.
`false` → le fichier relu ne contient pas le texte écrit : **on ne compile pas**, on remontre le
diff. Erreurs reconnues : `FILE_NOT_FOUND` (le `--local-file` n'existe pas, code `1`) ;
`McpError: … mounted Verse content root` → le CLI réécrit `verse_path` sous la racine du projet
montée par l'éditeur puis retente — vérifier que le chemin final est bien **mon** fichier.

## 4. `09_verse_report.json` — la seule preuve de build qui vaille

Sortie **réelle** du run de référence (`verse-build`, code `0`) :

```json
{
  "timestamp": "2026-10-23T22:52:27.448400+00:00",
  "command": "verse-build",
  "session": "Disconnected",
  "status": "PASSED",
  "diagnostics_count": 0,
  "error_diagnostics": [],
  "warnings": [],
  "build_log_lines": [ "… 15 lignes …" ],
  "success_lines": [ "[2026.10.23-20.14.27:123][396]VerseBuild: SUCCÈS -- Version terminée." ],
  "scope": "une liste de diagnostics vide ne suffit PAS : il faut aussi une ligne de succes recente dans VerseBuild. Les lignes sont localisees et le log garde les builds precedents : comparer l'horodatage a 2026-10-23T22:52:27.448400+00:00"
}
```

**Points de contrôle, dans cet ordre :**

1. `session` = **`"Disconnected"`**. Sinon `{"error_kind": "SESSION_CONNECTED"}`, code `1`, et
   `BuildAll` **n'est pas lancé** (comportement en session connectée jamais testé).
2. `error_diagnostics: []` **et** `diagnostics_count` cohérent.
3. `success_lines` **non vide** avec un horodatage **postérieur** à mon dernier `verse-write`.
   Le log conserve les builds passés : les 15 lignes du run couvrent 5 builds (20:14 → 22:52) et
   les lignes sont **localisées** (« SUCCÈS -- Version terminée. », « Compilation terminée. »,
   « Liaison terminée. ») — une ancienne ligne de succès n'est **pas** la preuve de mon build.
4. Le texte des lignes est repris **verbatim** dans le handoff (accents compris) ; `timeBuildMs`
   réel observé ≈ 6 s, donc un timeout ici est suspect, pas normal.

## 5. Échecs que je sais reconnaître

| Sortie | Signification | Conduite |
|---|---|---|
| code `2`, `OFFLINE` / `editeur injoignable sur http://127.0.0.1:8000/mcp` | pont hors ligne **ou** sur un autre port (le run documenté tournait sur **8001** via `UEFN_MCP_URL`) | vérifier la variable, remonter à `Engine_Programmer` ; **rien n'a été exécuté**, nulle part dire « build OK » |
| code `3`, `McpTimeout` / `WinError 10054` (`TIMEOUT_OUTCOME_UNKNOWN`) | écriture ou build peut-être appliqué sans réponse | relire par `Verse.ReadFile` / `GetLogEntries`, **ne pas rejouer** l'écriture à l'aveugle |
| code `1`, `{"type": "NO_VERSE_STAGED", "detail": "aucun .verse dans workspace/verse/ : le gabarit en fournit un, ou ecrire le fichier d'abord"}` | `list-editables` lancé avant tout module stage | état **documenté** (run de référence, ANNEXE B ligne 8) : soit j'écris mon module, soit je rends un `10_editables.json` local avec `scope` explicite — jamais un faux `editable_count: 0` présenté comme un succès |
| code `1`, `{"error_kind": "CONSENT_REQUIRED"}` | gate HITL non franchi | montrer le code, demander l'accord via le Producer, rejouer avec `--i-agree-to-modify-project` |
| `error_diagnostics` non vide, code `1` | erreurs Verse réelles | corriger **mon** fichier ; ne jamais toucher au `.verse` d'un autre agent pour faire passer ma compilation |
| `Logs.GetLogEntries : "Log category 'Valkyrie' not found."` | catégorie inventée | passer `GetLogCategories {"filter":"Valkyrie"}` → `LogValkyrie`, `LogValkyrieValidation`, et la catégorie du build `VerseBuild` |
