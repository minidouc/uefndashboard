# Sonde Python : prouver la porte, puis l'ouvrir

Objectif : remplacer le clavier (Computer Use) par des **outils MCP personnalisés** écrits en
Python, avec le vrai `unreal`. C'est ce qui sépare une île grise d'une île éclairée, et 1 h 15
de pose de 10 minutes.

## Ce qui est déjà prouvé par le code source d'Epic

Relevé le 2026-10-23 dans `C:\Program Files\Epic Games\Fortnite\Engine\Plugins\Experimental\` :

| Affirmation | Preuve |
| --- | --- |
| `Content/Python/init_unreal.py` est exécuté au démarrage | Epic s'appuie dessus : `ToolsetRegistry/Content/Python/init_unreal.py` et `Toolsets/EditorToolset/Content/Python/init_unreal.py` existent sur le disque et tournent (vus dans le journal Night City) |
| `import toolset_registry` fonctionne dans ce contexte | `from toolset_registry import tests` dans le fichier d'Epic |
| L'API d'enregistrement du document est exacte | `toolset_registry/registration.py` : `Registration(classes).register() -> bool` |
| `@unreal.uclass()` + `unreal.ToolsetDefinition` est le bon motif | 16 toolsets d'Epic le font, ex. `editor_toolset/toolsets/programmatic.py:1046` |
| Le bac à sable `execute_tool_script` est limité à 6 modules par construction | Liste codée en dur `_SUPPORTED_MODULES` dans `programmatic.py` |
| Le rechargement à chaud existe | `toolset_registry.reload_module(module)` désenregistre, recharge, ré-enregistre |
| **Le loader s'exécute au niveau PROJET** | Un produit tiers livré (`UEFN-Ducky`, `ducky_app/frontend/init_unreal.py`) écrit ce fichier dans `Content/Python/init_unreal.py` de l'île, plus `Documents/UnrealEngine/Python/init_unreal.py`, et démarre un listener |
| **L'enregistrement à l'import échoue : le registre n'est pas prêt** | Même fichier : « Defers ~45 ticks so Epic MCP Toolsets can bind :8000 first » |

La sonde diffère donc l'enregistrement avec `unreal.register_slate_post_tick_callback`,
jalons 45/90/180/360 ticks (`ISLANDFORGE_DEFER_TICKS` pour changer la base), et écrit un
**rapport provisoire dès l'import** : la preuve que le script s'est exécuté ne doit pas dépendre
de la réussite de l'enregistrement.

Ce qui restait **non prouvé** — le loader au niveau **projet** — est désormais corroboré par un
produit tiers livré qui s'appuie dessus (voir les deux dernières lignes du tableau). Ce que la
sonde doit encore établir chez nous : que **notre** toolset apparaît bien côté serveur MCP, et
qu'un outil personnalisé peut être appelé par le CLI.

## Résultats du test réel en direct (UEFN 42.40, projet `testmcp`, 2026-10-23)

- **Exécution de `init_unreal.py`** : `"FIN_ENREGISTRE - 6 etapes reussies sur 6"` (`register() == True`).
- **Inventaire des capacités (`IslandForgeProbe.sonder_capacites`)** : **19 / 20 capacités `True`** :
  - `PointLight`, `SpotLight`, `RectLight`, `DirectionalLight` : `True`
  - `EditorActorSubsystem`, `EditorLevelLibrary`, `EditorAssetLibrary`, `MaterialEditingLibrary`, `EditorValidatorSubsystem` : `True`
  - `StaticMeshComponent.create_dynamic_material_instance` : `True` (seul `MaterialEditingLibrary.create_material_instance` est `False`)
  - `LandscapeProxy`, `InstancedFoliageActor`, `FoliageType`, `HierarchicalInstancedStaticMeshComponent`, `NiagaraSystem`, `NiagaraComponent`, `ToolsetDefinition` : `True`
- **Découverte clé sur `UE::ValkyrieToolset::ToolsetPolicy`** :
  - En UEFN 42.40, la politique C++ `UE::ValkyrieToolset::ToolsetPolicy` filtre `get_all_toolset_json_schemas()` aux 29 toolsets officiels d'Epic, et `bAutoStartServer` peut être à `False` dans `EditorPerProjectUserSettings.ini`.
  - Solution intégrée dans `probes/init_unreal.py` et `script/mcp_client.py` :
    1. `init_unreal.py` active automatiquement les toolsets Python et C++ d'Epic (`valkyrie_toolset.registration.enable()`, `DeviceToolset`, `VerseToolset`, `EntityToolset`, `SessionToolset`), écrit les capacités directement dans `%TEMP%\sonde_islandforge.json`, et démarre un pont HTTP `/mcp` sur `127.0.0.1:8000` (si le port 8000 n'est pas déjà lié) qui expose les 29 toolsets officiels **ainsi que** `IslandForgeProbe` (`Probe.sonder_capacites`, `Probe.compter_acteurs`) sur le *game thread*.
    2. Si `http://127.0.0.1:8000/mcp` est fermé au premier appel, `McpClient` (`script/mcp_client.py`) lance automatiquement un bootstrap via `remote_execution` (`UDP 239.0.0.1:6766` avec correctif multicast loopback Windows sur `127.0.0.1`) pour exécuter `probes/init_unreal.py` dans l'éditeur UEFN ouvert sans aucune intervention manuelle.

