# Verse : conventions, verification de l'API, compilation, auto-test

Statuts issus des tests du 2026-10-19. Le projet de test ne contenait **aucun fichier .verse** :
la compilation n'a ete prouvee que sur un projet vide, et le patron de la section 4 n'a jamais ete compile.

## 1. Convention de nommage (`actor_label` == nom `@editable`)

Le nom de chaque variable `@editable` est identique a l'`actor_label` du device dans `04_devices.json`.
Cela permet de retrouver la cible d'une reference a la main, ou plus tard automatiquement si le cablage `savedActor` est prouve (voir `devices-catalog-and-wiring.md`, section 6).

```json
{"actor_label": "Spawner_Team1_01", "asset_key": "player_spawner"}
```
```verse
@editable
Spawner_Team1_01 : player_spawner_device = player_spawner_device{}
```

## 2. Verifier l'API avant d'ecrire (outils proven)

Les digests Verse du moteur sont lisibles par MCP. Avant d'appeler une methode d'un device, verifier qu'elle existe :

| besoin | outil | arguments |
|---|---|---|
| racines | `Verse.ListFiles` | `{"path": "", "bRecursive": false}` -> `/Fortnite.com (Fortnite)`, `/Verse.org (Verse)`, `/UnrealEngine.com (UnrealEngine)`, dossier du projet |
| chercher une signature | `Verse.Grep` | `{"pattern": "GrantItem", "pathGlob": "/Fortnite.com (Fortnite)/**", "maxResults": 10}` |
| lire autour | `Verse.ReadFile` | `{"path": "<filePath renvoye>", "span": {"startLine", "startCharacter", "endLine", "endCharacter"}}` |
| fichiers du projet | `Verse.ListFiles` | `{"path": "/<id du projet>", "bRecursive": true}` |

Un `Grep` sans resultat renvoie `[]` sans erreur : verifier le motif sur un nom connu avant de conclure qu'une methode n'existe pas.

## 3. Regles de syntaxe

- Imports (forme correcte, sans lien) :
  ```verse
  using { /Fortnite.com/Devices }
  using { /Fortnite.com/Characters }
  using { /Verse.org/Simulation }
  using { /Verse.org/Random }
  using { /UnrealEngine.com/Temporary/Diagnostics }
  using { /UnrealEngine.com/Temporary/SpatialMath }
  ```
- Variable mutable : `var Nom : type = valeur`, puis `set Nom = nouvelle_valeur`.
- Contexte d'echec : un acces `Tableau[Index]` ou un appel `<decides>` se fait dans un `if (X := Tableau[0]):`.
- `Sleep()` seulement dans une fonction `<suspends>` ou un bloc `spawn{}`.

## 4. Patron de device principal (jamais compile)

```verse
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/Diagnostics }

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
        Print("[STEP] Spawners_Enabled")
        Barrier_Start_01.Enable()
        Sleep(0.2)
        Barrier_Start_01.Disable()
        Print("[STEP] Barrier_Toggle_Cycle")
        Round_Timer_01.Start()
        Sleep(0.2)
        Round_Timer_01.Reset()
        Print("[STEP] Timer_Start_Reset_Cycle")
        Print("[SELF_TEST_COMPLETE]")
```

Avis critique sur l'auto-test : il n'affirme rien. Il appelle des methodes et imprime une ligne, sans lire aucun etat.
Une ligne `[STEP]` prouve seulement que le code a atteint ce point, pas que la barriere ou le timer ont reagi.
Ne pas la presenter comme un `[ASSERT_OK]`. Avant d'utiliser chaque methode (`SpawnedEvent`, `GrantItem`, `Start`, `Reset`, `SuccessEvent`), la verifier dans le digest (section 2).

## 5. Ecrire le fichier .verse

- `VerseToolset.WriteFile` et les autres outils d'edition Verse sont **dangerous et non testes**. Ne les utiliser qu'avec l'accord de l'utilisateur, puis relire avec `Verse.ReadFile`.
- Sinon : donner le code a l'utilisateur, qui le colle dans le projet.

## 6. Compiler (proven, session Disconnected seulement)

1. `Session.GetSessionStatus {}` doit valoir `Disconnected`. Le comportement de `BuildAll` avec une session connectee n'est pas teste.
2. `Verse.BuildAll {}` : environ 6 s sur un projet vide. Renvoie la liste des diagnostics `{severity: Error|Warning|Information|Hint, code, message, filePath, span}`. Liste vide = aucune erreur signalee.
3. Recouper dans les logs : `Logs.GetLogEntries {"category": "VerseBuild", "pattern": "", "maxEntries": 15}`.
   Les lignes sont localisees (« Compilation terminée. », « Liaison terminée. », « SUCCÈS -- Version terminée. ») et le log garde les builds precedents : comparer l'horodatage a celui de l'appel.
4. Ne jamais conclure « 0 erreur » sur une liste vide seule : verifier aussi qu'une ligne de succes recente existe dans `VerseBuild`.

`BuildAll` n'a pas de parametre de push. Pousser le Verse (`PushChanges`) est dangerous et non teste.

## 7. Cabler les @editable

- Valeurs simples (`int`, `float`, `logic`, `string`) : `Device.SetDeviceProperty {"device", "propertyName", "value"}` est **unknown** (jamais teste sur un device Verse).
- References d'acteurs : **unknown** (hypothese `savedActor`, voir `devices-catalog-and-wiring.md`, section 6).
- Il n'y a pas de commande `verse.set_property` ni d'injection `.t3d` : elles appartenaient a un Bridge Python qui n'existe pas dans ce montage.
- En attendant une preuve : lister a l'utilisateur chaque `@editable` et l'`actor_label` cible, pour un cablage a la main.
