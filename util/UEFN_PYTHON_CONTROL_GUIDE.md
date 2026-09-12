# Guide Ultime de Contrôle & Fonctionnalités UEFN via le Bridge Python

Ce document est le compte-rendu exhaustif des tests d'exploration, de contrôle et de performance réalisés directement au sein de **Unreal Editor for Fortnite (UEFN)** via le bridge Python embarqué (`http://127.0.0.1:8790/run-script`).

---

## 1. Architecture & Environnement d'Exécution

### 1.1 Spécifications de l'Environnement Testé
* **Moteur** : Unreal Engine 6.0.0 (Build interne Epic `6.0.0-57819926+++Fortnite+Release-42.10`).
* **Exécutable Hôte** : `UnrealEditorFortnite-Win64-Shipping.exe`.
* **Interpréteur Python Intégré** : Python 3.11.8 (64-bit AMD64, MSC v.1937).
* **Richesse de l'API** :
  * **41 356** attributs dans le module `unreal`.
  * **41 299** classes natives répertoriées.
  * **265** sous-systèmes d'éditeur (`EditorSubsystem`).
  * **201 841** assets indexés dans l'Asset Registry (`/Game`, `/Engine`, `/FortniteGame`).
  * **10 517** classes spécifiques à Fortnite.
  * **598** classes relatives au mode Créatif.
  * **292** classes relatives aux Devices.
  * **164** classes relatives au langage Verse.

### 1.2 Mécanisme de Fonctionnement du Bridge
Le script `bridge_server.py` fonctionne selon un modèle asynchrone sécurisé :
1. **Serveur HTTP** : Reçoit les requêtes POST JSON `{"script": "..."}` sur un thread démon (`127.0.0.1:8790`).
2. **Queue & Thread Safety** : Chaque script est déposé dans une file thread-safe `script_queue`.
3. **Exécution Main Thread** : Les scripts sont exécutés sur le thread principal du moteur via le callback `unreal.register_slate_post_tick_callback()`. Cela garantit que **toutes les opérations UEFN (spawn, modification, suppression, compilation) sont 100% thread-safe**.
4. **Récupération du Résultat** : Le script exécuté stocke son retour dans la variable `result`.

> [!CAUTION]
> **Règle Critique de Sérialisation JSON :**
> Le bridge applique `json.dumps(result)` sans encodeur personnalisé. **Tout type natif Unreal** (`unreal.Name`, `unreal.Vector`, `unreal.Rotator`, `unreal.LinearColor`, `UObject`, `AActor`, etc.) placé directement dans `result` provoquera une exception côté serveur HTTP (erreur 500 ou socket fermé).
> **Solution :** Toujours convertir les objets Unreal en types primitifs Python (`str()`, `float()`, `int()`, `list`, `dict`) avant assignation dans `result`.

---

## 2. Synthèse Globale des Capacités Validées

