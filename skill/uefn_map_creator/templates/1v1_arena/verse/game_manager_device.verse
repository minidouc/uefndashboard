# GABARIT NON COMPILE. Ce fichier n'a jamais passe dans Verse.BuildAll : il est propose,
# pas prouve. Avant de l'ecrire dans le projet (etape 8, `verse-write`) :
#   1. verifier CHAQUE signature d'API dans les digests (`verse-grep --pattern <nom>`) ;
#      un Grep vide ne prouve pas l'absence, il impose de relire le digest ;
#   2. `verse-build` : diagnostics vides ET ligne de succes recente dans les logs VerseBuild.
# Convention : chaque @editable porte exactement l'actor_label de 04_devices.json.
# L'auto-test ci-dessous n'affirme rien : une ligne [STEP] prouve seulement que le code est
# arrive jusque la, pas que la barriere ou le timer ont reagi.

using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/Diagnostics }

game_manager_device := class(creative_device):

    @editable
    DebugSelfTest : logic = true

    @editable
    Spawner_P1_01 : player_spawner_device = player_spawner_device{}

    @editable
    Spawner_P2_01 : player_spawner_device = player_spawner_device{}

    @editable
    Granter_Loadout_01 : item_granter_device = item_granter_device{}

    @editable
    Barrier_Center_01 : barrier_device = barrier_device{}

    @editable
    Barrier_Center_02 : barrier_device = barrier_device{}

    @editable
    Round_Timer_01 : timer_device = timer_device{}

    var IsRoundActive : logic = false

    OnBegin<override>()<suspends>:void =
        Spawner_P1_01.SpawnedEvent.Subscribe(OnPlayerSpawned)
        Spawner_P2_01.SpawnedEvent.Subscribe(OnPlayerSpawned)
        Round_Timer_01.SuccessEvent.Subscribe(OnRoundTimerFinished)
        if (DebugSelfTest?):
            RunSelfTest()
        StartNewRound()

    OnPlayerSpawned(Agent : agent):void =
        Granter_Loadout_01.GrantItem(Agent)

    StartNewRound()<suspends>:void =
        set IsRoundActive = false
        Barrier_Center_01.Enable()
        Barrier_Center_02.Enable()
        Round_Timer_01.Start()
        Sleep(3.0)
        Barrier_Center_01.Disable()
        Barrier_Center_02.Disable()
        set IsRoundActive = true

    OnRoundTimerFinished(MaybeAgent : ?agent):void =
        set IsRoundActive = false

    RunSelfTest()<suspends>:void =
        Print("[SELF_TEST_START] game_manager_device")
        Barrier_Center_01.Enable()
        Barrier_Center_02.Enable()
        Sleep(0.2)
        Barrier_Center_01.Disable()
        Barrier_Center_02.Disable()
        Print("[STEP] Barrier_Toggle_Cycle")
        Round_Timer_01.Start()
        Sleep(0.2)
        Round_Timer_01.Reset()
        Print("[STEP] Timer_Start_Reset_Cycle")
        Print("[SELF_TEST_COMPLETE]")
