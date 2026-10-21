# Patrons Architecturaux de Level Design UEFN par Mode de Jeu

## 1. Regles Universelles de Topologie UEFN

1. **Decalage Obligatoire de l'Origine (`Brush_0` Avoidance)** :
   Chaque niveau UEFN contient un volume par defaut `Brush_0` autour de `[-128..+128 cm]`. Toute zone de jeu (`Zone_Arena`) doit avoir son origine decalee d'au moins **2 tuiles** (`origin_tile: [2, 2, 0]`) pour eviter toute collision fantome.
2. **Isolement de la Zone Technique (`Zone_Logic`)** :
   Tous les appareils non-spatiaux (`item_granter`, `score_manager`, `end_game`, `hud_message`, `creative_device` Verse) doivent etre regroupes sur une plateforme de service dediee `Zone_Logic` placee a `origin_tile: [-12, 2, -6]` (soit **61.44 m a l'Ouest** bord-a-bord et **23.04 m sous l'arene**).
3. **Compensation Asymetrique des Dalles de Sol (`arena_floor`)** :
   La dalle standard `/CR_Legacy/Playsets/PlaysetProps/PPID_CR_Legacy_Obstacle_Course_Floor_01` mesure `[512.0, 512.0, 31.921]` cm mais son point de pivot est decale sur l'axe Y (`min_cm: [-256, 0, -16]`, `max_cm: [256, 512, +15.92]`). Toujours utiliser son `bounds_center_offset_cm: [0, +256, -0.04]` issu de `02_palette.json` pour aligner les 64 dalles sans interstice.

---

## 2. Patron Officiel Mode 1 : `1v1 Build Fight` (`8 x 8` tuiles)

### Pourquoi un plateau 100% vide est insuffisant
Un vrai **1v1 Build Fight** competitif ne se contente pas d'un plateau plat : il exige un **Pad de Depart Central (`O`)** au milieu de l'arene compose de **2 rampes de depart face-a-face (ou dos-a-dos)** separees par une barriere de depart, ainsi qu'un **maillage de 5 barils explosifs** (4 aux coins + 1 au centre sous le pad de depart) pour garantir que 100% des constructions s'effondrent entre chaque manche.

### Architecture Spatiale Obligatoire (`Zone_Arena` 8x8)
- **Dimensions** : `8 x 8` tuiles (`4096 x 4096 cm`), `edge_policy: "fall_zone"`, `symmetry: "rotate_180_swap_teams"`.
- **Position des Spawns** :
  - `Spawner_P1_01` en tuile `D2` (`[3, 1, 0]`), `slot: "CENTER"`, `face_towards: "NORTH"`.
  - `Spawner_P2_01` en tuile `E7` (`[4, 6, 0]`), `slot: "CENTER"`, `face_towards: "SOUTH"`.
  - Distance inter-spawns : `2611 cm` (~2.9 secondes de sprint).
- **Structure de Duel Centrale (Tuiles `D4` et `E5` ou `D4` et `D5`)** :
  - Placer **2 rampes de depart** menant l'une vers l'autre au centre (`O`), orientees exactement dans l'axe des deux joueurs (`NORTH` pour P1, `SOUTH` pour P2).
  - Placer une `barrier_device` centrale entre les deux rampes qui bloque le passage pendant les 3 secondes de `Countdown` et se desactive au signal `COMBAT !`.
- **Disposition en Quinte des Barils de Reset (`5 explosive_device`)** :
  - `Reset_Explosive_01..04` sur les 4 coins (`[0,0,0]`, `[7,0,0]`, `[0,7,0]`, `[7,7,0]`).
  - `Reset_Explosive_05` au **centre exact de l'arene (`[3, 3, 0]` ou `[4, 4, 0]`)** pour detruire immediatement les deux premieres rampes posees par les joueurs et provoquer l'effondrement par gravite de toute la tour de build.

---

## 3. Patron Officiel Mode 2 : `Box Fight` (`4 x 6` ou `6 x 6` tuiles fermees)

### Architecture Spatiale Obligatoire
- **Enveloppe** : Boite **100% close** sur 2 etages (`Z = 0` et `Z = 1`, hauteur sous plafond totale = `768 cm` soit 2 tuiles de build en hauteur) avec murs `#` sur tout le perimetre et plafond plein au-dessus de `Z = 1`.
- **Aucune couverture pre-placee au centre** : L'interieur de la boite doit etre parfaitement vide pour permettre la pose de grilles de construction Fortnite sur 100% des cases.
- **Barriere de Pre-Manche** : Deux `barrier_device` couvrant toute la largeur de la boite devant la rangee de spawn de l'Equipe 1 (rangee 1) et de l'Equipe 2 (rangee `N-2`), desactivees apres 3 secondes de compte a rebours pour laisser le temps aux joueurs de boire leurs potions et pre-editer leur mur.

---

## 4. Patron Officiel Mode 3 : `Zone Wars` / `Red vs Blue` (`> 8 x 8` tuiles)

### Regle de Decoupage en Zones (Chunking)
- Diviser obligatoirement le niveau en **3 Zones** dans `01_gdd.json` :
  - `Zone_A_BaseTeam1` (`6 x 6` tuiles)
  - `Zone_B_Midground` (`8 x 8` tuiles avec couvertures symetriques)
  - `Zone_C_BaseTeam2` (`6 x 6` tuiles, image miroir a 180° de `Zone_A`)
- **Regle des Lignes de Vue (Sightline Blocking)** : Ne jamais laisser une ligne de tir directe et degagee entre un `Player Spawner` de la `Zone_A` et un `Player Spawner` de la `Zone_C` (Anti-Spawn Kill). Toujours interposer un mur d'ecran ou un obstacle central sur la ligne mediane de `Zone_B`.