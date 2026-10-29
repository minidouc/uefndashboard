# Tool output — `apply-properties`

> **Tool Outputs** (WP3 p.8). Le rapport qui décide si une valeur d'ambiance est **appliquée** ou
> simplement **espérée**. Formes réelles du run UEFN documenté (2026-10-24) et du code
> `script/uefn_spatial_cli.py` (`cmd_apply_properties`).

## 1. `07_properties_report.json` — la sortie **réelle** du run de référence

```json
{
  "timestamp": "2026-10-23T22:38:31.874791+00:00",
  "status": "PASSED",
  "error_count": 0,
  "applied": [],
  "errors": [],
  "not_placed": [],
  "scope": "chaque valeur ecrite par set_properties est relue par get_properties ; les devices Verse (SetDeviceProperty) ne sont pas couverts : outil inconnu, jamais teste sur un creative_device"
}
```

**Lecture :** un PASSED **vide** est un état documenté, pas une victoire. Ici `04_devices.json` ne
portait aucune clé `properties`, donc **rien n'a été écrit** — le `scope` le dit et il faut le
reprendre tel quel dans le handoff. Le point qui compte pour moi : la partie « **les devices Verse
ne sont pas couverts** » (outil inconnu, jamais testé sur un `creative_device`).

## 2. Avant d'écrire : `--dry-run`

```json
{
  "status": "DRY_RUN",
  "command": "apply-properties",
  "devices": 3,
  "properties": 7,
  "not_placed": [
    { "type": "NOT_PLACED", "actor": "Lamp_Ambiance_Nord",
      "detail": "place-scene n'a pas pose cet acteur (absent de _placed.json)" }
  ],
  "next": "list_properties puis set_properties (values en CHAINE JSON) puis get_properties : une erreur peut accompagner une ecriture partielle."
}
```

**Lecture :** `DRY_RUN` n'a **aucun** effet de bord. `not_placed` = l'acteur n'existe pas dans
`_placed.json` : ce n'est pas à moi de le poser (`Physics_Programmer`), et un rapport « PASSED » avec
des `not_placed` n'existe pas — le CLI compte ces lignes dans `error_count` et sort en code `1`.

## 3. Une ligne `applied` (forme émise par le CLI — le run de référence a rendu `applied: []`)

```json
{ "actor": "Lamp_01", "property": "intensity", "written": 1200.0, "read_back": 1200.0 }
```

**Ce que le validateur exige** (`value_matches`) :

- flottables : égalité à `1e-6` près — un `written: 0.35` relu `0.3499999` passe, un `0.4` échoue ;
- booléens : comparaison booléenne stricte ;
- dictionnaires (couleur, vecteur) : ** chaque clé écrite doit être confirmée** dans ce qui est relu,
  des clés en plus côté éditeur sont acceptées (`teamIndex` seul relu avec `teamType` — constat du
  2026-10-19) ;
- `get_properties` renvoie une **chaîne JSON** : le CLI la décode, une décodée vide ≠ « sans valeur ».

## 4. Les trois échecs de propriété que je sais distinguer

```json
{ "type": "PROPERTY_NOT_FOUND", "actor": "Skydome_Ambiance_01", "properties": ["TimeOfDay"],
  "nearest": { "TimeOfDay": [] },
  "detail": "absentes de list_properties : ne pas inventer un autre nom" }
```

```json
{ "type": "PROPERTY_MISMATCH", "actor": "Lamp_01", "property": "intensity",
  "written": 1200.0, "read_back": 0.0 }
```

```json
{ "type": "PROPERTY_UNREADABLE", "actor": "Lamp_01", "property": "lightColor",
  "written": { "r": 0.85, "g": 0.4, "b": 0.15 }, "read_back": null,
  "detail": "get_properties ne renvoie pas la cle : valeur inconnue, pas valeur absente" }
```

| Type | Ce que ça veut dire | Conduite |
|---|---|---|
| `PROPERTY_NOT_FOUND` | la propriété n'existe **pas** sur cet acteur (`list_properties` ne la rend pas) | je n'écris rien ; `nearest` est une **indication**, pas une autorisation ; la ligne va dans `properties_tentees` en `NOT_FOUND` |
| `PROPERTY_MISMATCH` | écrit, relu **différent** | une passe de correction ; si le delta persiste, le device n'écoute pas cette propriété → `UNKNOWN` + remontée |
| `PROPERTY_UNREADABLE` | la clé n'est pas revenue à la relecture | **valeur inconnue** : jamais « appliquée », jamais « absente » |
| `NOT_PLACED` | l'acteur absent de `_placed.json` | pose hors périmètre → Producteur → `Physics_Programmer` |

Nota : quand `PROPERTY_NOT_FOUND` frappe, le CLI **retire** ces propriétés du lot ; si le lot devient
vide, l'acteur est **silencieusement ignoré** (`continue`). D'où l'obligation de consigner chaque
tentative dans `05_visuals.json`, pas seulement les succès.

## 5. Pannes de pont (mêmes messages que l'ANNEXE B du journal)

| Sortie | Code | Signification | Conduite |
|---|---|---|---|
| `{"status": "FAILED", "command": "apply-properties", "error_kind": "OFFLINE", "error": "editeur injoignable sur http://127.0.0.1:8000/mcp"}` | **2** | pont absent **ou** sur un autre port (le run documenté tournait sur **8001**) | vérifier `UEFN_MCP_URL` ; **rien n'a été écrit** |
| `{"error_kind": "TIMEOUT_OUTCOME_UNKNOWN", "error": "timeout 60.0s : timed out"}` ou `WinError 10054`, avec `applied_before_failure` / `errors_before_failure` | **3** | écriture peut-être passée sans réponse | `next` du CLI : « Relire l'etat (find_actors, get_actor_transform) avant de rejouer. » |
| `{"error_kind": "TOOL_ERROR", "next": "L'appel a ete traite : relire l'etat (_placed.json, find_actors) avant de rejouer."}` | **1** | appel **traité** avec erreur | relire, ne pas rejouer le lot entier |
| sortie catalogue > 4 000 tokens (ex. `list_toolsets` 790,8 Ko → « Output too large ») | — | payload ingérable | fichier sur disque + Grep ciblé, **chemin seulement** dans le handoff |

## 6. Ce que cet outil ne **peut** pas faire

- aucun outil MCP lumière / émissif / Lumen / terrain / foliage dans les 388 inventoriés :
  `apply-properties` ne **règle** que ce qui est déjà posé et exposé ;
- `Device.SetDeviceProperty` (devices Verse) : **non couvert**, `UNKNOWN` ;
- `MaterialInstanceTools.set_*` : DANGEREUX_NON_TESTE, hors allowlist sans accord Engine + Producer ;
- un réglage fait à la main dans l'éditeur n'apparaît **jamais** ici : c'est exactement pour ça que le
  rapport est la seule preuve qui compte.
