# Tool output — armes, objets et réglages d'île (ItemSpawner, ItemGranter, IslandSettings)

> **Tool Outputs** (WP3 p.8). Sorties **réelles** du run `MyProjectArtyu` (1v1 build fight,
> 2026-10-29) via `ObjectTools.get_properties` / `set_properties` et `DeviceToolset`.
> Légalité des objets : `../../../_commun/legalite-assets.md` ; chemins prouvés :
> `../../../_commun/catalogue-verifie.json → acceptes.objets`.

## 0. Les 5 pièges qui cassent tout (à lire avant le reste)

| # | Signe | Cause | Conduite |
|---|---|---|---|
| 1 | Le device posé a `bIsFlag`, `captureItemTakenTag`… | `/CR_Legacy/Playsets/PID_CP_Devices_ItemSpawner` est le spawner de **drapeau (CTF)** | utiliser `/CreativeCoreDevices/SetupAssets/PID_Device_ItemSpawner` (classe `Device_ItemSpawner_V3_C`) |
| 2 | `set_properties` « réussit » mais rien ne change en jeu ; erreur citant `TRASH_Minigame_Spawner_Component_C_3` | chemin de composant **construit à la main** (`<acteur>.Minigame_Spawner_Component`) : après la pose, ce nom désigne une copie morte | **toujours** obtenir le composant par `get_properties(acteur, ["minigame_Spawner_Component"])` puis utiliser le `refPath` rendu |
| 3 | `ArrayAdd: elements changed alongside the size change; insertion points are ambiguous` | `set_properties` n'accepte qu'**un élément de plus par appel** sur un tableau ; écrire 15 éléments d'un coup en garde **1** sans erreur visible | vider (`[]`), puis boucle : relire le tableau → ajouter 1 élément → réécrire ; relire la taille à la fin |
| 4 | `… is not valid FortWorldItemDefinition (asset is FortGameFeatureData)` | chemin du **plugin** (`/Figment_Athena_Grenade/Figment_Athena_Grenade`) au lieu de l'objet | `AssetTools.get_asset_class` doit rendre `*ItemDefinition` ; code `WRONG_ASSET_CLASS` |
| 5 | l'éditeur accepte l'arme, la sauvegarde loggue `references disallowed object` | objet non exposé aux créateurs (`/BlastBerryWeapons`, `/Figment_*`…) | n'utiliser que `catalogue-verifie.json → acceptes.objets` ; sinon procédure de `legalite-assets.md` |

## 1. ItemSpawner (socle d'arme) — la liste vit sur un composant

```json
// get_properties(spawner, ["minigame_Spawner_Component"])
{"minigame_Spawner_Component": {"refPath": "/…/PersistentLevel.Device_ItemSpawner_V3_C_UAID_…_1736572870.Minigame_Spawner_Component"}}

// set_properties(<ce refPath>, {"toSpawnList": [ … ]}) — un élément par appel (piège 3)
// relecture d'un élément écrit :
{"pickupToSpawn": {"refPath": "/Game/Athena/Items/Weapons/WID_Shotgun_Standard_Athena_SR_Ore_T03.WID_Shotgun_Standard_Athena_SR_Ore_T03"},
 "pickupQuantity": 1,
 "itemVariantGuid": "00000000-0000-0000-0000-000000000000",
 "spawnTransform": {"location": {"x": 0, "y": 0, "z": 0}, "rotation": {"pitch": 0, "yaw": 0, "roll": 0}, "scale": {"x": 1, "y": 1, "z": 1}},
 "bHasLinkedWeapon": false}
```

**Lecture :** l'élément relu porte des champs ajoutés par le moteur (`itemVariantGuid`,
`spawnTransform`, `bHasLinkedWeapon`). Pour ajouter l'élément suivant, on renvoie le tableau
**relu** (avec ces champs) + le nouvel élément ; renvoyer une version « nettoyée » des anciens
éléments déclenche le piège 3.

`pickupItemList` du spawner (`get_properties(spawner, ["pickupItemList"])`) est **non lisible** sur
`Device_ItemSpawner_V3_C`, et celui de `creative_ItemPreview_Component` vaut `null` en éditeur :
ce ne sont pas les bons champs.