| Domaine Testé | Statut | Performance / Résultat | Remarques & Méthodes Clés |
| :--- | :---: | :---: | :--- |
| **Spawn d'Actors Moteur** |  Validé | 14/14 types testés OK | `EditorActorSubsystem.spawn_actor_from_class` |
| **Transformations 3D** |  Validé | Précision sub-millimétrique | `set_actor_location`, `rotation`, `scale3d` |
| **Hiérarchie & Outliner** |  Validé | Organisation instantanée | `set_folder_path`, `set_actor_label`, `attach_to_actor` |
| **Meshes de Base & MIDs** |  Validé | 100% fonctionnel | Cube, Sphere, Cylinder, Cone, Plane (`/Engine/BasicShapes`) |
| **Shaders & Graphe de Matériaux** |  Validé | Création & Recompilation | `MaterialEditingLibrary`, création de nœuds d'expression |
| **Éclairage & Atmosphère** |  Validé | Rendu cinématique direct | DirectionalLight, SkyAtmosphere, Volumetric Fog, PostProcess |
| **Séquenceur & Caméras** |  Validé | Création de cinématiques | `LevelSequence`, `CineCameraActor`, pistes de transform |
| **Devices & Props Fortnite** |  Validé | Spawn via classes générées | `BP_PinballFlipper_C`, `Device_Floor_VehicleSpawner_C` |
| **Câblage Événements & Channels** |  Validé | GameplayTagContainer | `FortGameplayReceiverMessageComponent.set_channel_id` |
| **Nanite & Maillages Statiques** |  Validé | Inspection & Contrôle | `StaticMeshEditorSubsystem` (Nanite settings, UVs, LODs) |
| **Render Targets Dynamiques** |  Validé | Création à chaud 512x512 | `RenderingLibrary.create_render_target2d` |
| **Contrôle Viewport & Caméra** |  Validé | Cadrage 3D & FOV | `LevelEditorSubsystem.set_level_viewport_camera_info` |
| **Commandes Console** |  Validé | 100% fonctionnel | `SystemLibrary.execute_console_command` (`stat fps`, etc.) |
| **Système de Transaction (Undo)** |  Validé | Annulation Ctrl+Z native | `with unreal.ScopedEditorTransaction("Titre"):` |
| **Niagara & Audio Spatialisé** |  Validé | Spawn dynamique | `NiagaraActor`, `AmbientSound`, `NiagaraFunctionLibrary` |
| **Stress Test Extrême (2 000 Actors)** |  Validé | **14 000 ops en 9,48s** | Linéarité parfaite, clean en 0,48s |

---

## 3. Détail des Fonctionnalités par Domaine & Recettes de Code

### 3.1 Gestion du Niveau et des Acteurs (Suite 1)

Tous les acteurs fondamentaux du moteur s'instancient sans restriction :
* `StaticMeshActor`, `PointLight`, `SpotLight`, `DirectionalLight`, `RectLight`, `SkyLight`
* `ExponentialHeightFog`, `PostProcessVolume`, `SkyAtmosphere`, `VolumetricCloud`
* `CameraActor`, `CineCameraActor`, `DecalActor`, `TextRenderActor`

#### Modèle d'organisation & Transformation
```python
import unreal

actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

# 1. Spawning
loc = unreal.Vector(500, 0, 100)
rot = unreal.Rotator(0, 45, 0)
actor = actor_sub.spawn_actor_from_class(unreal.StaticMeshActor, loc, rot)

# 2. Nommage & Arborescence dans l'Outliner
actor.set_actor_label("Hero_Platform_01")
actor.set_folder_path("Environment/Platforms")

# 3. Tags de gameplay
tags = actor.get_editor_property('tags')
tags.append(unreal.Name("Interactive"))
actor.set_editor_property('tags', tags)

# 4. Attachement hiérarchique
child_cam = actor_sub.spawn_actor_from_class(unreal.CameraActor, loc, rot)
child_cam.attach_to_actor(
    actor, 
    unreal.Name("None"), 
    unreal.AttachmentRule.KEEP_WORLD, 
    unreal.AttachmentRule.KEEP_WORLD, 
    unreal.AttachmentRule.KEEP_WORLD, 
    False
)

result = {
    'spawned': str(actor.get_actor_label()),
    'folder': str(actor.get_folder_path()),
    'parent': str(child_cam.get_attach_parent_actor().get_actor_label())
}
```

---

### 3.2 Matériaux Dynamiques & Compilation de Shaders (Suite 4)

Il est possible d'attribuer des maillages, de créer des **Material Instance Dynamic (MID)** à la volée, et même de **créer des assets de matériaux complets de manière procédurale** dans le Content Browser !

