# Runbook : lancer et faire tourner le studio

## 0. Installation (une fois)
```bash
cd C:/Users/douco/Downloads/uefn-dashboard/new-agent-architecture
python tools/test_garde.py                     # 19 cas du hook : doit afficher TOUT BON
python validators/run_all.py --golden-seulement # integrite OK + golden OK
```
Ensuite, ouvrir Claude Code **dans ce dossier** : les hooks, les permissions et les sous-agents
sont charges automatiquement.

## 1. Actions reservees a l'humain
| Action | Commande |
|---|---|
| Modifier un validateur, puis le reverrouiller | editer `validators/...`, puis `python tools/lock_validators.py`, puis `python validators/run_all.py --golden-seulement` |
| Regenerer le golden set | `python tools/make_golden.py`, puis `python tools/lock_validators.py` |
| Autoriser un nouvel outil d'ecriture MCP | deplacer l'outil vers `ecritures_prouvees` dans `config/studio.json`, avec la preuve |
| Couper un outil en urgence | `config/circuit_breakers.json` : `outils_coupes` ou `ecritures_coupees: true` |
| Modifier les hooks ou les permissions | `.claude/hooks/`, `.claude/settings.json` |

## 2. Nouvelle map, de n'importe quel type (chemin rapide)
```bash
python scripts/nouveau_projet.py mon-arene --profil arene --root "C:/Users/douco/Documents/Qoder/mon-arene" --content-root /<guid> --niveau <NomDuNiveau>
set STUDIO_PROJET=mon-arene              # PowerShell : $env:STUDIO_PROJET="mon-arene"
python scripts/generer_plan.py --liste   # parametres disponibles
python scripts/generer_plan.py --params '{"taille_uu": 10000, "joueurs_par_equipe": 6}'
python scripts/state.py gate --nom brief --citation "..."   # puis phase DESIGN, gates gdd / archi / ecriture_uefn, phase BUILD
python scripts/build_complet.py --jusqua 1                  # premier lot pour verifier
python scripts/build_complet.py                             # le reste
```
Puis le sous-agent `critique` sur `build/studio/captures/`, et la gate DA humaine.

**Nouveau type de map :**
1. Copier `config/profils/arene.json` et l'adapter (gameplay requis, captures, ordre de pose).
2. Ecrire `scripts/generateurs/<type>.py` (sur le modele de `arene.py`, environ 50 lignes).
3. Lancer `generer_plan.py` jusqu'a ce que la verification soit PASS.

## 2 bis. Redemarrer corpo-plaza proprement (recommande)
L'editeur contient environ 328 acteurs poses par l'ancien run, hors architecture : ils ne sont
pas valides et sont rehausses par le defaut de Z. On repart sur une base saine.

1. **Ouvrir UEFN** sur `MyProjectArtyu`, MCP actif sur le port 8000.
2. **Baseline des 24 preexistants**, a partir de la preuve relue pendant le spike :
   ```bash
   python scripts/preflight.py --baseline-depuis "C:/Users/douco/Documents/Qoder/corpo-plaza/tech/spikes/SPIKE-VISUAL-CAPACITY/ws/T0bis_acteurs_preexistants_24.json"
   ```
   Resultat attendu : un ecart du type « ~328 acteurs ni preexistants ni ranges », donc les
   restes de l'ancien run.
3. **Nettoyer l'ancien run** : d'abord la simulation, puis le reel apres avoir verifie la liste.
   ```bash
   python scripts/rollback.py --hors-baseline --dry-run
   python scripts/rollback.py --hors-baseline
   ```
4. **Etat initial :**
   ```bash
   python scripts/state.py init --phase DESIGN
   ```
   Puis l'utilisateur redonne les gates, avec ses mots exacts : `gdd`, `archi`, `ecriture_uefn`.
5. **Corriger le plan** avant toute pose. Mission au `level-designer` :
   - corriger les defauts de `python scripts/check_plan.py`, dont l'escalier C2 a 900 uu des
     surfaces S0/S1 ;
   - declarer les exceptions justifiees (volumes DELTA, decals au sol, bannieres de facade) ;
   - ecrire `cameras.json`.
6. **Debloquer la DA** :
   ```bash
   python scripts/spike_capacite.py palette PPID_CRP_Sunburst
   ```
   Puis `poser-asset` sur un prop. Si c'est prouve, le level designer remplace des cubes par des
   `ASSET:`.
7. **Passer en BUILD.** Version rapide : `python scripts/build_complet.py --jusqua 1`, puis
   `python scripts/build_complet.py`. Version lot par lot (depannage) :
   ```bash
   python scripts/state.py phase --vers BUILD
   python scripts/pose_lot.py plan --refaire     # seulement si le plan a change
   python scripts/pose_lot.py simuler 1
   python scripts/pose_lot.py lot 1
   python scripts/capture.py prendre S-1 --lot lot_01
   python validators/run_all.py
   python scripts/state.py lot --id lot_01 --statut VALIDE   # refuse si le lot n'est pas PASS
   ```
   Puis le sous-agent `critique` sur la capture. On recommence lot par lot.
8. **Nuit et DA** : lot du delta, captures `nuit_*`, critique, puis **gate humaine** sur les images.

## 3. Pannes courantes
| Symptome | Quoi faire |
|---|---|
| `rc=2 OFFLINE` | UEFN ferme ou MCP inactif. Rien n'a ete ecrit |
| `rc=3 TIMEOUT` | etat INCONNU : relancer `preflight.py` avant toute action |
| `rc=4 UNKNOWN_TOOL_BLOCKED` | outil non prouve. Faire un spike, puis une decision humaine dans `studio.json` |
| `rc=5 JAUGE_RAM` | fermer des applications. Rien n'a ete ecrit |
| Lot `INTERROMPU` | lire le champ `arret`, puis `rollback.py --lot N`, corriger, reposer |
| `integrite: ALTERE` | quelqu'un a modifie `validators/`. Verifier le diff git avant de reverrouiller |
| `golden: ECHEC` | un validateur ne detecte plus un defaut : NE PAS reverrouiller, corriger le validateur |
