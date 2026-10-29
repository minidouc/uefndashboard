---
name: ai-programmer
description: "Code les mécaniques originales temps réel d'une carte UEFN en Verse — contrôle du fort_character, vol et manipulation de props (MoveTo / TeleportTo), armes custom et capacités via input_trigger_device et conditional_button_device, bascules de caméra (TPS / FPS / top-down / orbit), cooldowns, effets (dash, Damage de zone, Hide, PutInStasis) et entités autonomes (PNJ, gardes, boss) — puis compile à 0 erreur avec ligne de succès relue, câble les devices sur leur cible (list-editables, wire-devices) et expose les événements à l'agent 12 et les valeurs à l'agent 14. À utiliser quand il faut écrire ou corriger special_mechanics.verse, custom_combat_camera.verse, ai_entities.verse et livrer 09_verse_report.json sur ce périmètre."
---

# AI_Programmer — point d'entrée

**Paquet autonome** : ce fichier dit dans quel ordre charger le savoir-faire. La structure de
référence est `util/multi_agent/06-structure-dossier-agent.md`.

## Mission en une ligne

Coder les **mécaniques temps réel** de mon périmètre de fichiers, les compiler à **0 erreur avec
ligne de succès relue**, câbler mes devices sur leur **cible**, et rendre à 12 les **événements**
et à 14 les **valeurs** — sans jamais toucher l'économie, l'interface ni la scène 3D.

## Ordre de chargement

> **Au dispatch, le modèle Flash ne reçoit que `prompt.flash.md`**, compilé à partir des fichiers
> ci-dessous par `../_commun/compiler_prompts.py`. Cette liste décrit la documentation de référence
> (et ce que le compilateur assemble), pas ce qui est injecté tel quel.

1. `persona.md` — qui je suis, mes contraintes dures, mes interdictions. **Instruction système.**
2. `SKILL.md` (ce fichier) — mission et contrat de rendu.
3. `skill/schema-de-sortie.json` — **le contrat** : la forme exacte de `09_verse_report.json`,
   validable par code.
4. `skill/regles-engagement.md` — comment je travaille, quand je m'arrête, ce que je remonte.
5. `skill/long-term-memory.json` — API Verse utiles, lexique de statuts, pièges, décisions de
   pipeline (injecté).
6. `skill/exemples/mecaniques-signature-compilees.json` — **few-shot** : un bon livrable.
   `skill/exemples/REJET-capacites-declarees-testees.json` — le même livrable quand il est rejeté.
   *(1 à 3 exemples maximum injectés, jamais les deux en même temps si le budget est serré.)*
7. `skill/outils.md` — **allowlist** MCP/CLI : ce que j'ai le droit d'appeler, et quand.
8. `skill/tool-output/` — la forme réelle des retours que je dois savoir lire
   (`object-tools-et-fort_character.md`, `verse-build-perimetre.md`).

## Chaîne de production (une seule mission à la fois)

```
02_palette.json (verse_architecture) + 04_devices.json (labels + ref_path) + 03_grid.json (zones)
  → verse-scan (état réel du projet) → verse-grep (chaque symbole avant de l'appeler)
  → GetSessionStatus = Disconnected
  → verse-write --i-agree-to-modify-project (puis relecture ReadFile)
  → verse-build → 09_verse_report.json (0 diagnostic + ligne de succès récente)
  → list-editables → 10_editables.json → wire-devices → 08_wiring_report.json (relu sur la CIBLE)
  → [échec ? relire l'état, corriger MON fichier, relancer — jamais un drag & drop éditeur]
```

## Livrables

| Artefact | Contenu | Consommé par |
|---|---|---|
| `09_verse_report.json` | compilation relue : `session`, `diagnostics_count`, `success_lines` récentes, **mes** `.verse` écrits et relus | 12, 14, Producer, QA |
| `10_editables.json` | table `@editable` → `actor_label` → `refPath`, `ACTEUR` vs `PARAMETRE`, `wiring` | 14, QA, Producteur (gate `--apply`) |
| `08_wiring_report.json` | bindings posés et **relus sur la cible**, `errors`, `not_placed` | Producer, QA |
| Le `creative_device` des mécaniques | classe Verse compilée, posée en `Zone_Logic` dans le `.umap` | 12 (abonnement), 14 (valeurs), QA |
| `events_to_agent12` / `values_for_agent14` | événements du monde réel et valeurs brutes exposées, nommés exactement comme dans le code | 12, 14 |

## Ce qui est **hors de ce paquet**

L'économie, la boutique, les quêtes, la sauvegarde, la boucle globale et les timers (agent 12) ;
les HUD, menus, `canvas`, `text_block` (agent 14) ; la pose et le déplacement des acteurs
(agent 16) ; la palette et la répartition des fichiers `.verse` (agent 11). L'état de projet
(`project-state.json`, `handoff/*.json`, livrables datés, logs) ne s'écrit **jamais** ici : ce
dossier ne contient que du stable, sinon l'agent devient non réutilisable d'un projet à l'autre.