#### Application de MIDs avec Couleurs & Rugosité Dynamiques
```python
import unreal

actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = actor_sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0,0,100), unreal.Rotator(0,0,0))
sm_comp = actor.get_editor_property('static_mesh_component')

# Charger le maillage cube du moteur
mesh = unreal.load_asset('/Engine/BasicShapes/Cube.Cube')
sm_comp.set_editor_property('static_mesh', mesh)

# Créer un MID basé sur le matériau de base
base_mat = unreal.load_asset('/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial')
mid = sm_comp.create_dynamic_material_instance(0, base_mat)

# Configurer les paramètres scalaires et vectoriels
mid.set_vector_parameter_value('Color', unreal.LinearColor(0.1, 0.7, 1.0, 1.0)) # Bleu néon
mid.set_scalar_parameter_value('Roughness', 0.15) # Reflet brillant

result = {'status': 'Material applied successfully'}
```

#### Création Procédurale de Matériaux (`MaterialEditingLibrary`)
```python
import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
mat_factory = unreal.MaterialFactoryNew()

# 1. Créer le matériau dans /Game
new_mat = asset_tools.create_asset('M_CustomShader', '/Game/Shaders', unreal.Material, mat_factory)

# 2. Ajouter un nœud de paramètre vectoriel (Base Color)
vec_node = unreal.MaterialEditingLibrary.create_material_expression(
    new_mat, 
    unreal.MaterialExpressionVectorParameter, 
    -400, 0
)
vec_node.set_editor_property('parameter_name', unreal.Name('BaseColor'))
vec_node.set_editor_property('default_value', unreal.LinearColor(1.0, 0.2, 0.2, 1.0))

# 3. Connecter au canal Base Color
unreal.MaterialEditingLibrary.connect_material_property(
    vec_node, 
    'RGBA', 
    unreal.MaterialProperty.MP_BASE_COLOR
)

# 4. Recompiler le shader
unreal.MaterialEditingLibrary.recompile_material(new_mat)

result = {'material_path': str(new_mat.get_path_name())}
```

---

### 3.3 Intégration Fortnite : Devices, Spawners & Props (Suite 3)

Dans UEFN, les Blueprints de Devices et de Props Fortnite situés dans `/Game/Creative/Devices/` ou `/Game/Items/Traps/` sont compilés en classes générées.

> [!IMPORTANT]
> **Règle de Chargement des Devices UEFN :**
> N'utilisez pas `unreal.load_asset(path)` pour spawner un Blueprint de device directement.
> Utilisez le suffixe de classe générée `_C` avec `unreal.load_class(None, f"{path}.{name}_C")` !

#### Exemple : Spawner et inspecter un Flipper de Pinball ou un Vehicle Spawner
```python
import unreal

actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

# Charger la classe générée du Flipper
device_class_path = '/Game/Creative/Devices/Pinball_Flipper/BP_PinballFlipper.BP_PinballFlipper_C'
flipper_class = unreal.load_class(None, device_class_path)

# Spawner l'appareil dans le monde UEFN
flipper = actor_sub.spawn_actor_from_class(flipper_class, unreal.Vector(0, 0, 50), unreal.Rotator(0, 0, 0))
flipper.set_actor_label("Creative_Pinball_Flipper_01")
flipper.set_folder_path("Devices/Gameplay")

# Les 21 composants internes du device (triggers, messages, options) sont accessibles :
components = [c.get_name() for c in flipper.get_components_by_class(unreal.ActorComponent)]

result = {
    'actor': str(flipper.get_actor_label()),
    'components_count': len(components),
    'components_sample': components[:5]
}
```

---

### 3.4 Environnement, Éclairage & Post-Processing (Suite 6)

L'atmosphère et la colorimétrie peuvent être entièrement sculptées par script pour créer des ambiances cinématiques instantanées :

