# Finitions visuelles, reperes spatiaux, playtest

## 1. Regle de l'habillage : lisible sans gener le jeu

Dans les modes competitifs (1v1, Box Fight, Zone Wars), un decor au milieu de l'aire de jeu gene la pose des murs. Un environnement uniforme fait perdre l'orientation.

- **Aucun decor collidable dans les tuiles de combat** (`.` et `O` restent libres).
- Les finitions vont sur la **peripherie** (coins, bordures) ou **hors de portee** (colonnes d'horizon, eclairage).

## 2. Les 3 couches de finition

Les chemins et tailles ci-dessous viennent d'anciennes notes : **non mesures pendant la campagne de tests**.
Les ajouter a `02_palette.json` et lancer `measure-palette` avant tout placement. Le CLI refuse un asset non mesure.

| cle | chemin note | taille notee (cm) |
|---|---|---|
| `maze_pylon` | `/CRG_Maze/SetupAssets/Meshes/CP_Maze_Pillar_Pylon_01` | 106.4 x 106.9 x 61.9 |
| `maze_pylon_orb` | `/CRG_Maze/SetupAssets/Meshes/CP_Maze_Pillar_PylonOrb_01` | 96.4 x 95.9 x 96.4 |
| `pillar_mole` | `/MoleEnvironments/Meshes/Creative/Factory/CP_Mole_Factory_Pillar_01` | 87.8 x 75.8 x 868.0 |

Le chemin d'un asset pour `add_to_scene_from_asset` a la forme `/Dossier/Nom.Nom`. Le confirmer avec `Asset.find_assets` ; une liste vide ne prouve pas l'absence.

### Couche 1 : balisage vertical des 4 coins
Sur une plateforme ouverte (`edge_policy: "fall_zone"`), aux 4 coins exterieurs :
1. Base : `maze_pylon` en `TILE_ANCHOR` sur `CORNER_SW` / `CORNER_SE` / `CORNER_NW` / `CORNER_NE`, `snap_to_floor: true`.
2. Orbe : `maze_pylon_orb` en `RELATIVE_TO_ACTOR`, `ON_TOP_OF` la base, `gap_cm: 10`.
3. Colonne haute : `pillar_mole`, reference visible meme a 3 ou 4 etages de construction.

### Couche 2 : nord et sud differents
Garder une empreinte au sol symetrique, mais varier la hauteur : par exemple les colonnes `pillar_mole` cote nord (derriere `S2`) et les orbes cote sud (derriere `S1`).

### Couche 3 : limite visible
Sur une carte a bords ouverts, les 4 pylones marquent les sommets de l'arene. Le joueur doit voir la limite avant de tomber.

### Controle
Apres placement : `audit-scene --live` (chevauchements et gravite sur les bounds relus), puis `visual-snapshot` pour une vue de dessus.
Le cadrage a pitch -90 n'a pas ete teste en editeur (seul pitch -30 a ete relu) : regarder l'image avant de conclure.

## 3. Playtest en session (etape 10) : NON PROUVE

Etat des tests du 2026-10-19 :
- `Session.GetSessionStatus` : proven (`Disconnected` pendant toute la campagne).
- `StartSession`, `PushChanges`, `StopSession` : **dangerous, jamais executes**. `StartSession` envoie le projet et a deja bloque le pont lors d'un essai anterieur.
- `GetClientLogEntries` : **failed** hors session (« No client log was found; start a play-in-client session first. »). Aucun log client n'a jamais ete obtenu.
- Aucune validation d'assets n'est accessible par MCP (`validate_folder` / `validate_selected` n'existent pas dans ce montage).

Procedure si l'utilisateur donne son accord explicite pour une session :
1. Verifier avant : `Verse.BuildAll` sans erreur, recoupe dans les logs `VerseBuild`.
2. Demander a l'utilisateur de lancer la validation d'assets dans l'editeur.
3. Appeler `StartSession` **une fois**. Puis `GetSessionStatus` toutes les 10 s jusqu'a un etat stable (`Connected` ou `Disconnected`). Ne pas relancer pendant `Connecting` / `UpdatingContent`.
4. Sur echec, ne relancer qu'une fois, puis arreter et rendre compte.
5. Les logs client exigent un client Fortnite lance et connecte. Lire `GetClientLogEntries` sans `maxResults` ou avec une valeur >= 1 (0 est refuse).
6. Rapport : dire ce qui a ete vu. Si aucun log client n'est lu, ecrire que le comportement en jeu **n'est pas verifie**.
