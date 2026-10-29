# Tool output — `list-editables` et `wire-devices`

> **Tool Outputs** (WP3 p.8). Forme **réelle** des deux rapports de câblage du run UEFN documenté
> `1v1-buildfight` (2026-10-21) : `10_editables.json` (6 `@editable`) et `08_wiring_report.json`
> (1 lien prouvé). Codes retour : `0` PASSED · `1` FAILED (**appel traité**) · `2` OFFLINE ·
> `3` TIMEOUT / état inconnu.

## 1. `10_editables.json` — PASSED (ce que je rends)

```json
{
  "timestamp": "2026-10-21T00:01:13.192879+00:00",
  "command": "list-editables",
  "status": "PASSED",
  "editable_count": 6,
  "actor_references": 5,
  "parameters": 1,
  "without_target": [],
  "mapping": [
    {
      "file": "game_manager_device.verse",
      "editable": "DebugSelfTest",
      "type": "logic",
      "kind": "PARAMETRE",
      "declared_in_04_devices": false,
      "asset_key": null,
      "refPath": null,
      "wiring": "AUCUNE_CIBLE"
    },
    {
      "file": "game_manager_device.verse",
      "editable": "Spawner_P1_01",
      "type": "player_spawner_device",
      "kind": "ACTEUR",
      "declared_in_04_devices": true,
      "asset_key": "player_spawner",
      "refPath": "/1a52cfc2-8485-44f7-8516-3583d0b0c33c/testmcp.testmcp:PersistentLevel.BP_Creative_Player_Spawner_Prop_C_UAID_00FFA9FB53741B0D03_1543002450",
      "wiring": "MANUEL"
    }
  ],
  "live": null,
  "scope": "seules les references d'ACTEUR doivent viser un acteur pose : un @editable de type primitif (logic, int, float...) est un parametre a regler, pas une cible. Le cablage automatique des references d'acteurs est UNKNOWN : cette liste sert a cabler a la main dans l'editeur."
}
```

**Lecture :**

1. `without_target: []` = chaque référence d'**acteur** a un `refPath` dans `_placed.json`. Ça ne
   dit **pas** que le lien est écrit dans le device.
2. `wiring: "MANUEL"` sur les 5 lignes ACTEUR = **câblage non prouvé** (aucun `--apply` sur ce run).
   Seul `AUTO_VERIFIED` prouve : écrit **puis relu**. Annoncer ces lignes comme « câblées » est un
   rejet automatique.
3. `DebugSelfTest` est un `PARAMETRE` (`logic` ∈ `PARAM_TYPES`) → `AUCUNE_CIBLE`, `refPath: null`,
   `declared_in_04_devices: false` : normal, rien à câbler.
4. `live: null` : aucun `--live` demandé ; la table vient des fichiers, pas de l'éditeur.

## 2. `08_wiring_report.json` — PASSED avec preuve sur la **cible**

```json
{
  "timestamp": "2026-10-21T00:01:09.624480+00:00",
  "status": "PASSED",
  "error_count": 0,
  "wired": [
    {
      "from": "Round_Timer_01",
      "event": "OnSuccess",
      "to": "Barrier_Center_01",
      "function": "Disable",
      "read_back": {
        "sourceDevicePath": {"refPath": "…Device_Timer_V2_C_UAID_00FFA9FB53741B0D03_1558002467"},
        "sourceEvent": "OnSuccess",
        "targetDevicePath": {"refPath": "…Device_Barrier_V2_Placed_C_UAID_00FFA9FB53741B0D03_1715543676"},
        "targetFunction": "Disable"
      }
    }
  ],
  "errors": [],
  "not_placed": [],
  "scope": "cablage evenement -> fonction entre devices poses. Le cablage par canal (GameplayTagContainer) et les references @editable ne sont pas couverts."
}
```

**Lecture :** `AddEventBinding` renvoie `{"returnValue": null}` → **aucune preuve**. La seule preuve
est le `read_back` issu de `Device.ListEventBindings` appelé sur le device **cible**
(`Barrier_Center_01`), pas sur l'émetteur. Le `scope` dit aussi ce qui n'est **pas** couvert :
canaux `GameplayTagContainer` et références `@editable`.

## 3. Les échecs que je dois savoir reconnaître