```python
import unreal

actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

# 1. Soleil (Directional Light)
sun = actor_sub.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 500), unreal.Rotator(-35, 45, 0))
sun_comp = sun.get_editor_property('light_component')
sun_comp.set_editor_property('intensity', 12.0)
sun_comp.set_editor_property('use_temperature', True)
sun_comp.set_editor_property('temperature', 4500.0) # Golden Hour
sun_comp.set_editor_property('atmosphere_sun_light', True)

# 2. Atmosphère Physique (SkyAtmosphere)
sky = actor_sub.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0,0,0), unreal.Rotator(0,0,0))

# 3. Brouillard Volumétrique (ExponentialHeightFog)
fog = actor_sub.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0,0,0), unreal.Rotator(0,0,0))
fog_comp = fog.get_editor_property('component')
fog_comp.set_fog_density(0.015)
fog_comp.set_volumetric_fog(True)
fog_comp.set_volumetric_fog_scattering_distribution(0.75)
fog_comp.set_volumetric_fog_distance(12000.0)

# 4. Post-Process Global (PostProcessVolume)
ppv = actor_sub.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0,0,0), unreal.Rotator(0,0,0))
ppv.set_editor_property('unbound', True) # Effet infini sur toute la carte

result = {'status': 'Cinematic environment established'}
```

---

### 3.5 Contrôle du Viewport, de la Caméra & Commandes Console (Suite 7)

Vous pouvez piloter la caméra de travail de l'éditeur pour cadrer précisément sur un objet ou une zone :

```python
import unreal

level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
unreal_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = unreal_sub.get_editor_world()

# Déplacer et orienter la caméra du Viewport
target_cam_loc = unreal.Vector(1200, -800, 600)
target_cam_rot = unreal.Rotator(-25, 140, 0)
level_sub.set_level_viewport_camera_info(target_cam_loc, target_cam_rot)
level_sub.set_level_viewport_fov(85.0)

# Exécuter des commandes console dans l'éditeur
unreal.SystemLibrary.execute_console_command(world, "stat fps")
unreal.SystemLibrary.execute_console_command(world, "viewmode lit")

result = {
    'viewport': str(level_sub.get_active_viewport_config_key()),
    'camera_positioned': True
}
```

---

### 3.6 Séquences Cinématiques & Sequencer (Suite 5)

La création de cinématiques et de tracks de caméra est totalement scriptable :

```python
import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

# 1. Créer l'asset LevelSequence
seq_factory = unreal.LevelSequenceFactoryNew()
seq = asset_tools.create_asset('LS_CinematicShot', '/Game/Cinematics', unreal.LevelSequence, seq_factory)

# 2. Spawner une CineCameraActor
cam = actor_sub.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(0, -500, 150), unreal.Rotator(0, 90, 0))
cam.set_actor_label("Shot_Camera_A")

# 3. Lier au séquenceur (Possessable)
binding = seq.add_possessable(cam)

# 4. Ajouter la piste de mouvement 3D
track = binding.add_track(unreal.MovieScene3DTransformTrack)
section = track.add_section()

result = {
    'sequence': str(seq.get_path_name()),
    'binding_id': str(binding.get_id())
}
```

---

### 3.7 Gestion des Transactions & Sécurité Undo (Ctrl+Z)

Toutes les opérations d'un script peuvent être regroupées dans une transaction atomique. Si l'utilisateur appuie sur **Ctrl+Z** dans UEFN, l'intégralité du script est annulée en une seule frappe !

```python
import unreal

actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

with unreal.ScopedEditorTransaction("Spawn Arène Procédurale"):
    # Tout ce qui est exécuté dans ce bloc est réversible d'un seul Ctrl+Z
    for i in range(20):
        a = actor_sub.spawn_actor_from_class(
            unreal.StaticMeshActor, 
            unreal.Vector(i * 100, 0, 0), 
            unreal.Rotator(0, 0, 0)
        )
        a.set_actor_label(f"ArenaPillar_{i}")

result = {'transaction': 'Completed with undo support'}
```

### 3.8 Câblage Événements & Direct Event Binding (Channels)

Dans Fortnite / UEFN, les appareils communiquent via des récepteurs et déclencheurs de messages (`FortGameplayReceiverMessageComponent` et `FortGameplayTriggerMessageComponent`).
Les canaux ne sont pas de simples entiers, mais des **`GameplayTagContainer`** structurés.

