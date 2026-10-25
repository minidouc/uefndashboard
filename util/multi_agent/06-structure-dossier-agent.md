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

1. Le Producer ouvre le dossier de l'agent ciblé.
2. `persona.md` + `SKILL.md` → chargés comme **instruction système**.
3. `skill/schema-de-sortie.json` → le contrat à respecter.
4. `skill/regles-engagement.md` + `skill/long-term-memory.json` → injectés.
5. `skill/exemples/*.json` → injectés en **few-shot** (1 à 3 seulement).
6. Pour un agent technique : `skill/outils.md` borne les appels MCP autorisés.
7. L'agent produit son livrable → validé contre `schema-de-sortie.json` → écrit en
   `handoff/*.json` **hors du dossier agent**.

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
