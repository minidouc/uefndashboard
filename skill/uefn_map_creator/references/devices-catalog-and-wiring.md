# Devices UEFN : pose, proprietes, equipe, cablage

Statuts issus des tests du 2026-10-19 (`mcp_tests/RAPPORT_MCP.md`, phase 4, devices `PID_Device_Button`, classe `Device_Button_V2_C`).
Tout ce qui n'est pas marque **proven** est a verifier dans l'editeur avant usage.
Dans les arguments, un chemin d'acteur s'ecrit toujours `{"refPath": "<chemin complet>"}`.

## 1. Trouver le chemin d'un device

- Ne jamais deviner un chemin. Lancer `Device.ListDeviceAssets {"nameFilter": "<mot>"}` (proven) et prendre `assetPath`.
- Forme attendue : `/Plugin/Dossier/PID_Nom.PID_Nom` (chemin de paquet + `.` + nom d'objet).
- Plusieurs entrees peuvent correspondre au meme device. Exemple observe : `ListDeviceAssets("Button")` renvoie `/CR_Legacy/Playsets/PID_CP_Devices_CreativeButton.PID_CP_Devices_CreativeButton`, alors que le bouton pose pendant les tests etait `/CreativeCoreDevices/SetupAssets/PID_Device_Button.PID_Device_Button`. Leur equivalence n'est pas prouvee : poser, puis lire la classe (`Object.get_class {"instance"}`).
- Un `nameFilter` sans resultat renvoie `[]` sans erreur : cela ne prouve pas que le device n'existe pas.
- Inscrire le chemin retenu dans `02_palette.json` (`uefn_path`, `category: "DEVICE_..."`), puis lancer `measure-palette`.

## 2. Poser un device

- `Device.PlaceDevice {"assetPath": {"refPath": "<chemin>"}, "transform": {...}}` (proven) renvoie `{"refPath"}`.
- **Piege prouve** : le yaw demande est ignore (yaw 0 demande, yaw 90 relu). Toujours enchainer `Actor.set_actor_transform`, puis relire avec `get_actor_transform`. `place-scene` et `measure-palette` le font.
- `measure-palette` mesure a yaw 0 et rejette la mesure si le yaw relu n'est pas 0 ; `place-scene` force la transform puis la relit. Les devices et les props sont donc dans le meme referentiel.
- `PlaceDevice` ne pose pas de label : le CLI appelle `set_label`, puis `add_tag`, juste apres. Un timeout entre les deux laisse un device anonyme (voir `mcp-routing.md`, section 6).
- Taille et pivot : seulement par `measure-palette` (bounds relus a yaw 0). Les tailles des anciennes notes ne sont pas des mesures de cette campagne.

## 3. Lire et regler les proprietes

**Device natif (Creatif V2, non Verse) : ObjectTools seulement.**

| outil | statut | constat |
|---|---|---|
| `Object.list_properties {"instance"}` | proven | 331 proprietes sur le Button V2 |
| `Object.get_properties {"instance", "properties": ["bIsEnabled", "interaction Text"]}` | proven | renvoie une chaine JSON nom -> valeur |
| `Object.set_properties {"instance", "values": "{\"bIsEnabled\": false}"}` | proven | `values` est une **chaine JSON**, pas un objet |
| `Device.ListDeviceProperties` / `GetDeviceProperties` / `SetDeviceProperty {"device", "propertyName", "value"}` | unknown | sur un device natif : « is not valid ScriptDevice for property 'Device' ». Reserve aux devices Verse ; jamais teste sur un device Verse |

Regles :
- Toujours lancer `list_properties` d'abord : les noms reels contiennent parfois des espaces (`interaction Text`) et ne suivent pas le libelle de l'interface.
- Toujours relire avec `get_properties` apres `set_properties`, **meme en cas d'erreur** : une erreur peut accompagner une ecriture partielle.
- Si une propriete est illisible (« the following properties could not be read: <nom> »), ne pas inventer un autre nom : relire la liste.

## 4. Equipe (CreativeTeamOption)

Prouve sur `activatingTeam` du Button V2 :

| ecrit | relu |
|---|---|
| `{"teamIndex": 3}` | `{"teamType": "Any", "teamIndex": 3}` |
| `{"teamType": "TeamIndex", "teamIndex": 2}` | `{"teamType": "TeamIndex", "teamIndex": 2}` |
| `{"teamType": "All"}` | `{"teamType": "All", "teamIndex": <inchange>}` |
| `{"teamType": "Specific", "teamIndex": 5}` (hors enum) | **erreur**, mais relu `{"teamType": "Any", "teamIndex": 5}` |

- Ecrire `teamType` **et** `teamIndex` ensemble, avec une valeur d'enum deja relue sur un device du meme type.
- Valeurs vues : `Any`, `TeamIndex`, `All`. Toute autre valeur (ex. `ActivatingTeam`) est a verifier sur le device cible.
- Le nom du champ d'equipe change selon le device (`activatingTeam` sur le bouton) : le trouver avec `list_properties`.

## 5. Cablage evenement -> fonction (proven)

1. `Device.GetBindingOptions {"devicePath": {"refPath": "<source>"}}` -> `{"sourceEvents": ["On Interact"], "targetFunctions": ["Enable", "Disable"]}`. Utiliser ces chaines exactes.
2. `Device.AddEventBinding {"sourceDevicePath", "sourceEvent", "targetDevicePath", "targetFunction"}`. Il est idempotent : un second appel identique ne cree pas de doublon.
3. `Device.ListEventBindings {"devicePath": <CIBLE>}` : le lien apparait sur le device **cible**, pas sur la source.
4. `Device.RemoveEventBinding` (memes arguments) renvoie `null` : relire `ListEventBindings` pour confirmer.

Cablage par canal : non prouve. Un essai anterieur avec un entier a echoue ; le champ attendrait un `GameplayTagContainer`.

## 6. References @editable d'un device Verse (savedActor) : UNKNOWN

Hypothese non verifiee : chaque `@editable` d'un `creative_device` Verse aurait un sous-objet `__verse_0x<HASH>` portant une propriete `savedActor`.
Le projet de test ne contenait aucun device Verse : l'hypothese n'a pas pu etre testee.

Si l'utilisateur accepte de la tester (il faut alors ecrire et compiler du Verse) :
1. `Object.list_properties` sur le composant script du device Verse pose ; relever les vrais noms. Ne jamais deviner un hash.
2. `Object.set_properties {"instance": {"refPath": "<sous-objet>"}, "values": "{\"savedActor\": \"<refPath cible>\"}"}`.
3. `Object.get_properties {"instance", "properties": ["savedActor"]}` doit renvoyer la cible.
4. Essayer aussi `Device.SetDeviceProperty` (unknown) et noter lequel marche.
5. `Verse.BuildAll` doit finir sans erreur.

Tant que ce n'est pas fait, dire a l'utilisateur que les `@editable` se cablent a la main dans l'editeur.

## 7. Fiches de devices : NON VERIFIEES

Les chemins et noms de proprietes ci-dessous viennent d'anciennes notes. Aucun n'a ete relu pendant la campagne. Ils servent de piste de recherche.
Avant usage : `ListDeviceAssets`, `measure-palette`, `list_properties`, puis relecture de chaque valeur ecrite.

| device | chemin note | proprietes notees |
|---|---|---|
| player_spawner_device | `/CRD_PlayerSpawn/ItemDefinitions/PID_CP_Devices_PlayerSpawner` | `playerTeam {teamType: "TeamIndex", teamIndex: N}`, `visibleInGame: false`, `enabledDuringPhase: "Always"` |
| item_granter_device | `/CreativeCoreDevices/SetupAssets/PID_Device_ItemGranter` | granter 1 : `onGrantAction: "Clear Inventory"`, `bEquipGrantedItem: true` ; suivants : `"Keep All"`, `false` ; `grantCondition: "Always"`, `bGrantOnGameStart: false` |
| explosive_device | `/CreativeCoreDevices/SetupAssets/PID_Device_ExplosiveBarrel` | `blast Radius`, `player Damage: 0`, `structure Damage`, `visible During Game: false`, `can be Damaged: false` |
| score_manager_device | `/CreativeCoreDevices/SetupAssets/PID_Device_ScoreManager` | |
| end_game_device | `/CRD_GameEnd/SetupAssets/PID_Device_EndGame_V2` | `whatToEnd: "EndGame"`, `winningTeam` (valeur `ActivatingTeam` hors des valeurs vues) |
| hud_message_device | `/CreativeCoreDevices/SetupAssets/PID_Device_HUDMessage` | `showForDuration: false`, `placement: "Top Center"`, `showOnRoundStart: false` |
| barrier_device | a chercher | `Enable()` / `Disable()` depuis Verse |

Regles de jeu reprises des notes (logique Verse, pas des faits d'editeur) :
- Teleportation vers un spawner : ajouter environ 100 cm en Z pour ne pas traverser le sol.
- Plusieurs granters : attendre `ItemGrantedEvent` du granter 1 avant d'appeler le granter 2, sinon `Clear Inventory` peut effacer la seconde arme.
- Reset des constructions par barils : la portee d'un baril est limitee. Poser un baril central en plus de ceux des coins.
- Barriere : `Enable()` pendant le compte a rebours, `Disable()` a la fin du compte.

## 8. Armes (item_granter) : hors perimetre, rien de prouve

- Ce skill ne traite pas la legalite des assets. Aucune liste blanche d'armes n'a ete validee.
- Rapporte par l'utilisateur, non reverifie : `WID_Figment_Assault_Auto_Athena_SR` a ete refuse a la publication. Les autres `WID_` des anciennes notes (dont des `WID_Figment_*` notes « valides ») n'ont aucune preuve.
- Aucun outil `validate_selected` / `validate_folder` n'est prouve via MCP. Proposer a l'utilisateur de lancer la validation dans l'editeur. Ne pas accepter une correction automatique qui viderait le granter.
- Un `WID_` ne se pose pas dans la scene : il s'assigne au granter (trouver le champ avec `list_properties`, puis relire).
