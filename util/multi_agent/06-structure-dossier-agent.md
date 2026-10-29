# 06 · Structure du dossier d'un agent

> **Spec structurelle** — décrit l'arborescence physique d'un agent du studio et le rôle de
> chaque fichier. Chaque agent est un **paquet autonome** (même logique qu'un skill
> QoderWork : un point d'entrée `SKILL.md` + un dossier de savoir-faire).
>
> Conventions retenues : **2 fichiers racine** (`persona.md` + `SKILL.md`) + **1 dossier
> `skill/`** · formats **typés par nature** · nommage **kebab-case français** · le dossier de
> l'agent **conserve son nom existant** en Pascal_Snake (ex. `Producer_Orchestrator`).

---

## Arborescence canonique

```
<Agent_X>/                          # ex: Producer_Orchestrator/  (nom Pascal_Snake conservé)
├── persona.md                      # RACINE — persona + domaine  (Markdown)
├── SKILL.md                        # RACINE — point d'entrée, renvoie vers skill/  (Markdown)
└── skill/                          # RACINE — savoir-faire opérationnel
    ├── schema-de-sortie.json       # contrat du livrable              (JSON Schema)
    ├── regles-engagement.md        # règles d'engagement             (Markdown)
    ├── long-term-memory.json       # connaissances persistantes      (JSON)
    ├── exemples/                   # golden examples / few-shot      (JSON)
    │   └── <exemple-parfait>.json
    ├── tool-output/                # sorties d'outils attendues       (Markdown ou JSON)
    │   └── <outil>.md
    └── outils.md                   # [technique] allowlist MCP de l'agent (Markdown)
```

---

## Rôle de chaque élément

### Racine

| Élément | Format | Rôle |
|---|---|---|
| `persona.md` | Markdown | **Qui est l'agent.** Persona + domaine + capacités + contraintes + ton. C'est l'instruction système stable (le « System Instructions » du payload). |
| `SKILL.md` | Markdown | **Point d'entrée.** Frontmatter (`name`, `description`) + corps qui décrit la mission et **renvoie vers les fichiers de `skill/`**. C'est lui qui dit dans quel ordre charger le reste. |

### Dossier `skill/`

| Fichier | Format | Rôle |
|---|---|---|
| `schema-de-sortie.json` | JSON Schema | **Ce que l'agent doit produire.** Contrat du livrable, aligné sur `uefn.handoff.v1` (voir `04-contrat-handoff.md`). Validable automatiquement. |
| `regles-engagement.md` | Markdown | **Comment il travaille.** 1 mission à la fois, `UNKNOWN` plutôt qu'inventer, ne jamais parler à l'utilisateur, périmètre interdit, etc. |
| `long-term-memory.json` | JSON | **Ce qu'il sait déjà.** Connaissances persistantes entre sessions : palette `PID_`, références projet, décisions actées. |
| `exemples/` | JSON | **À quoi ressemble un bon livrable.** Golden examples / few-shot. **1 à 3 fichiers max** (au-delà = context rot). |
| `tool-output/` | Markdown/JSON | **À quoi ressemblent les retours d'outils** qu'il doit savoir lire (ex. sortie de `get_actor_bounds`). Vide/absent pour les agents Design. |
| `outils.md` | Markdown | **[agents techniques seulement]** Allowlist MCP de l'agent + schémas d'entrée/sortie. Absent pour les agents Design (aucun accès MCP). |

---

## Mapping avec le payload d'un agent (WP3 p.8)

Cette structure est l'implémentation physique des composants de contexte listés par le
Whitepaper :

| Composant WP3 p.8 | Fichier correspondant |
|---|---|
| System Instructions | `persona.md` |
| Tool Definitions | `skill/outils.md` |
| Few-Shot Examples | `skill/exemples/*.json` |
| Long-Term Memory | `skill/long-term-memory.json` |
| Tool Outputs | `skill/tool-output/*` |
| *(schéma de sortie — WP3 p.45 structured output)* | `skill/schema-de-sortie.json` |
| *(règles d'engagement — WP1 p.24)* | `skill/regles-engagement.md` |
| Sub-Agent Outputs | **pas dans ce dossier** — arrive via le handoff JSON (voir ci-dessous) |
| External Knowledge (RAG) | **pas dans ce dossier** — optionnel, dossier dédié du projet |

---

## Frontière stable / transitoire (règle importante — WP3 p.61)

Le dossier de l'agent ne contient **que du stable** (sa configuration, son savoir-faire).
Tout ce qui est **mouvant** vit **ailleurs** :

- **Dans le dossier agent (stable)** : persona, règles, schéma, exemples, mémoire longue, outils.
- **Hors du dossier agent (transitoire)** : `project-state.json`, les `handoff/*.json`, les
  livrables `00_vision.json … 07_*.json`, les logs de trajectoire.

Ne jamais écrire d'état de projet dans le dossier d'un agent : ça le rendrait non réutilisable
d'un projet à l'autre et polluerait son contexte stable.

---

## Deux profils de paquets

**Agent Design / Audio (hors UEFN)** — paquet allégé :

```
Creative_Director/
├── persona.md
├── SKILL.md
└── skill/
    ├── schema-de-sortie.json
    ├── regles-engagement.md
    ├── long-term-memory.json
    └── exemples/
```
> Pas de `outils.md` ni de `tool-output/` : aucun accès MCP.

**Agent Technique (UEFN / MCP / Verse)** — paquet complet :

```
Physics_Programmer/
├── persona.md
├── SKILL.md
└── skill/
    ├── schema-de-sortie.json
    ├── regles-engagement.md
    ├── long-term-memory.json
    ├── exemples/
    ├── tool-output/          # ex: get_actor_bounds.md
    └── outils.md             # allowlist MCP + schémas (voir 05-securite-mcp.md)
```

---

## Chargement à l'exécution (rappel)

> **Mis à jour le 2026-10-29.** Injecter tous les fichiers ci-dessous coûtait ≈ 19 000 tokens par
> agent : trop pour un modèle Flash. Ils sont désormais **compilés** en un seul `prompt.flash.md`.

1. **Compilation** (code, déterministe) : `python agent-team/_commun/compiler_prompts.py` produit
   `<Agent>/prompt.flash.md` à partir de `persona.md`, `skill/regles-engagement.md`,
   `skill/outils.md`, `skill/long-term-memory.json`, un **squelette** de `skill/schema-de-sortie.json`,
   **un** bon exemple et les tableaux de pièges de `skill/tool-output/`. Retirés : citations WP,
   méta-commentaires, règles communes recopiées (remplacées par `_commun/regles-communes-flash.md`),
   `decisions_de_pipeline`, `chiffres_de_reference`, descriptions de schéma, exemples REJET.
   Résultat : ≈ 8 500 tokens en moyenne (−54 %). `--check` échoue si un prompt est périmé ou dépasse
   le plafond (11 000).
2. Au DISPATCH, `agent-team/_commun/studio.py dispatch --mission <handoff>` écrit
   `<projet>/dispatch/<id>__<Agent>.md` : `prompt.flash.md` + mission + fichiers d'entrée + consignes
   de rendu (avec auto-contrôle `validate --essai`). Le Producer passe au sous-agent de son harness la
   ligne `prompt_sous_agent` (« lis ce fichier et exécute-le »), jamais un prompt réécrit à la main.
   Marche dans tout harness qui a un shell et un outil de sous-agent. Le Producer n'est pas compilé.
3. Le livrable est jugé par `studio.py validate` contre le `skill/schema-de-sortie.json` **complet**
   (le squelette du prompt n'en est qu'un résumé), plus légalité, émetteur, mission, budget et
   compteur de tentatives ; la sortie donne `decision_conseillee` et le `message_correctif`.
4. On ne modifie **jamais** `prompt.flash.md` à la main : on corrige la source, puis on recompile.

---

## Cohérence avec l'existant

- Cette structure **remplace** le fichier unique `<Nom>/<Nom>.md` actuel : le contenu de ces
  fiches se répartit dans `persona.md` (identité/mission) et `skill/` (contrats, règles,
  exemples).
- Elle **n'entre pas en conflit** avec `templates/TEMPLATE-fiche-agent.md` : ce template
  décrit le *contenu* à mettre dans `persona.md` + `regles-engagement.md` ; le présent doc
  décrit *où* le ranger.
- Le `Producer_Orchestrator.system-prompt-v0.5.md` existant devient le contenu de son
  `persona.md` + `SKILL.md`.
