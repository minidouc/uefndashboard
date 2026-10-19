# Catalogue des Appareils UEFN, Whitelist d'Armes et Protocole de Cablage `@editable`

## 1. Protocole Officiel de Cablage `@editable` via `savedActor` (Etape 9)

### Pourquoi `SetDeviceProperty` echoue sur les references Verse
L'appel direct `SetDeviceProperty` ou `ObjectTools.set_properties` sur le composant script principal echoue avec l'erreur :
`BP_Creative_..._C is not valid <device_type> for property '__verse_0x...'`
ou `the following properties could not be set: <property_name>`.
Le runtime Verse exige un wrapper de type strict, tandis que le niveau UEFN stocke des instances de Blueprints (`_C`).

### La Methode Infaillible en 3 Etapes (`ObjectTools` -> `__verse_0x*` -> `savedActor`)
Chaque propriete `@editable` declaree dans un `creative_device` Verse genere automatiquement un **sous-objet interne** sous le composant script de l'acteur Verse, nomme `__verse_0x<HASH_8_HEX>_<NomPropriete>` (ou `__verse_0x<HASH_8_HEX>`). Ce sous-objet expose une propriete bas niveau **`savedActor`** typee `/Script/Engine.Actor` qui accepte directement le chemin complet du Blueprint sans rejet de type.

1. **Etape 9.1 - Inspecter la hierarchie du Device Verse place** :
   Lister les sous-objets du composant script (ex. `<LevelPrefix>.<VerseDevice_UAID>.<nom_classe_verse>_0`) pour relever la correspondance exacte entre chaque nom de propriete `@editable` et son hash `__verse_0x<HASH>`. Ne jamais deviner le hash.
2. **Etape 9.2 - Ecrire `savedActor` via `ObjectTools.set_properties`** :
   Pour chacune des proprietes `@editable`, executer :
   ```json
   {
     "tool": "editor_toolset.toolsets.object.ObjectTools.set_properties",
     "arguments": {
       "object_path": "<LevelPrefix>.<VerseDevice_UAID>.<nom_classe_verse>_0.__verse_0x<HASH>",
       "properties": {
         "savedActor": "<LevelPrefix>.<TargetDevice_Exact_UAID>"
       }
     }
   }
   ```
3. **Etape 9.3 - Relecture et Recompilation de Validation** :
   Relire chaque sous-objet avec `ObjectTools.get_properties` pour confirmer que `savedActor` est non vide, puis lancer une compilation Verse (*Build Verse Code*) qui doit retourner `0 Error`.

---

## 2. Whitelist Stricte d'Armes et Objets (`item_granter_device`)

**INTERDICTION ABSOLUE** d'utiliser des assets du namespace `/Figment_...` (ex. `WID_Figment_Assault_Auto_Athena_SR`), des armes Mythiques de boss saisonniers ou des chemins `WID_` devines non listes ci-dessous, car ils provoquent un rejet bloquant du validateur UEFN a l'Etape 10.

Utiliser uniquement des armes issues de la liste blanche Creative standard ou verifier systematiquement l'asset avec `validate_selected` immediatement a l'Etape 5 :

| Categorie | Role Gameplay | Chemin / Pattern Autorise | Action si Rejete par `validate_selected` |
| :--- | :--- | :--- | :--- |
| **Fusil a pompe (Shotgun)** | Arme principale Slot 1 (`Clear Inventory` + `Equip: true`) | `/Figment_Shotgun_Standard_Athena/Gameplay/WID_Figment_Shotgun_Standard_Athena_SR` *(Verifie valide)* ou `WID_Shotgun_Standard_Athena_UC_Ore_T03` | Remplacer immediatement a l'Etape 5 avant de continuer |
| **Fusil d'assaut (AR)** | Arme secondaire Slot 2 (`Keep All` + `Equip: false`) | `WID_Assault_AutoHigh_Athena_SR_Ore_T03` (Scar Standard) ou `WID_Assault_Auto_Athena_R_Ore_T03` | **Ne jamais utiliser** `WID_Figment_Assault_Auto_Athena_SR` (Interdit) |
| **Pistolet-mitrailleur (SMG)** | Arme de pression Slot 2/3 | `WID_Pistol_AutoHeavyPDW_Athena_SR_Ore_T03` | Verifier via `validate_selected` |
| **Soin rapide (Heal)** | Slot 3/4 en Box Fight / Zone Wars | `Athena_Medkit` / `Athena_ShieldSmall` (Mini Potions) / `WID_Athena_Flopper` | Verifier via `validate_selected` |

