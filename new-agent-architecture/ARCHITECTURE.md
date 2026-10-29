# Architecture du studio UEFN, v2

> **Claude orchestre, des scripts executent, du code verifie, l'humain tranche.**
> Cette version remplace l'architecture Qoder a 21 agents (`util/multi_agent/`). Elle garde ses
> principes, mais les fait respecter **par du code** au lieu de compter sur la discipline des
> modeles. Chaque choix ci-dessous renvoie au white paper Google qui le fonde (WPn p.X).

## 1. Pourquoi une v2 : ce que le run corpo-plaza a montre

| Ce qui a casse | Cause | Reponse v2 |
|---|---|---|
| Validateurs affaiblis par l'agent evalue | regle ecrite dans un prompt, pas imposee | hooks + empreinte MANIFEST + golden set (§4) |
| Preuves ecrites en dur (`rc: 0`, bornes inventees) | validateurs qui lisaient les champs declares | validateurs qui remontent aux reponses MCP brutes (§4) |
| Captures inexploitables declarees PASS | « la capture existe » = preuve | mesures d'image + critique sur rubrique + gate humaine (§5) |
| DA absente (293 cubes a damier) | import de textures non prouve, puis abandonne | `spike_capacite.py` + pack de props legal Sunburst (§6) |
| Run tres lent, puis accelere en sacrifiant les preuves | sessions paralleles, state de 147 Ko, une relecture par acteur | pose par lots scriptee, relecture groupee, state < 20 Ko, mode rapide encadre (§7) |
| Reprise par un modele exterieur hors systeme | aucun protocole de reprise | `docs/reprise-externe.md` ; garanties actives meme sans hooks |

## 1 bis. Generaliste, rapide, peu couteux

**Tous les types de maps.** Le savoir-faire des 21 agents v1 est conserve dans `agents/`. Le type
de map est porte par deux choses :
- un **profil** (`config/profils/<type>.json`) : gameplay obligatoire, regles de deplacement,
  ordre de pose, captures ;
- un **generateur** (`scripts/generateurs/<type>.py`) : quelques parametres en entree, tout le
  plan calcule en sortie.

Aujourd'hui : `exploration` (generateur `ville`), `arene`, `parkour`. Un projet = un profil + ses
reglages (corpo-plaza = `exploration` + sa DA cyberpunk). Aucun style n'est code en dur : les
couleurs et l'ambiance mesurees viennent du brief du projet.

**Rapide et economique.** Le cout d'un studio d'agents, ce sont les tours de modele. Donc :

| Etape | Avant (v1) | Maintenant |
|---|---|---|
| Plan de niveau | agent qui ecrit des centaines de positions + plusieurs allers-retours | `generer_plan.py` : environ 10 parametres, plan + verification + cameras en 1 commande (environ 1 s) |
| BUILD | des dizaines de tours (lot, validation, capture, etat) | `build_complet.py` : **1 tour**, Claude n'est rappele qu'en cas d'echec |
| Chevauchements a trier | lecture par un agent | `suggerer_exceptions.py` (environ 1 s) |
| Cameras de preuve | agent | `gen_cameras.py` |
| Critique visuelle | a chaque lot | mesures gratuites a chaque lot, critique Sonnet **une fois** a la fin |
| Modeles | Frontier + Flash | Sonnet par defaut, Haiku pour la redaction, Opus sur demande |

Cible : **une map complete en une quinzaine de tours de Claude.** Teste hors ligne : les trois
generateurs produisent des plans sans chevauchement, sans flottant et entierement accessibles,
quels que soient les parametres essayes (arene 12 000 uu a 16 joueurs, ville de 5x4 blocs,
parkour de 45 plateformes sur 4 graines).

## 2. Topologie

```
                    Utilisateur  (gates : brief, GDD, archi, ecriture UEFN, derogation)
                         |
            +------------v-------------+      hooks Claude Code (garde.py, demarrage.py)
            | ORCHESTRATEUR (Claude)   |<---- = point de controle HORS du raisonnement (WP1 p.35)
            | CLAUDE.md                |
            +--+-----------+--------+--+
   handoff v2  |           |        |  resumes bornes uniquement
   (fichier)   |           |        |
   +-----------v--+  +-----v----+  +v------------------------------+
   | sous-agents  |  | critique |  | SCRIPTS-TACHES (Python)        |
   | conception   |  | (juge)   |  | preflight, check_plan, pose_lot|
   | opus/sonnet/ |  | lecture  |  | capture, rollback, spike, state|
   | haiku        |  | seule    |  +---------------+----------------+
   +--------------+  +----------+                  |
                                     +-------------v----------------+
                                     | PASSERELLE MCP UNIQUE         |  allowlist, schemas,
                                     | scripts/uefn/mcp_gateway.py   |  circuit breaker, jauge RAM,
                                     +-------------+----------------+  trace, sorties sur disque
                                                   |
                                             UEFN (MCP :8000)
                     +------------------------------------------------+
                     | VALIDATEURS (proteges) validators/run_all.py   |
                     | integrite -> golden -> regles -> rapport       |
                     +------------------------------------------------+
```