## Règles du motif, d'après les docstrings d'Epic


- docstring de la **classe** = description du toolset vue par l'agent ;
- docstring de la **méthode** = description de l'outil, args au format Google ;
- `@tool_call` puis `@staticmethod`, dans cet ordre ;
- **params et type de retour obligatoirement annotés**, sinon `ToolCallMissingAnnotation` ;
- les outils tournent sur le *game thread* ;
- `register()` renvoie `False` **sans erreur** si le registre est indisponible : la valeur de
  retour est la seule preuve, jamais l'absence d'exception.

## Installer la sonde

1. Ouvrir le projet dans UEFN, noter le chemin (barre de titre). La sonde le réécrira de toute
   façon dans son rapport.
2. **Sauvegarder** `<PROJET>/Content/Python/init_unreal.py` s'il existe déjà.
3. Copier `probes/init_unreal.py` vers `<PROJET>/Content/Python/init_unreal.py`.
4. Redémarrer l'éditeur.

La sonde est strictement en **lecture** : aucun acteur, aucun asset, aucune sauvegarde.
Hors éditeur elle ne lève rien (testé : code retour 0, échec consigné dans le rapport).

## Vérifier sans Computer Use

Éditeur ouvert, depuis `script/` :

```bash
python mcp_client.py call Logs GetLogEntries '{"pattern":"SONDE_ISLANDFORGE","maxEntries":40}'
python mcp_client.py list
python mcp_client.py call IslandForgeProbe sonder_capacites '{}'
python mcp_client.py call IslandForgeProbe compter_acteurs '{}'
```

Et lire `%TEMP%\sonde_islandforge.json`.

## Table de décision

| Résultat | Conclusion | Suite |
| --- | --- | --- |
| Rapport absent, aucun log `SONDE_ISLANDFORGE` | Le loader ne s'exécute pas au niveau projet | Revenir à la console Python + Computer Use, ou chercher le réglage `Project Settings > Plugins > Python > Startup Scripts` |
| Rapport présent, `import_unreal` ok, `enregistrement_mcp` false | Le script tourne mais le registre n'est pas prêt à ce moment | Différer l'enregistrement (tick suivant / callback), ou passer par `ModelContextProtocol.RefreshTools` |
| Rapport présent, `enregistrement_mcp` true, toolset invisible dans `list` | Enregistré mais non exposé | Commande console `ModelContextProtocol.RefreshTools` puis relire |
| `sonder_capacites` répond | **La porte est ouverte** | Écrire le toolset d'écriture (lumières, matériau par instance), voir plus bas |

## Après la sonde : les outils qui comptent

Dans l'ordre, chacun suivi d'une relecture :

1. `placer_lumieres(spec_json)` — remplace ce qui était tapé à la main dans Night City
   (`LogActorFactory … /Script/Engine.PointLight`).
2. `set_materiau_par_instance(acteur, chemin)` — `create_dynamic_material_instance` : le plafond
   MCP ne permet que `set_material` sur l'**asset** (tous les exemplaires changent). La sonde dira
   si la méthode existe.
3. `audit_legalite()` — `AssetCheck` nomme chaque référence illégale avec son chemin exact.
   C'est l'oracle de légalité, et la règle d'or n°1 : **ne toucher par script que ce qui est
   visible dans l'interface UEFN**, sinon échec à la validation de publication.
4. `budget_memoire()` — 300 Mo / 100 000 unités ; la plaza à 2 257 acteurs n'a jamais été mesurée.

Architecture visée : toolset dans son propre module (`Content/Python/islandforge_tools.py`) et
`init_unreal.py` qui l'importe et l'enregistre — pour pouvoir recharger à chaud avec
`toolset_registry.reload_module(islandforge_tools)` sans redémarrer l'éditeur.

## Cadre MegaJam

Configurer « vos outils, agents et MCP à l'avance » est explicitement autorisé avant le
12 novembre. Ce fichier est un **outil de construction**, pas du contenu : il reste dans
l'éditeur, rien n'est exécuté au runtime de l'île, et la soumission UEFN est un code de version
privée — pas le projet. Il entre néanmoins dans la déclaration des scripts créés avant la jam.
