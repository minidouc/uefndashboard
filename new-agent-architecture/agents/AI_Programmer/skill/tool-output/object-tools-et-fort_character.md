# Tool output — `ObjectTools` : lire/écrire une propriété d'un acteur (device Verse, `fort_character`)

> **Tool Outputs** (WP3 p.8). Forme **réelle** de ce que rend le pont MCP sur les propriétés,
> extraite des tests documentés du harnais (`mcp_tests/RAPPORT_MCP.md`, phase 4, device
> `PID_Device_Button`, classe `Device_Button_V2_C` ; 2026-10-19) et de
> `references/devices-catalog-and-wiring.md` §3-§6. Chemin d'acteur toujours écrit
> `{"refPath": "<chemin complet>"}`.

## 1. `Object.list_properties` — la liste réelle, pas celle de l'interface

```json
{
  "returnValue": [
    { "name": "bIsEnabled", "type": "logic" },
    { "name": "interaction Text", "type": "string" },
    { "name": "activatingTeam", "type": "CreativeTeamOption" }
  ]
}
```

**Lecture :** 331 propriétés relues sur le Button V2. Les noms **réels** peuvent contenir des
espaces (`interaction Text`) et ne suivent **pas** le libellé affiché dans l'éditeur. C'est cette
liste, et elle seule, qui autorise un `get_properties` / `set_properties` : je ne devine jamais un
nom, et `apply-properties` répond `PROPERTY_NOT_FOUND` avec des suggestions `nearest` **reprises de
cette liste**.

## 2. `Object.get_properties` — une chaîne JSON nom → valeur

```json
{
  "returnValue": "{\"bIsEnabled\":true,\"interaction Text\":\"Appuyez pour dash\",\"activatingTeam\":{\"teamType\":\"TeamIndex\",\"teamIndex\":2}}"
}
```

**Lecture :** la valeur est renvoyée **sous forme de chaîne JSON**, pas d'objet typé. Elle est à
parser avant toute comparaison. Une propriété illisible rend
`the following properties could not be read: <nom>` → je relis la liste, je n'invente pas un autre
nom.

## 3. `Object.set_properties` — `values` est une **chaîne JSON**, et toute écriture se relit

```json
{
  "instance": { "refPath": "/1a52cfc2-8485-44f7-8516-3583d0b0c33c/testmcp.testmcp:PersistentLevel.BP_Creative_Player_Spawner_Prop_C_UAID_00FFA9FB53741B0D03_1543002450" },
  "values": "{\"bIsEnabled\": false}"
}
```

Écritures **relues** lors de la campagne de tests (device Button V2, propriété `activatingTeam`) :

| j'écris | je relis |
|---|---|
| `{"teamIndex": 3}` | `{"teamType": "Any", "teamIndex": 3}` |
| `{"teamType": "TeamIndex", "teamIndex": 2}` | `{"teamType": "TeamIndex", "teamIndex": 2}` |
| `{"teamType": "All"}` | `{"teamType": "All", "teamIndex": <inchangé>}` |
| `{"teamType": "Specific", "teamIndex": 5}` (hors enum) | **erreur**, mais relu `{"teamType": "Any", "teamIndex": 5}` |

**Lecture :** la dernière ligne est le piège central de ce rôle — **une erreur peut accompagner une
écriture partielle**. On relit `get_properties` **même quand l'appel a échoué**, et on n'écrit un
`teamType` qu'avec une valeur déjà observée comme relue sur un device du même type.

## 4. Propriétés d'un `creative_device` Verse (mes mécaniques posées)

- `Device.ListDeviceProperties` / `GetDeviceProperties` / `SetDeviceProperty` sur un device Verse :
  statut **« inconnu »** (jamais revérifiés hors le flux `list-editables --apply`). Sur un device
  **natif**, ils répondent `is not valid ScriptDevice for property 'Device'` : ObjectTools seulement.
- Le câblage d'une référence `@editable` passe par `Object.set_properties` avec
  `{"savedActor": {"refPath": "<cible>"}}` puis relecture par `get_properties` → la ligne repasse en
  `AUTO_VERIFIED` dans `10_editables.json`. Sans relecture : `MANUEL`, et `wired_devices_count` ne
  compte **rien**.
- Effets sur le `fort_character` (`Damage`, `Hide`, `Show`, `PutInStasis`, `MoveTo`) : **aucune**
  passe par ObjectTools. Ils passent par le code Verse, donc par une signature vérifiée dans le
  digest (`verse-grep`) avant d'être appelée. Un acteur de type `fort_character` en jeu ne se règle
  pas à la main dans l'Outliner.

## 5. Échecs que je reconnais, avec le message exact et le code

| Sortie brute (exacte) | Code | Ce que ça veut dire | Conduite |
|---|---|---|---|
| `{"type": "NO_VERSE_STAGED", "detail": "aucun .verse dans workspace/verse/"}` (ANNEXE B n°8, 2026-10-24) | `1` | rien n'est stageable : `list-editables` n'a **pas** de matière | rapport écrit localement, périmètre explicité, `--apply` **jamais** ; ce n'est pas une anomalie d'éditeur |
| `Error: File does not exist.` sur la lecture de `12_session_report.json` (ANNEXE B n°10) | — | le CLI a **timeouté avant d'écrire** le rapport | aucune conclusion sur un comportement en jeu : le rapport est à produire à la reprise du flux |
| `McpError: Logs.GetLogEntries : "Log category 'Valkyrie' not found."` (ANNEXE B n°11) | `1` | la catégorie littérale n'existe pas | `Logs.GetLogCategories {"filter":"Valkyrie"}` → catégories réelles `LogValkyrie`, `LogValkyrieValidation`, puis lecture de ces catégories (pour la compilation : `VerseBuild`) |
| `WinError 10054` pendant une écriture (ANNEXE B n°2) | `3` | déconnexion transitoire du pont : **l'écriture a pu passer** sans réponse | relire `get_properties` avant toute décision ; un acteur orphelin se supprime **par `refPath`**, jamais par un nom supposé |
| `{"error_kind":"OFFLINE","error":"editeur injoignable sur http://127.0.0.1:8000/mcp"}` (ANNEXE B n°1) | `2` | pont actif sur `8001` et non `8000` | `export UEFN_MCP_URL="http://127.0.0.1:8001/mcp"` ; **rien n'a été exécuté** : on peut rejouer |
| `{"isError": true, "text": "file does not exist: '/1a52cfc2-…/special_mechanics.verse'."}` | — | fichier pas encore écrit | attendu avant le premier `verse-write` ; `FILE_NOT_FOUND`, pas une anomalie |

## 6. Ce qu'aucune de ces sorties ne prouve

Une propriété relue conforme ne dit **rien** du comportement en jeu : elle dit que la valeur est
écrite. Un binding posé ne dit pas que le device réagit. La seule preuve d'un comportement observé
est un `12_session_report.json` `PASSED` avec journaux client relus — et la session relève du
Producteur, pas de moi.