**Regle de securite Etape 5 :** Des qu'un `item_granter_device` ou `vending_machine_device` recoit un `item_asset`, lancer un controle de validation sur cet acteur. Si le validateur signale une reference illegale, changer d'arme **immediatement a l'Etape 5** (ne jamais cliquer sur "Effectuer la correction automatique" sans reassigner une arme valide, sinon le Granter reste vide et casse `RunSelfTest`).

---

## 3. Fiches Techniques des Appareils Fondamentaux (`ValkyrieToolset.DeviceToolset`)

### 3.1 `player_spawner_device`
- **Chemin Asset** : `/CRD_PlayerSpawn/ItemDefinitions/PID_CP_Devices_PlayerSpawner`
- **Taille reelle (`get_actor_bounds`)** : `[379.6, 284.7, 323.9]` cm (Decalage centre : `[+61.8, -14.4, +33.9]` cm)
- **Proprietes critiques** :
  ```json
  {
    "playerTeam": {"teamType": "TeamIndex", "teamIndex": 1},
    "visibleInGame": false,
    "enabledDuringPhase": "Always"
  }
  ```
- **Regle Verse** : Lors d'un `fort_character.TeleportTo` vers la position d'un spawner, toujours ajouter **`+100.0 cm` sur l'axe Z** pour eviter que la capsule joueur (192 cm) ne traverse la dalle de sol (`31.9 cm` d'epaisseur).

### 3.2 `item_granter_device`
- **Chemin Asset** : `/CreativeCoreDevices/SetupAssets/PID_Device_ItemGranter`
- **Taille reelle** : `[256.0, 256.0, 291.7]` cm (Placer en `Zone_Logic`)
- **Pattern Séquentiel Obligatoire (Multi-Armes)** :
  - **Granter 1 (Arme principale en main)** : `"onGrantAction": "Clear Inventory"`, `"bEquipGrantedItem": true`, `"grantCondition": "Always"`, `"bGrantOnGameStart": false`.
  - **Granter 2+ (Armes suivantes et soins)** : `"onGrantAction": "Keep All"`, `"bEquipGrantedItem": false`, `"grantCondition": "Always"`, `"bGrantOnGameStart": false`.
- **Regle Verse** : Toujours attendre `ItemGrantedEvent` du Granter 1 avant d'appeler `GrantItem` sur le Granter 2 afin d'eviter qu'un `Clear Inventory` tardif n'efface la seconde arme.

### 3.3 `explosive_device` (Reset de Builds)
- **Chemin Asset** : `/CreativeCoreDevices/SetupAssets/PID_Device_ExplosiveBarrel`
- **Taille reelle** : `[71.3, 71.3, 115.5]` cm
- **Proprietes de Reset Non-Letal** :
  ```json
  {
    "blast Radius": 100,
    "player Damage": 0,
    "structure Damage": 1000000,
    "visible During Game": false,
    "can be Damaged": false,
    "damage Indestructible Buildings": false,
    "play Audio/VFX": false
  }
  ```
- **Regle de Couverture** : Un seul baril a un rayon limite. Sur une arene 8x8 (`4096 x 4096 cm`, diagonale `5793 cm`), 4 barils places uniquement aux coins extremes ne suffisent pas a detruire les constructions au centre. Toujours placer **1 baril central sous/sur la zone de depart (`O`)** en plus des 4 barils de cadrage pour casser la base portante des builds joueurs (la gravite Fortnite detruit alors instantanement tout le reste de la tour).

### 3.4 `barrier_device`
- **Role** : Bloquer les joueurs dans leur box ou devant leur rampe de depart pendant l'etat `Countdown` (`3, 2, 1`).
- **Usage Verse** : Activer avec `Barrier.Enable()` dans `Preparing`, desactiver avec `Barrier.Disable()` exactement au tick `OnCountdownFinished`.

### 3.5 `score_manager_device` & `end_game_device`
- **Chemins Assets** :
  - `/CreativeCoreDevices/SetupAssets/PID_Device_ScoreManager`
  - `/CRD_GameEnd/SetupAssets/PID_Device_EndGame_V2`
- **Configuration `Match_End_Game`** :
  ```json
  {
    "whatToEnd": "EndGame",
    "winningTeam": {"teamType": "ActivatingTeam", "teamIndex": 0},
    "activatingTeam": {"teamType": "Any", "teamIndex": 0}
  }
  ```

### 3.6 `hud_message_device`
- **Chemin Asset** : `/CreativeCoreDevices/SetupAssets/PID_Device_HUDMessage`
- **Configuration Score Persistant** :
  ```json
  {
    "showForDuration": false,
    "placement": "Top Center",
    "showOnRoundStart": false,
    "priority": 1,
    "layer": 0
  }
  ```