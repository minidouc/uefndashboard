# Tool output — `verse-build`

> **Tool Outputs** (WP3 p.8). Forme **réelle** des retours de la chaîne Verse, extraite du run
> UEFN documenté `1v1-buildfight` (niveau `/1a52cfc2-8485-44f7-8516-3583d0b0c33c/testmcp`,
> 2026-10-21) et du code `script/uefn_spatial_cli.py` (`cmd_verse_build`). Le rapport qui fait foi
> est `09_verse_report.json`.

## 1. PASSED — ce que je rends (extrait réel de `09_verse_report.json`)

```json
{
  "timestamp": "2026-10-20T23:32:16.670455+00:00",
  "command": "verse-build",
  "session": "Disconnected",
  "status": "PASSED",
  "diagnostics_count": 0,
  "error_diagnostics": [],
  "warnings": [],
  "build_log_lines": [
    "[2026.10.20-23.32.21:205][724]VerseBuild: Compilation terminée.",
    "[2026.10.20-23.32.21:205][724]VerseBuild: Liaison terminée.",
    "[2026.10.20-23.32.21:205][724]VerseBuild: SUCCÈS -- Version terminée."
  ],
  "success_lines": [
    "[2026.10.20-23.32.21:205][724]VerseBuild: Compilation terminée."
  ],
  "scope": "une liste de diagnostics vide ne suffit PAS : il faut aussi une ligne de succes recente dans VerseBuild. Les lignes sont localisees et le log garde les builds precedents : comparer l'horodatage a 2026-10-20T23:32:16.670455+00:00"
}
```

**Points de contrôle, dans cet ordre :**

1. `session` = `"Disconnected"` : `GetSessionStatus` est appelé **avant** `BuildAll`.
2. `error_diagnostics: []` **et** `diagnostics_count: 0`. Le `BuildAll` réel de ce run renvoie
   `{"returnValue":[]}` — une liste vide ne dit rien d'autre.
3. `success_lines` **non vide** et horodatée après le `timestamp` de l'appel. Le log garde les
   builds précédents : le run contient 5 blocs de 3 lignes (22.06.56, 22.06.58, 22.07.14, 22.07.18,
   23.32.21). Seule la ligne `[2026.10.20-23.32.21:205]` suit l'appel à `23:32:16` : les quatre
   autres sont des **restes** et ne prouvent rien.
4. `scope` est recopié tel quel dans mon handoff : c'est lui qui porte l'avertissement.

## 2. Le piège d'encodage (à connaître, pas à corriger)

Dans la console Windows (cp1252) les lignes s'affichent cassées :

```
[2026.10.20-23.32.21:205][724]VerseBuild: Compilation termin?e.
[2026.10.20-23.32.21:205][724]VerseBuild: SUCC?S -- Version termin?e.
```

**Lecture :** le fichier est en UTF-8 avec les libellés **localisés** de l'éditeur (`terminée`,
`SUCCÈS`) ; c'est l'affichage qui dégrade les octets, pas la donnée. Le détecteur du CLI est
`re.search(r"succ|termin|success|complete", t, re.IGNORECASE)` : il matche sur la racine ASCII,
donc il fonctionne malgré l'affichage. **Je ne « corrige » jamais un libellé qui paraît cassé** et
je ne compare pas l'affichage du terminal, je compare les octets du fichier.

## 3. Refus avant appel — `SESSION_CONNECTED` (code retour `1`, rien n'a tourné)

```json
{
  "status": "FAILED",
  "command": "verse-build",
  "error_kind": "SESSION_CONNECTED",
  "session": "InProgress",
  "detail": "BuildAll n'est prouve qu'avec une session Disconnected. Son comportement session connectee n'a jamais ete teste : ne pas lancer."
}
```

**Lecture :** `BuildAll` en session connectée est **inconnu**, pas « risqué » : `UNKNOWN`. Aucun
`09_verse_report.json` n'est écrit, rien n'est compilé. L'arrêt de session relève du Producteur
(gate HITL) — j'attends, je ne lance rien.

## 4. Échecs d'appel — les trois sorties que je sais lire

| Sortie brute | Code | Ce que ça veut dire | Conduite |
|---|---|---|---|
| `{"status":"FAILED","command":"verse-build","error_kind":"OFFLINE","error":"…connection refused…"}` | `2` | l'éditeur n'a pas reçu l'appel | vérifier UEFN ouvert + port (`8000` par défaut, pont observé sur `8001`) via `UEFN_MCP_URL` ; rejouer une fois |
| `{"status":"FAILED","command":"verse-build","error_kind":"TIMEOUT_OUTCOME_UNKNOWN","error":"timeout 60.0s : timed out","next":"Relire l'etat (find_actors, get_actor_transform) avant de rejouer."}` | `3` | **état inconnu** : le build a peut-être tourné | relire `Verse.BuildAll` suivant + log `VerseBuild` ; jamais relancer à l'aveugle |
| `{"status":"FAILED","command":"verse-build","error_kind":"TOOL_ERROR","error":"…","next":"L'appel a ete traite : relire l'etat (_placed.json, find_actors) avant de rejouer."}` | `1` | l'appel a été **traité** | lire les diagnostics et le log avant toute décision |

Observé sur le run de référence (`night_city_corpo_plaza`, 2026-10-24) pour un autre appel
(`SessionToolset.StartSession`) : `McpTimeout: timeout 60.0s : timed out` → code `3`. Le même
mécanisme s'applique à `verse-build` : un timeout **n'est pas** un échec de compilation.

## 5. Autour du build : ce que les autres appels renvoient vraiment

- `Verse.ListFiles {"path": "", "bRecursive": false}` → les 5 racines montées, dont
  `/1a52cfc2-8485-44f7-8516-3583d0b0c33c` (mon projet) et `/Fortnite.com (Fortnite)` (le digest).
- `Verse.ListFiles {"path": "/1a52cfc2-…", "bRecursive": true}` → `_verse_files.json`
  (`root`, `recursive`, `at`, `files`) : **63 entrées** ici, dont les `.verse` réels.
- `Verse.ReadFile {"path": "/1a52cfc2-…/game_manager_device.verse"}` **avant** écriture →
  `{"isError": true, "text": "file does not exist: '/1a52cfc2-…/game_manager_device.verse'."}`.
  C'est l'expected : `FILE_NOT_FOUND`, pas une anomalie.
- `Verse.WriteFile {path, content, bCreateIfMissing: true}` → `{"returnValue": null}`. **Le `null`
  ne prouve rien** : seule la relecture compte (`_verse_written.json`, `read_back_matches: true`,
  `bytes: 2442`).
- `Logs.GetLogEntries {"category": "VerseBuild", "pattern": "", "maxEntries": 15}` → le bloc de 15
  lignes ci-dessus. `Logs.GetLogEntries {"category": "Valkyrie"}` →
  `McpError: Logs.GetLogEntries : "Log category 'Valkyrie' not found."` ; les noms réels sont
  `LogValkyrie` / `LogValkyrieValidation` (à découvrir avec `Logs.GetLogCategories`).

## 6. Une compilation qui « passe » ne dit toujours rien

Le `BuildAll` du run renvoie `[]` alors que les diagnostics attendus en cas d'erreur sont des objets
`{"severity": "error", …}` : `error_diagnostics` filtre sur `severity == "error"`. **Aucun cas
d'échec de compilation n'a été observé dans les runs documentés** → la forme exacte d'un diagnostic
d'erreur est `UNKNOWN` ; je ne l'invente pas dans un handoff, je cite le log `VerseBuild` relu.
