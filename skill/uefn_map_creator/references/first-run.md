# Premier test du skill : runbook

Objectif : verifier le skill de bout en bout, dans l'ordre, sans deviner. Chaque commande
annonce ce qu'elle a **relu** et ce qu'elle n'a pas verifie. Un `PASSED` obtenu sans editeur
ne prouve rien sur l'editeur.

## 0. Prealables

- Python **3.10 ou plus** (`python --version`). En dessous, le CLI s'arrete avec le code 2.
- Editeur UEFN ouvert sur un projet de test, serveur MCP officiel actif sur
  `http://127.0.0.1:8000/mcp` (localhost uniquement, jamais expose).
- Un niveau **jetable** : rien n'est sauvegarde par le skill, et `cleanup` supprime tous les
  acteurs portant le tag `UEFNMAP`. S'assurer que le niveau courant ne contient pas deja
  d'acteurs a ce tag avant tout test.
- Un dossier d'etat **hors du skill**, en chemin absolu :
  `C:/Users/<vous>/uefn-workspaces/test1`. Le CLI refuse un workspace a l'interieur du skill
  (`WORKSPACE_INSIDE_SKILL`) : l'etat d'une carte n'est pas un fichier du skill.
- Toutes les commandes ci-dessous se lancent depuis la racine du skill, avec un seul appel a la
  fois (jamais deux fenetres, jamais deux agents sur l'editeur).

Ce runbook n'a pas besoin que le skill soit installe : il appelle les scripts directement.
Pour le faire piloter par Qoder ensuite, le dossier doit porter le nom du frontmatter
(`uefn-map-creator`) et contenir `SKILL.md` :

```bash
cp -r "C:/Users/douco/Downloads/uefn-dashboard/skill/uefn_map_creator" \
      "C:/Users/douco/.qoder/skills/uefn-map-creator"
```

Cette copie **ecrase** l'exemplaire installe actuel, qui est obsolete : ne la lancer qu'apres
avoir decide de le remplacer.

```bash
WS="C:/Users/<vous>/uefn-workspaces/test1"
CLI="python script/uefn_spatial_cli.py"
```

## A. Repetition sans editeur (5 minutes)

```bash
python script/tests/verify.py
```

Attendu : `110/110 OK`, code retour 0. Le harness demarre un faux serveur MCP
(`script/tests/mock_mcp.py`, 127.0.0.1 seulement, detruit a la fin) et rejoue la chaine
complete, y compris les pieges documentes : `PlaceDevice` qui ignore le yaw, `teamIndex` relu
avec `teamType`, echelle perdue, session connectee, absence de ligne de succes de build.

Ce que cela prouve : les **contrats** du skill (codes retour, statuts, refus sans accord,
rapports honnetes). Ce que cela ne prouve pas : le comportement de l'editeur reel, les chemins
d'assets, les noms de proprietes, les signatures Verse.

## B. Chaine complete reelle, gabarit `blank` (15 minutes)

Le gabarit `blank` n'utilise que des assets du moteur (`/Engine/BasicShapes/Cube` mis a
l'echelle) : aucune chasse d'asset, la chaine est testable telle quelle.

| # | commande | attendu |
|---|---|---|
| 0 | `$CLI preflight --workspace "$WS"` | `PASSED`, `pagination_after: "200"`, `level` = le niveau ouvert. **Faire confirmer le niveau par l'utilisateur avant la premiere ecriture.** |
| 1 | `$CLI init --workspace "$WS" --template blank` | `PASSED`, 5 fichiers crees |
| 2 | `$CLI validate-grid --workspace "$WS"` | `PASSED`, 0 erreur |
| 3 | `$CLI validate-scene --workspace "$WS"` | `FAILED`, **une seule** erreur `PALETTE_EMPTY` (normal : rien n'est mesure) |
| 4 | `$CLI measure-palette --workspace "$WS" --dry-run` | `DRY_RUN`, 3 assets a mesurer |
| 5 | `$CLI measure-palette --workspace "$WS"` | `PASSED`, `02_palette.json` avec `measured`, `size_cm` et `pivot_offset_cm` relus |
| 6 | `$CLI validate-scene --workspace "$WS"` | `PASSED`, 0 erreur |
| 7 | `$CLI compile-transforms --workspace "$WS"` | `PASSED`, 2 acteurs, `scale` reporte dans `_compiled_scene.json` |
| 8 | `$CLI build-structure --workspace "$WS" --dry-run` | `DRY_RUN`, `operations: 32` |
| 9 | `$CLI build-structure --workspace "$WS"` | `PASSED`, sols et murs du perimetre poses, transforms relues |
| 10 | `$CLI place-scene --workspace "$WS"` | `PASSED`, `props.verified: 2` |
| 11 | `$CLI audit-scene --workspace "$WS" --live` | `PASSED`, `source: "live"`, `gravity_scope: "bounds relus dans l'editeur"` |
| 12 | `$CLI check-navigation --workspace "$WS"` | `PASSED`, `06_navigation_report.json` |
| 13 | `$CLI check-symmetry --workspace "$WS" --live` | `PASSED`, `source: "live"`, `axis: null` + un `scope` « AUCUN AXE » (le gabarit `blank` declare `symmetric: false`) |
| 14 | `$CLI visual-snapshot --workspace "$WS"` | `PASSED`, PNG ecrit (cadrage pitch -90 jamais teste en editeur : regarder l'image) |
| 15 | `$CLI cleanup --workspace "$WS"` | `PASSED`, `left: 0` — **apres accord de l'utilisateur** |

Points de controle visuels : apres l'etape 9, une dalle 4 x 4 avec ses murs de bord ; apres
l'etape 10, deux cubes de 120 cm, le second a 120 cm devant le premier.

Si une etape echoue, lire le `error_kind` / `errors[].type` et le champ `next` : ils disent quoi
corriger. Ne jamais relancer a l'aveugle apres un code 1 ou 3 (l'etat peut etre partiel) :
relire d'abord (`find_actors` par tag, `_placed.json`, `GetSessionStatus`).

## C. Carte jouable, gabarit `1v1_arena` (ce qui reste humain)

```bash
$CLI init --workspace "$WS2" --template 1v1_arena
$CLI validate-grid --workspace "$WS2"
```

Le gabarit suit `references/level-design-patterns.md` section 2 (8 x 8, spawns en `D2`/`E7`,
6 barils de reset en 3 paires, `Zone_Logic` sous l'arene). Il est declare `symmetric: true` avec
`symmetry_axis: "R180"` : chaque acteur de `04`/`05` a son jumeau dans la tuile opposee, ce que
`check-symmetry` verifie (puis `check-symmetry --live` sur la scene posee). Trois choses ne sont
**pas** automatisables sans verification humaine :

1. **Chemins d'assets manquants.** `barrier`, `round_timer` et `prop_ramp` ont `uefn_path: null`
   volontairement : un chemin invente est une erreur. Les trouver avec
   `Device.ListDeviceAssets {"nameFilter": "Barrier"}` et `Asset.find_assets`, puis les ecrire
   dans `01_gdd.json` avant `measure-palette`.
2. **Noms de proprietes et de bindings.** Les `properties` des gabarits viennent d'anciennes
   notes : `apply-properties` les confronte a `Object.list_properties` et signale
   `PROPERTY_NOT_FOUND` avec les noms les plus proches au lieu de deviner. Les `bindings` sont
   vides : les remplir avec les chaines exactes de `Device.GetBindingOptions` sur la source,
   puis `wire-devices` recroise par `ListEventBindings` sur la **cible**.
3. **Verse.** `verse-scan` puis `verse-grep --symbols <nom>` pour chaque signature utilisee dans
   `verse/game_manager_device.verse` (un Grep vide ne prouve PAS l'absence). `verse-write`
   refuse sans `--i-agree-to-modify-project` : montrer le code a l'utilisateur d'abord.
   `verse-build` exige une session `Disconnected` **et** une ligne de succes dans les logs.
   `list-editables` produit la table `@editable` -> `actor_label` -> `refPath` pour le cablage
   **manuel** : le cablage automatique des references d'acteurs est UNKNOWN.

Ensuite : `playtest-plan` imprime la demande d'accord et la sequence, sans rien lancer.

## D. Codes retour

| code | sens | quoi faire |
|---|---|---|
| 0 | `PASSED` : relu | continuer |
| 1 | `FAILED` : l'appel a ete traite, l'etat peut etre **partiel** | relire avant de rejouer ; corriger la cause |
| 2 | editeur injoignable : **rien** n'a ete execute | verifier l'editeur et le port 8000 |
| 3 | timeout : etat **inconnu** | relire (`find_actors`, `_placed.json`) puis rejouer seulement ce qui manque |

Un timeout pendant `place-scene` peut laisser un device **sans label** (le label est pose par un
appel suivant) : chercher les devices sans le tag `UEFNMAP` avant de relancer.

## E. Interdits sans accord explicite de l'utilisateur

`Save` / `SaveAll`, publication, `StartSession` / `StopSession` / `PushChanges`,
`EnablePythonInUEFN`, tout outil qui modifie un asset du projet, `VerseToolset.WriteFile`
(necessite `--i-agree-to-modify-project`). Fermer le niveau sans enregistrer annule la
construction : le dire a l'utilisateur a la fin.

## F. Ou sont les preuves

| fichier | ecrit par |
|---|---|
| `01_gdd.json` … `05_props.json` | `init`, puis l'utilisateur / l'etape 1 a 7 |
| `06_audit_report.json` | `audit-scene` (`source` : `live`, `compiled` ou `not_live`) |
| `06_navigation_report.json` | `check-navigation` |
| `07_properties_report.json` | `apply-properties` |
| `08_wiring_report.json` | `wire-devices` |
| `09_verse_report.json` | `verse-build` |
| `10_editables.json` | `list-editables` |
| `11_symmetry_report.json` | `check-symmetry` (`source` : `live`, `compiled` ou `not_live`) |
| `_compiled_structure.json`, `_compiled_scene.json`, `_placed.json` | calculs et poses |
| `_verse_files.json`, `_verse_grep.json`, `_verse_written.json` | etape 8 |
| `_mcp_calls.jsonl` | journal de chaque appel MCP du CLI |

Chaque rapport porte un champ `scope` qui dit ce qu'il ne verifie **pas**. Le rapport final a
l'utilisateur separe : prouve (relu), inconnu, non lance.
