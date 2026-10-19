# Guide des Finitions Visuelles, Reperes Spatiaux et Fiabilisation Session PIC

## 1. Regle d'Or de l'Habillage : Lisibilite sans Obstacle Gameplay

Dans les modes compétitifs (1v1, Box Fight, Zone Wars), un joueur qui construit rapidement perd facilement son orientation cardinale si l'environnement est uniforme, mais tout décor placé au milieu de l'aire de jeu gêne la pose des murs.

**Loi de placement des finitions :**
- **0 décor collidable à l'intérieur des tuiles de combat** (toutes les tuiles internes `.` et `O` restent libres à 100%).
- **100% des finitions visuelles** sont placées sur la **périphérie extérieure** (coins, bordures de plateforme) ou **hors de portée** (colonnes d'horizon, éclairage).

---

## 2. Les 3 Couches de Finition Obligatoires (Etapes 4 et 6)

### Couche 1 : Balisage Vertical des 4 Coins (Repères d'Horizon)
Sur toute plateforme ouverte (`edge_policy: "fall_zone"`), encadrer les 4 angles extérieurs de l'arène (`A1`, `H1`, `A8`, `H8`) avec un assemblage vertical à trois niveaux testé et validé sans chevauchement :
1. **Base au sol** : `maze_pylon` (`/CRG_Maze/SetupAssets/Meshes/CP_Maze_Pillar_Pylon_01`, taille `[106.4, 106.9, 61.9]` cm) posé sur l'ancre de coin (`CORNER_SW`, `CORNER_SE`, `CORNER_NW`, `CORNER_NE`) avec `snap_to_floor: true`.
2. **Elément lumineux / Orbe** : `maze_pylon_orb` (`/CRG_Maze/SetupAssets/Meshes/CP_Maze_Pillar_PylonOrb_01`, taille `[96.4, 95.9, 96.4]` cm) placé en `ON_TOP_OF` la base avec `gap_cm: 10.0`.
3. **Colonne de silhouette haute** : `pillar_mole` (`/MoleEnvironments/Meshes/Creative/Factory/CP_Mole_Factory_Pillar_01`, taille `[87.8, 75.8, 868.0]` cm) placé sur les coins pour donner une référence verticale visible même lorsque les joueurs construisent à 3 ou 4 étages de hauteur.

### Couche 2 : Différenciation Visuelle Nord / Sud (Orientation Joueur)
Pour qu'un joueur sache instantanément après un `TeleportTo` ou un edit à 360° de quel côté se trouve le camp adverse :
- Utiliser une composition asymétrique sur la hauteur des pylônes ou des balises : par exemple placer les grandes colonnes `pillar_mole` (`868 cm` de haut) uniquement du côté **Nord** (derrière `S2`) et les orbes lumineux `maze_pylon_orb` du côté **Sud** (derrière `S1`), tout en conservant une empreinte au sol symétrique.

### Couche 3 : Bordure de Sécurité Visuelle (`fall_zone`)
- Sur les cartes à bords ouverts, le joueur doit percevoir clairement la limite des `4096 x 4096 cm` avant de tomber sous `FloorZ - 1200 cm`.
- Les 4 pylônes d'angle marquent exactement les sommets du carré `8 x 8` tuiles : aucune construction ou déplacement au-delà de la ligne reliant deux pylônes d'angle n'est supporté par une dalle.

---

## 3. Fiabilisation du Playtest en Session Fortnite PIC (Etape 10)

### 3.1 Pourquoi `GetClientLogEntries` retourne parfois `No client log was found`
Lorsque `StartSession` est appelé via `ValkyrieToolset.SessionToolset`, UEFN cuisine et envoie le contenu vers un serveur de session distant (`Connected` / `Running`). Mais si l'exécutable du client de jeu Fortnite n'est pas lancé localement sur la machine (ou qu'aucun joueur local n'a rejoint la session), aucun fichier `FortniteGame.log` récent n'est alimenté et `GetClientLogEntries` reste vide.

### 3.2 Procédure Obligatoire à l'Etape 10 pour Valider les 2 points finaux de la Checklist

1. **Validation Préalable des Assets (`0 Asset Error` avant `StartSession`)** :
   - Avant même de lancer `StartSession`, exécuter la validation UEFN sur tous les acteurs du niveau.
   - Si un `item_granter_device` échoue la validation à cause d'une arme interdite, **ne jamais utiliser uniquement le bouton "Effectuer la correction"** (qui laisse le Granter vide) : remplacer immédiatement la propriété `item_asset` par une arme autorisée de `devices-catalog-and-wiring.md` et revalider jusqu'à obtenir `0 Asset Error` avec les 2 Granters pleins.
2. **Gestion du Timeout Transitoire sur `StartSession`** :
   - Il est normal que le premier appel à `StartSession` échoue parfois avec `The session left the content update without becoming connected` (`Disconnected`) le temps que le backend Epic provisionne l'instance.
   - Toujours vérifier `GetSessionStatus` et relancer **une seule fois** `StartSession` : la seconde tentative passe en `Connected` + `Running`.
3. **Vérification des Logs Client (`GetClientLogEntries`)** :
   - Appeler `GetClientLogEntries` une fois la session `Running`.
   - Si le retour est `No client log was found` alors que la compilation Verse affiche `0 Error`, que les 11/11 propriétés `@editable` ont leur `savedActor` vérifié en relecture et que la validation d'assets affiche `0 Error`, consigner dans le rapport que la session serveur tourne mais nécessite la connexion d'un client Fortnite local pour observer les 22 lignes `[ASSERT_OK]`.