Options du socle (sur l'**acteur**, noms exacts avec espaces) — relues après écriture :

```json
{"respawn Item On Timer": true, "time Between Spawns": 15, "random Spawns": "No Repeats",
 "base Visible During Game": true, "bonus Ammo for Weapons": true}
```
`random Spawns` ∈ `Off | Random | No Repeats`. Autres options vues : `spawn Item On Timer`,
`time Before First Spawn`, `items Respawn`, `run Over Pickup`, `item Scale`, `enabled At Game Start`.

## 2. ItemGranter (équipement donné au joueur)

```json
// get_properties(granter, ["pickupItemList"])  → ici le composant EST le bon
{"pickupItemList": {"refPath": "/…/PersistentLevel.Device_ItemGranter_V2_C_UAID_…_1736239869.PickupItemList"}}
// set_properties(<ce refPath>, {"itemListData": [{"itemDefinition": {"refPath": "<WID>"}, "itemQuantity": 1}, …]})  — piège 3
```

Options relues :
```json
{"grant": "All Items", "onGrantAction": "Clear Items", "grantCondition": "Always", "bEquipGrantedItem": true}
```
`grant` ∈ `Current Item | All Items` ; `onGrantAction` ∈ `Clear Inventory | Clear Items |
Clear Resources | Keep All` ; `grantCondition` ∈ `Always | Only If Empty | Only If Space |
Only If Initially Empty | Only if Not Owned`.

**Câblage** (donner l'équipement à chaque apparition) :
```json
// GetBindingOptions(spawn pad) → {"sourceEvents": ["On Player Spawned", "OnSpawnFailed"], ...}
// GetBindingOptions(granter)   → {"targetFunctions": ["Enable","Disable","GrantItem","CycleToPreviousItem",
//                                  "CycleToNextItem","CycleToRandomItem","RestockItems","ClearSaveDataForPlayer"]}
AddEventBinding {"sourceDevicePath": <pad>, "sourceEvent": "On Player Spawned",
                 "targetDevicePath": <granter>, "targetFunction": "GrantItem"}
// relecture : ListEventBindings(granter) liste un lien par pad
```

## 3. IslandSettings (règles de la partie) — acteur `IslandSettings_0`

Écrire **une propriété par appel** et collecter les refus : un seul refus fait échouer le script
entier même si les autres propriétés ont été appliquées. Toujours **relire** ensuite.

Profil 1v1 build fight relu le 2026-10-29 :
```json
{"maxPlayers": 2, "teamSize": "Solos", "spawnLimit": 1, "spawnLimit_Override": true,
 "totalRounds": 9, "bEndGameOnMatchPointWin": true, "gameWinCondition": "MostRoundWins",
 "roundWinCondition": "Eliminations", "roundTimeLimit": 5, "hUDInfoType": "Round Status",
 "gameStartCountdown": 3, "bInfiniteBuildingResources": true, "bInfiniteResources": true,
 "bInfiniteAmmo": true, "maximumResources": 999, "startingShieldPercentage": 100,
 "dropAllItemsOverride": "ForceDestroy", "autoPickupWeaponItems": "IsTrue",
 "timeOfDayOverride": "ForceDay", "spawnImmunityTime": 2, "respawnTime": 1,
 "environmentDamagePreset": "Player Built Only"}
```

Pièges :
- Plusieurs réglages n'ont d'effet qu'avec leur drapeau `*_Override` à `true` (`spawnLimit_Override`,
  `roundWinCondition_Override`, `roundTimeLimit_Override`, `hudInfoType_Override` — attention à la
  casse : `hUDInfoType` mais `hudInfoType_Override`).
- `bFallDamage` est **refusé en écriture** (`the following properties could not be set: bFallDamage`) ;
  les dégâts de chute passent par `fallDamageMultiplier` / `fallDamageType`.
- `spawnImmunityTime` ne s'applique qu'avec `bOverrideSpawnImmunityTime: true`.

## 4. Échecs reconnus

| Sortie brute | Code | Conduite |
|---|---|---|
| `… could not be read: pickupItemList` (ItemSpawner) | 1 | mauvais champ : passer par `minigame_Spawner_Component` (§1) |
| `'NoneType' object is not subscriptable` sur `creative_ItemPreview_Component.pickupItemList` | 1 | champ `null` en éditeur ; même conduite |
| `ArrayAdd: … insertion points are ambiguous` | 1 | piège 3 : écriture élément par élément |
| `is not valid FortWorldItemDefinition (asset is FortGameFeatureData)` | 1 | `WRONG_ASSET_CLASS` : prendre l'objet sous `.../Gameplay/` |
| `references disallowed object <chemin>` dans le journal après sauvegarde | 1 | `ILLEGAL_ASSET_PATH` : retirer, remplacer par un objet du catalogue, re-sauvegarder, relire |
| tableau relu de taille 1 après une écriture de N éléments | 1 | écriture silencieusement tronquée : refaire élément par élément |