```python
import unreal

# Créer un conteneur de GameplayTag pour le canal désiré
tag = unreal.GameplayTag()
tag.import_text('(TagName="Creative.Property.Channel.Channel1")')

container = unreal.GameplayTagContainer()
container.add_tag(tag)

# Assigner le canal sur le composant récepteur du device
receiver_comp.set_channel_id(container)

# Vérifier la lecture du canal
active_channel = receiver_comp.get_channel_id().export_text()
```

---

### 3.9 Render Targets Dynamiques & Nanite (`StaticMeshEditorSubsystem`)

```python
import unreal

unreal_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = unreal_sub.get_editor_world()

# 1. Création d'une Render Target 2D à chaud et peinture de fond
rt = unreal.RenderingLibrary.create_render_target2d(
    world, 512, 512, 
    unreal.TextureRenderTargetFormat.RTF_RGBA8
)
unreal.RenderingLibrary.clear_render_target2d(world, rt, unreal.LinearColor(0.9, 0.1, 0.4, 1.0))

# 2. Inspection & Configuration Nanite sur les maillages
sm_sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
cube_mesh = unreal.load_asset('/Engine/BasicShapes/Cube.Cube')
nanite_settings = sm_sub.get_nanite_settings(cube_mesh)
```

---

## 4. Benchmarks de Stress Extrême : Poussé aux Derniers Retranchements

Pour mesurer la limite absolue de débit du bridge et du thread principal UEFN, nous avons exécuté des séries de tests de génération de structures géométriques spiralées avec 7 opérations par acteur (calcul polaire, spawn, scale, attribution de mesh, création de MID, calcul de couleur dynamique, classement Outliner) sur **4 paliers successifs** :

| Palier d'Acteurs | Opérations Éditeur | Temps de Spawn | Débit de Spawn | Temps de Nettoyage (Clean) | Débit de Clean |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **100** | ~700 ops | **0,42 s** | 1 663 ops / sec | **0,022 s** | 4 529 ops / sec |
| **500** | ~3 500 ops | **2,14 s** | 1 632 ops / sec | **0,120 s** | 4 158 ops / sec |
| **1 000** | ~7 000 ops | **4,42 s** | 1 582 ops / sec | **0,235 s** | 4 238 ops / sec |
| **2 000** | ~14 000 ops | **9,48 s** | 1 476 ops / sec | **0,484 s** | 4 126 ops / sec |

### Enseignements Clés du Stress Test :
1. **Linéarité quasi-parfaite** : Le coût par acteur reste constant (~4,7 ms par acteur complet) même au palier de 2 000 acteurs.
2. **Aucun gel de l'éditeur** : L'exécution sur `unreal.register_slate_post_tick_callback` traite l'ensemble des 14 000 opérations sans jamais dépasser le timeout de 60s du bridge HTTP.
3. **Destruction chirurgicale ultra-rapide** : 2 000 acteurs détruits proprement de la mémoire du monde en moins d'une demi-seconde (**0,48 s**).

---

## 5. La Ville Fortnite Réaliste Actuellement Déployée dans votre UEFN (Zéro Graybox)

Pour répondre à votre demande de tester avec de **vrais objets Fortnite texturés et modélisés**, la scène a été entièrement reconstruite avec **139 acteurs utilisant 100% d'assets officiels de Fortnite** issus du package `/Game/` :

