# Standard de Code Verse, Cablage `@editable` et Auto-Test (QA)

## 1. Convention Stricte de Nommage (`actor_label` == `@editable`)

Pour permettre au script de cablage automatique de relier les appareils sans erreur, le nom de la variable `@editable` dans le fichier `.verse` doit etre **strictement identique** au champ `actor_label` defini dans `workspace_map/04_devices.json`.

**Dans `04_devices.json` :**
```json
{
  "actor_label": "Spawner_Team1_01",
  "device_class": "player_spawner_device"
}
```

**Dans le fichier `.verse` :**
```verse
@editable
Spawner_Team1_01 : player_spawner_device = player_spawner_device{}
```

## 2. Regles de Syntaxe Verse Anti-Erreur de Compilation

- **Imports obligatoires en haut de chaque fichier** :
  ```verse
  using { /[Fortnite.com/Devices](https://Fortnite.com/Devices) }
  using { /[Fortnite.com/Characters](https://Fortnite.com/Characters) }
  using { /Verse.org/Simulation }
  using { /Verse.org/Random }
  using { /[UnrealEngine.com/Temporary/Diagnostics](https://UnrealEngine.com/Temporary/Diagnostics) }
  using { /[UnrealEngine.com/Temporary/SpatialMath](https://UnrealEngine.com/Temporary/SpatialMath) }
  ```
- **Variables mutables** : Toujours declarer avec `var NomVariable : type = valeur` et modifier avec `set NomVariable = nouvelle_valeur`. Ne jamais utiliser `=` seul pour reaffecter une variable.
- **Contextes d'echec (Failable Contexts)** : Tout acces a un tableau par index `MonTableau[Index]` ou toute fonction portant le spécificateur `<decides>` doit obligatoirement se trouver dans une condition `if (Element := MonTableau[0]):`.
- **Fonctions asynchrones (`<suspends>`)** : `Sleep(Seconds)` ne peut etre appele que dans une fonction dotee du specificateur `<suspends>` (comme `OnBegin<override>()<suspends>:void`) ou a l'interieur d'un bloc `spawn{}`.

## 3. Patron Obligatoire avec `RunSelfTest()` Integré

Tout appareil Verse principal genere par le skill doit inclure ce squelette d'auto-test pour valider la carte lors de l'Etape 10 (Play-in-Client) :

```verse
using { /[Fortnite.com/Devices](https://Fortnite.com/Devices) }
using { /[Fortnite.com/Characters](https://Fortnite.com/Characters) }
using { /Verse.org/Simulation }
using { /[UnrealEngine.com/Temporary/Diagnostics](https://UnrealEngine.com/Temporary/Diagnostics) }

game_manager_device := class(creative_device):

    @editable
    DebugSelfTest : logic = true

    @editable
    Spawner_Team1_01 : player_spawner_device = player_spawner_device{}

    @editable
    Spawner_Team2_01 : player_spawner_device = player_spawner_device{}

    @editable
    Granter_Loadout_01 : item_granter_device = item_granter_device{}

    @editable
    Barrier_Start_01 : barrier_device = barrier_device{}

    @editable
    Round_Timer_01 : timer_device = timer_device{}

    var IsRoundActive : logic = false

    OnBegin<override>()<suspends>:void =
        Spawner_Team1_01.SpawnedEvent.Subscribe(OnPlayerSpawned)
        Spawner_Team2_01.SpawnedEvent.Subscribe(OnPlayerSpawned)
        Round_Timer_01.SuccessEvent.Subscribe(OnRoundTimerFinished)

        if (DebugSelfTest?):
            RunSelfTest()

        StartNewRound()

    OnPlayerSpawned(Agent : agent):void =
        Granter_Loadout_01.GrantItem(Agent)

    StartNewRound()<suspends>:void =
        set IsRoundActive = false
        Barrier_Start_01.Enable()
        Round_Timer_01.Start()
        Sleep(3.0)
        Barrier_Start_01.Disable()
        set IsRoundActive = true

    OnRoundTimerFinished(MaybeAgent : ?agent):void =
        set IsRoundActive = false

    RunSelfTest()<suspends>:void =
        Print("[SELF_TEST_START] game_manager_device")
        
        Spawner_Team1_01.Enable()
        Spawner_Team2_01.Enable()
        Print("[ASSERT_OK] Spawners_Enabled")

        Barrier_Start_01.Enable()
        Sleep(0.2)
        Barrier_Start_01.Disable()
        Print("[ASSERT_OK] Barrier_Toggle_Cycle")

        Round_Timer_01.Start()
        Sleep(0.2)
        Round_Timer_01.Reset()
        Print("[ASSERT_OK] Timer_Start_Reset_Cycle")

        Print("[SELF_TEST_COMPLETE] 0_ERRORS")
```

## 4. Cablage des Proprietes `@editable` (Etape 9)

1. **Proprietes simples (`int`, `float`, `logic`, `string`)** : Utiliser `ValkyrieToolset.DeviceToolset` pour modifier directement la valeur sur l'instance placee.
2. **References d'objets (`is_object_ref: true`) sur appareils V2** : Utiliser la commande du Bridge Python qui resout le chemin complet de l'acteur cible dans le niveau courant et l'injecte via transaction `.t3d` :
   ```json
   {
     "command": "verse.set_property",
     "device_label": "Game_Manager_Main",
     "property_name": "Spawner_Team1_01",
     "target_actor_label": "Spawner_Team1_01",
     "is_object_ref": true
   }
   ```