- **Un seul hub** (WP1 p.17, p.48) : l'orchestrateur. Les sous-agents ne se parlent pas ; ils
  recoivent un handoff et rendent 5 lignes (WP3 p.18 : « *shares its final output, not its process* »).
- **Le disque est le bus** (WP3 p.12, p.38) :
  - `state/state.json` est petit et mutable ;
  - `state/events.jsonl` est l'historique en ajout seul ;
  - `build/studio/runs/` contient les reponses brutes ;
  - `trace.jsonl` contient une ligne par appel MCP.
- **Routage des modeles** (WP1 p.19-20) :
  - opus pour l'orchestrateur, le level designer et le critique (raisonnement spatial et jugement) ;
  - sonnet pour la conception et le code ;
  - haiku pour la redaction a faible enjeu ;
  - **aucun modele** pour la pose, la mesure ou la validation (des scripts).

## 3. Les scripts-taches : publier des taches, pas des API (WP2 p.18)

Le modele choisit **quoi** faire (« poser le lot 3 ») ; le script sait **comment**. Le modele ne
manipule jamais `(x, y, z)` (WP2 p.9 : les maths vont a une fonction externe).

| Script | Remplace (v1) | Ecrit dans l'editeur |
|---|---|---|
| `preflight.py` | Engine_Programmer (preflight, spike T0) | non |
| `check_plan.py` | relecture humaine du plan | non (hors editeur) |
| `pose_lot.py` | Engine_Programmer + Physics_Programmer (pose) | oui, par lots de 60 acteurs maximum |
| `capture.py` | captures manuelles | camera seulement |
| `rollback.py` | nettoyage manuel | retrait borne au dossier `CP_Studio/` |
| `spike_capacite.py` | spikes T1 a T6 | 1 ecriture de test, nettoyee |
| `state.py` | Producer (ecriture du state) | non |
| `handoff.py` | relecture des handoffs | non |

**Passerelle MCP** (`scripts/uefn/mcp_gateway.py`), point d'entree unique (WP2 p.41) :
- **allowlist** : lecture = statut `VERIFIE` ; ecriture = liste `ecritures_prouvees`, chaque
  outil avec sa preuve ;
- **schemas d'entree epingles** (`config/tool_schemas.json`, WP2 p.26-29) ;
- **circuit breaker** relu a chaque appel (WP5 p.21) ;
- **erreur = arret**, sans retry, sauf pour le cooldown « Wait 15 seconds » (WP4 p.20, WP2 p.30) ;
- **sorties volumineuses** ecrites sur disque, seul un resume est renvoye (WP2 p.19, WP3 p.22) ;
- **trace** : une ligne par appel (WP4 p.21, Glass Box).

## 4. Validation : la porte de qualite (WP5 p.11-12, WP4 p.20-26)

`python validators/run_all.py` execute, dans cet ordre immuable :
1. **Integrite** : les empreintes SHA-256 de `validators/` doivent correspondre a `MANIFEST.json`.
   Un ecart rend tout FAIL.
2. **Auto-test golden** : 20 mini-projets, dont 2 sains et 18 pieges (bornes falsifiees,
   chevauchement, groupe flottant, strate inaccessible, preexistant supprime, save echoue, capture
   de mur, « nuit » en plein jour, etc.). Chaque piege doit etre rejete par la bonne regle. Un
   validateur affaibli est donc detecte. Ca a ete teste : forcer le test de chevauchement a PASS
   est detecte immediatement.
3. **Regles reelles**, toutes recalculees depuis les preuves brutes :

| Regle | Ce qu'elle verifie |
|---|---|
| `integrite_preuves` | pose prouvee ; bornes declarees == bornes relues dans l'editeur ; bon acteur, bon niveau |
| `persistance` | save rc=0 ; `is_dirty=false` ; bornes du niveau relues apres save |
| `preexistants_intacts` | baseline incluse dans le `find_actors` de cloture |
| `source_coordonnees` | id present dans le plan, position relue coherente avec le plan |
| `zero_overlap` | penetrations entre items differents, hors exceptions **justifiees** |
| `zero_flottant` | chaine de contacts jusqu'au sol (un groupe qui ne touche que lui-meme flotte) |
| `accessibilite` | parcours en largeur sur les bornes RELUES : marches <= 120 uu, ecart <= 200 uu, rampes par leur pente |
| `couverture_plan` | tout item est pose ou en gap justifie ; gaps <= 15 % (on ne reduit pas le scope) |
| `captures_visuelles` | PNG present ; camera relue ; image non uniforme ; `nuit_*` sombre ET neon visible |