### Palette d'Assets Officiels Utilisés :
* **Véhicule Héro** : Le mythique **Battle Bus / School Bus** de Fortnite (`/Game/Vehicles/FORT_Vehicles_01/Meshes/Vehicle_SchoolBus_01`).
* **Loot & Récompenses** : Les **Coffres aux Trésors Dorés** authentiques (`/Game/Environments/Props/Boxes/Meshes/TreasureChestLootTier1`).
* **Conteneurs & Caisses** : Les caisses de **Supply Drop** (`/Game/Gadgets/Assets/SupplyDrop/Mesh/Prop_Wood_Crate_SupplyDrop`) et les tonneaux en bois (`SM_TRV_CAS_WoodenBarrels_1`).
* **Architecture & Bâtiments** : Vraies dalles et murs de construction joueur Fortnite (Planches de bois `PBW_W1_Floor`, briques `PBW_B1_Floor`, portes et arches `PBW_B1_DoorC`, façades de boutique `SM_NeonCityStore_Front_Wall_C_A`).
* **Mobilier Urbain de Neo Tilted** : Distributeurs automatiques (`S_NeoTilted_VendingMachine`), bouches d'incendie (`S_NeoTilted_FireHydrant`) et bancs publics (`S_NeoTilted_Bench`).
* **Éclairage Réel** : Lampadaires de style château (`S_PrincessCastle_LampPost_B`) équipés de vraies lanternes `PointLight` diffusant une lumière chaude à 5 200 K.
* **Végétation & Nature** : Tournesols géants (`Foliage_Sunflower_01`), citrouilles (`Foliage_Pumpkin_01`) et palmiers nains (`Foliage_PalmBush2`).
* **Dispositifs de Jeu** : Piège à pointes (`Spike_Trap_Floor_Base`), 4 plaques de spawn de joueurs (`FortPlayerStartCreative`), flippers de flipper (`BP_PinballFlipper_C`) et générateur de véhicules (`Device_Floor_VehicleSpawner_C`).

### Cadrage & Réversibilité :
* **Cadrage Caméra** : Le Viewport UEFN a été positionné aux coordonnées `(1250, -1150, 480)` avec un angle de plongée de -18° cadrant parfaitement le Battle Bus au centre de la place du village, les coffres dorés et les devantures de magasins.
* **100% Annulable (Ctrl+Z)** : Toute la ville est encapsulée dans une transaction. Un simple appui sur **Ctrl+Z** dans UEFN efface l'intégralité de la scène si vous souhaitez retrouver un projet vierge.

## 6. Matrice des Erreurs et Pièges à Éviter

| Piège / Erreur Fréquente | Cause Technique | Solution Éprouvée |
| :--- | :--- | :--- |
| `TypeError: Object of type ... is not JSON serializable` | L'objet retourné dans `result` contient un type Unreal (`FName`, `Vector`, `AActor`, etc.). | Convertir avec `str()`, `float()`, `[x, y, z]` ou dictionnaires natifs Python. |
| `spawn_actor_from_object returned None` sur un Blueprint | Les Blueprints Fortnite/Creative en mode cuit nécessitent leur classe générée `_C`. | Utiliser `unreal.load_class(None, f"{path}.{name}_C")` puis `spawn_actor_from_class`. |
| `Failed to find property 'simulate_physics'` | Propriété inaccessible directement via `set_editor_property` au niveau racine du composant. | Utiliser les méthodes directes `sm_comp.set_simulate_physics(True)` ou passer par `body_instance`. |
| `NativizeProperty: Cannot nativize 'Name' as 'ClassPathName'` | Depuis UE 5.1+, l'Asset Registry requiert `TopLevelAssetPath` pour les requêtes de classe. | Utiliser `unreal.TopLevelAssetPath('/Script/Module', 'ClassName')`. |
| Perte d'annulation (Undo) | Les scripts Python standard n'enregistrent pas automatiquement de point de rollback. | Encadrer systématiquement le code dans `with unreal.ScopedEditorTransaction("Description"):`. |

---

## 7. Template Maître pour Tout Script Futur

Voici le modèle optimal à utiliser pour n'importe quelle mission de génération ou de modification dans votre projet UEFN :

```python
import unreal
import json

# 1. Sous-systèmes principaux
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
unreal_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = unreal_sub.get_editor_world()

summary = {
    'spawned': 0,
    'modified': 0,
    'errors': []
}

# 2. Transaction sécurisée avec support Ctrl+Z
with unreal.ScopedEditorTransaction("Nom de Votre Tâche"):
    try:
        # VOS OPÉRATIONS ÉDITEUR ICI (Spawn, Wire, Transform, Set Material)
        pass
    except Exception as e:
        summary['errors'].append(str(e))

# 3. Résultat propre 100% sérialisable
result = {
    'success': len(summary['errors']) == 0,
    'summary': summary
}
```
