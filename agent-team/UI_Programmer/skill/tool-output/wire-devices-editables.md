# Tool output — `list-editables` et `wire-devices`

> **Tool Outputs** (WP3 p.8). Les deux rapports qui disent si l'interface est **rattachable** au
> reste de la carte. Formes réelles du run UEFN documenté (2026-10-24) et du code
> `script/uefn_spatial_cli.py`.

## 1. `10_editables.json` — table `@editable` → cible

Version **réelle** du run de référence (aucun module Verse écrit par décision de design ; rapport
produit **localement**, sans `--apply`, sans `Game_Manager_01`) :

```json
{
  "timestamp": "2026-10-23T22:52:57.576967+00:00",
  "command": "list-editables",
  "status": "PASSED",
  "editable_count": 0,
  "actor_references": 0,
  "parameters": 0,
  "without_target": [],
  "wiring_errors": [],
  "mapping": [],
  "live": {
    "custom_verse_modules": 0,
    "game_manager_created": false,
    "tool_result": "NO_VERSE_STAGED — non applicable à cette scène sans module personnalisé"
  },
  "scope": "Aucun Verse personnalisé et aucun @editable Corpo Plaza par décision de design. Aucun fichier Verse écrit, aucun --apply, aucun Game_Manager_01 créé."
}
```

Quand des `@editable` existent, chaque ligne de `mapping` a cette forme (CLI) :

```json
{
  "file": "ui_hud.verse",
  "editable": "PlayerSpawner",
  "type": "player_spawner_device",
  "kind": "ACTEUR",
  "declared_in_04_devices": true,
  "asset_key": "player_spawner",
  "refPath": "/dc587e05-…/claudtest.claudtest:PersistentLevel.BP_Creative_Player_Spawner_Prop_C_UAID_08F97E52BCAA090E03_1884200392",
  "wiring": "MANUEL"
}
```

**Lecture :**
- `kind` vient du type Verse : **`PARAMETRE`** pour `logic, bool, int, float, string, message,
  locale, type` (une valeur à régler dans l'éditeur), **`ACTEUR`** pour tout le reste (une cible à
  cabler). Seuls les `ACTEUR` sans `refPath` tombent dans `without_target` et font passer le rapport
  en `FAILED`.
- `wiring` : `MANUEL` = rien n'a été écrit ; `AUTO_VERIFIED` = écrit puis **relu**. Un `editable`
  dont le nom ne correspond à aucun `actor_label` posé n'est pas câblé pour autant.
- bloc `live` : présent seulement avec `--live` / `--apply`. Sans module stage, l'appel CLI échoue
  (`{"type": "NO_VERSE_STAGED", …}`, code `1`) : le documenter **n'est pas** un succès de câblage.
- avec `--apply` : le harnais écrit la cible dans la propriété `savedActor` du sous-objet
  `__verse_0x…_<Nom>` puis la relit. Erreurs propres à cette voie :
  `EDITABLE_PROPERTY_NOT_FOUND` (avec la liste `available`), `EDITABLE_READBACK_MISMATCH`
  (`written` vs `read_back`), `SET_DEVICE_PROPERTY_FAILED` (`SetDeviceProperty` **jamais** prouvé
  sur un `creative_device` → `UNKNOWN`, on le dit).

## 2. `08_wiring_report.json` — liens posés puis relus

Version **réelle** du run (`wire-devices --allow-empty`, code `0`) :

```json
{
  "timestamp": "2026-10-23T22:38:32.350460+00:00",
  "status": "PASSED",
  "error_count": 0,
  "wired": [],
  "errors": [],
  "not_placed": [],
  "scope": "aucun binding Direct Event declare (--allow-empty : logique cablee en Verse ou carte sans cablage)."
}
```

Avec des liens (`bindings` de `04_devices.json`), une ligne `wired` porte la **relecture** :

```json
{
  "from": "Input_Trigger_Menu", "event": "OnPressed",
  "to": "HUD_Manager_01", "function": "ShowMenu",
  "read_back": [ { "sourceEvent": "OnPressed", "targetFunction": "ShowMenu" } ]
}
```

et le `scope` rendu devient :

> « cablage evenement -> fonction entre devices poses. Le cablage par canal (GameplayTagContainer)
> et les references @editable ne sont pas couverts. »

**Points de contrôle :** `error_count` = 0 **et** `wired` non vide **et** chaque ligne a un
`read_back`. `wired: []` avec `--allow-empty` = « rien à câbler, déclaré » ; `wired: []` sans ce
drapeau = `NO_BINDING_DECLARED` (code `1`), pas un succès.

## 3. Échecs que je sais reconnaître

| Sortie | Signification | Conduite |
|---|---|---|
| code `1`, `{"type": "NO_BINDING_DECLARED", "detail": "aucun `bindings` dans 04_devices.json. Les noms d'evenement et de fonction se lisent avec Device.GetBindingOptions sur la source : ne jamais les deviner (ou passer --allow-empty si toute la logique passe par Verse)."}` | je veux câbler sans declaration amont | relire `04_devices.json`, ou passer `--allow-empty` **en le disant dans `scope`** ; jamais d'événement deviné |
| `{"type": "BINDING_EVENT_UNKNOWN", "from": …, "event": …, "sourceEvents": [...]}` | l'événement n'existe pas sur la source | reprendre un nom **dans** `sourceEvents` ; le `sourceEvents` rendu est la vérité éditeur |
| `{"type": "BINDING_FUNCTION_UNKNOWN", "to": …, "function": …, "targetFunctions": [...]}` | fonction absente sur la cible | idem avec `targetFunctions` ; si la fonction est la mienne → corriger **mon** `.verse`, rebuilder, recâbler |
| `{"type": "BINDING_NOT_READ_BACK", …, "target_bindings": [...]}` | `AddEventBinding` n'a rien produit de visible | le lien se prouve sur la **cible** (`ListEventBindings`) ; `AddEventBinding` est idempotent, rejouer est sans risque |
| `not_placed: [{"from": "…", "to": "…"}]` | acteur absent de `_placed.json` | ce n'est **pas** à moi de le poser → `Physics_Programmer` ; je consigne la liste telle quelle |
| code `2` `OFFLINE` / code `3` `TIMEOUT_OUTCOME_UNKNOWN` (`WinError 10054`) | rien de su, peut-être rien de fait | relire `ListEventBindings` avant toute reprise ; jamais « câblé » sans relecture |
| sortie > 4 000 tokens (ex. `list_toolsets` 790,8 Ko → « Output too large ») | payload ingérable | conservation dans un fichier, **chemin seulement** dans le handoff |