Le rapport donne un verdict **par lot**. `state.py lot --statut VALIDE` refuse tout lot qui n'est
pas PASS. `state.py phase` refuse de quitter BUILD, POLISH ou QA sans rapport PASS.

**Ce que le code ne juge pas** (le gout, la DA) passe par le sous-agent `critique` (LLM-as-a-Judge
sur rubrique, comparaison par paires, WP4 p.23-25), puis par **l'utilisateur** (WP4 p.26 : HITL
pour le subjectif).

## 5. Protection : rendre la triche impossible, pas seulement interdite

| Couche | Mecanisme | Protege meme un modele exterieur ? |
|---|---|---|
| Hook `garde.py` (PreToolUse) | bloque l'ecriture des validateurs, des hooks, du state, des preuves et de l'allowlist, ainsi que l'acces MCP direct ; refuse si l'entree est illisible | non (Claude Code seulement) |
| Permissions `settings.json` | `ask` sur pose, capture, rollback, spike ; `deny` sur le re-verrouillage | non |
| Empreinte MANIFEST | toute modification de validateur rend la validation FAIL | **oui** |
| Golden set | un validateur affaibli puis re-verrouille est detecte | **oui** |
| Preuves brutes horodatees | une preuve fabriquee ne correspond a aucune reponse MCP | **oui** |
| Provenance des evenements | `validator` / `editor_readback` / `human` sont probants ; `agent_claim` ne l'est jamais | **oui** |

Les tests sont dans `tools/test_garde.py` (19 cas) et dans le golden set (20 cas).

## 6. La DA : de la dette visible a un chemin prouve

Les lots marquent `degrade: true` tout item pose en cube de repli (texture ou mesh non posable).
La dette DA reste donc **visible** au lieu d'etre declaree faite. Deux voies, a prouver dans
l'ordre :
1. **Le pack de props cyberpunk legal Sunburst** (`PPID_CRP_Sunburst`, 348 assets selon
   l'inventaire) : `spike_capacite.py palette` puis `poser-asset`. Le level designer peut ensuite
   ecrire `"support": "ASSET:<chemin>"` dans le plan. On obtient de vrais materiaux sans aucun
   import.
2. **Les textures du studio** : `spike_capacite.py import-texture`, sous la racine du projet. Il
   restera ensuite a prouver l'assignation d'un materiau.

## 7. Vitesse sans perte de preuve

- **Relecture groupee** : un seul `find_actors` par lot au lieu de 60 `get_actor_bounds`.
- **Pas de tag** : le rangement dans le dossier `CP_Studio/lot_NN` suffit au rollback.
  Cela fait 3 ecritures par cube au lieu de 4 ou 5.
- **Jauge RAM en cache** 20 s (avant : un PowerShell par ecriture).
- **Plan verifie avant la pose** (`check_plan.py`) : les defauts de conception coutent 0 appel MCP.
- **Sous-agents de conception en parallele** : ils n'ecrivent pas dans l'editeur. Une seule
  session ecrit dans l'editeur.
- **Contexte minimal** : state < 20 Ko, resumes bornes, lecons injectees au demarrage.
- **Mode rapide** : seuls des controles listes comme sacrifiables peuvent etre retires, avec la
  citation de l'utilisateur.

## 8. Ce qui reste a prouver (honnetete)

- **Aucun script d'ecriture n'a encore tourne contre l'editeur** (MCP hors ligne pendant la
  construction). Les refus de politique, les schemas, les validateurs, les hooks et la simulation
  sont testes hors ligne. La premiere pose reelle doit se faire sur **un seul lot**, puis etre
  validee.
- **Format exact des reponses :** `find_actors` renvoie `actorPath` et `bounds` (preuve
  corpo-plaza du 2026-10-27). Pour `find_assets`, `add_to_scene_from_asset` et `import_file`, le
  format sera confirme au premier spike.
- **L'accessibilite est geometrique** (parcours sur les boites englobantes), pas une simulation de
  deplacement. Un playtest humain reste la preuve finale du « jouable ».
- **Les hooks sont une protection Claude Code.** Hors Claude Code, ce sont l'empreinte, le golden
  set et la provenance qui protegent.