| Sortie | Code | Signification | Conduite |
|---|---|---|---|
| `{"status":"FAILED","command":"list-editables","error_count":1,"errors":[{"type":"NO_VERSE_STAGED","verse_dir":"…\\verse","detail":"aucun .verse dans workspace/verse/ : le gabarit en fournit un, ou ecrire le fichier d'abord"}]}` | `1` | rien à lister | sur une scène sans module personnalisé c'est **normal** (run `night_city_corpo_plaza`) : le dire, ne pas inventer de table |
| `{"…","errors":[{"type":"DEVICE_NOT_PLACED","device":"game_manager_device_0"}]}` | `1` | le `creative_device` Verse n'est pas posé / pas trouvé | câblage `--apply` impossible ; la relecture `--live` non plus. Je le signale, je ne pose rien (pose = agent 16) |
| `{"…","wiring_errors":[{"type":"EDITABLE_PROPERTY_NOT_FOUND","editable":"…","available":[…]}]}` | `1` | le nom déclaré n'existe pas dans `Device.ListDeviceProperties` | je **corrige le `@editable` dans mon `.verse`**, je ne renomme pas le device ; `available` donne la liste réelle |
| `{"…","wiring_errors":[{"type":"EDITABLE_READBACK_MISMATCH", …}]}` / `SET_DEVICE_PROPERTY_FAILED` | `1` | écrit puis relu différent / erreur d'écriture | ligne ACTEUR restée `MANUEL` ; DeviceToolset `SetDeviceProperty` = statut **inconnu** sur un `creative_device` |
| `{"status":"FAILED","command":"wire-devices","error_count":1,"errors":[{"type":"NO_BINDING_DECLARED","detail":"aucun `bindings` dans 04_devices.json. Les noms d'evenement et de fonction se lisent avec Device.GetBindingOptions sur la source : ne jamais les deviner (ou passer --allow-empty si toute la logique passe par Verse)."}],"wired":[],"not_placed":[]}` | `1` | rien à câbler en Direct Event | si la logique est en Verse : `--allow-empty` → PASSED honnête, sinon handoff `BLOCKED` |
| `{"type":"BINDING_EVENT_UNKNOWN","from":"Round_Timer_01","event":"OnFinished","sourceEvents":["OnSuccess","OnFailure","OnStartUrgencyMode","On Saved","On Loaded","On Cleared"]}` | `1` | événement inventé | je reprends un nom **dans** `sourceEvents`, jamais l'inverse |
| `{"type":"BINDING_FUNCTION_UNKNOWN","to":"…","function":"Stop","targetFunctions":[…]}` | `1` | fonction absente des `targetFunctions` de la cible | même règle : lire `GetBindingOptions` sur la cible |
| `{"type":"BINDING_NOT_READ_BACK", …, "detail":"le lien apparait sur la CIBLE : s'il n'y est pas, il n'est pas prouve (AddEventBinding est idempotent, rejouer sans risque)"}` | `1` | lien **non prouvé** | relire sur la cible ; `AddEventBinding` idempotent → rejouer est sans risque |
| `not_placed: [{"from":"…","to":"…"}]` | `1` | label absent de `_placed.json` | aucun appel éditeur n'a touché ces devices ; alerter le Producteur, ne pas créer de `refPath` |

## 4. `GetBindingOptions` : la liste réelle, telle que rendue

```json
{"returnValue": {
  "sourceEvents": ["OnSuccess","OnFailure","OnStartUrgencyMode","On Saved","On Loaded","On Cleared"],
  "targetFunctions": ["Start","Complete","Reset","Pause","Resume","Enable","Disable",
    "SetLapTimeForPlayer","StartForAll","PauseForAll","ResumeForAll","CompleteForAll",
    "ResetForAll","SetLapTimeForAll","Save","Load","ClearPersistenceData",
    "ClearPersistenceDataForAll","Save For All","Load For All"]}}
```

`timer_device` ci-dessus (`Device_Timer_V2_C_…_1558002467`). À comparer :
`player_spawner_device` → `sourceEvents: ["On Player Spawned","OnSpawnFailed"]`,
`targetFunctions: ["Enable","Disable","SpawnPlayer"]` ; `barrier_device` → `sourceEvents: []`
(jamais émetteur), `targetFunctions: ["Enable","Disable","AddPlayerToIgnoreList", …]` ;
`item_granter_device` → `["OnItemGranted","OnItemGrantedWithCount"]` /
`["Enable","Disable","GrantItem","CycleToPreviousItem","CycleToNextItem","CycleToRandomItem",
"RestockItems","ClearSaveDataForPlayer"]`.

**Lecture :** les noms sont **tels quels**, y compris les espaces (`On Saved`, `Save For All`) —
les recopier exactement. Un `sourceEvents: []` interdit d'utiliser le device comme émetteur.

## 5. `--apply` : ce que le CLI ferait, et pourquoi je ne l'appelle pas seul

`list-editables --apply` écrit sur le device posé
`Object.set_properties {"instance": …, "values": "{\"savedActor\": {\"refPath\": \"…\"}}"}`
puis relit (`get_properties`) pour marquer `AUTO_VERIFIED`. Trois précautions :

- **gate** : accord explicite du Producteur (l'utilisateur) préalable — l'écriture touche le projet ;
- `values` est une **chaîne JSON**, pas un objet (sinon
  `Function "set_properties", input param "values" is required by the function input schema Json,
  but is missing…`) ;
- l'hypothèse `savedActor` n'a **jamais** été prouvée sur un `creative_device` de ce projet →
  sans relecture, le statut reste `UNKNOWN` et la ligne reste `MANUEL`.

## 6. Erreurs brutes d'éditeur rencontrées autour du câblage

```
Parameter error: /CRD_PlayerSpawn/ItemDefinitions/PID_CP_Devices_PlayerSpawner is not a valid
object path for property 'AssetPath'.        ← PlaceDevice (agent 16), asset sans sous-objet
GetObjectProperties on '…DirectionalLight' (DirectionalLightComponent): the following properties
could not be read: sourceAngle               ← une propriété lisible n'est pas garantie
Unknown tool get_property / spawn_actor / place_asset
Toolset 'rpc' not found
```

**Lecture :** après une erreur, **relire avant de conclure** : `set_properties` peut appliquer une
partie des valeurs tout en rendant `isError` (`SetObjectProperties on '…Device_Skydome_V2_C…':
the following properties could not be set: fogDensity, fogFalloff`). Une sortie vide (`[]`, `null`,
`{}`) = `UNKNOWN`, jamais « ça a marché ».
