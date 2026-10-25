# 01 · Architecture du système multi-agents

> **Résumé :** Hub-and-spoke (un seul Supervisor) + assembly line séquentielle +
> filesystem-as-bus. Les 20 agents ne se parlent jamais entre eux, tout passe par le
> Producer, et la mémoire du système vit sur le disque (fichiers JSON), pas dans les
> contextes. C'est la seule topologie qui tient sur 16 Go tout en gardant les Flash fiables.

Les références `WPn p.X` renvoient aux White Papers Google — détail et verbatim dans
[`02-principes-whitepaper.md`](./02-principes-whitepaper.md).

---

## Couche 1 — Topologie d'orchestration : hub-and-spoke, pas un mesh

Le WP1 décrit le niveau le plus avancé comme des agents qui « traitent les autres agents
comme des outils » (p.17) et montre le pattern **Supervisor** de Google Co-Scientist : un
manager délègue à des spécialistes (p.48). Pour nous : **un seul hub** = le Producer, et
**20 spokes**.

Pourquoi un hub et surtout **pas** de communication directe entre agents :

- Le WP1 p.25 dit que la division du travail rend chaque agent « *simpler, more focused,
  easier to build, test, maintain* ». Un Flash qui ne connaît que son rôle et son livrable
  est fiable ; un Flash qui doit négocier avec un voisin ne l'est pas.
- Le WP4 p.20 liste comme échec multi-agent les « *communication loops* » et les agents qui
  « *conflict with others* » sans respecter leur rôle. Un mesh de 20 agents = exactement ce
  piège, démultiplié.
- Un mesh = explosion combinatoire du contexte. Sur 16 Go avec des Flash, c'est la mort
  (WP3 p.9, *context rot*).

**Séquentiel, pas parallèle :** le WP1 p.25 nomme le pattern **Sequential** (« *digital
assembly line where the output from one agent becomes the direct input for the next* »).
C'est littéralement notre chaîne Design → Level → Physics → Verse. Un seul agent actif à la
fois = éditeur UEFN + 1 process Flash en RAM, jamais 20.

---

## Couche 2 — Communication & état : le disque comme bus

C'est **le** choix qui rend le système viable sur cette machine. Le WP3 p.18 : « *an agent
shares its final output, not its process* » (black box). Concrètement :

- Les agents communiquent **uniquement via des fichiers** dans le repo git-friendly
  (`project-state.json` + un `handoff.json` par passage). Zéro transcript partagé, zéro prose
  de raisonnement transmise.
- Séparer **events** (historique append-only) et **state** (mémoire de travail mutable) comme
  le WP3 p.12 le prescrit. `project-state.json` = le state mutable, unique source de vérité ;
  les livrables `00_vision.json … 07_*.json` = les artifacts.
- L'orchestrateur est **quasi stateless entre deux tours** : il relit juste la ligne `phase`
  + le dernier `summary_short` + les compteurs. Il ne recharge jamais l'historique
  (WP3 p.16 : history ≠ context ; WP3 p.22 : réduire la taille transférée). C'est ça qui
  économise la RAM.
- Le **contexte lourd part sur disque, pas dans la fenêtre** : WP3 p.38 recommande d'«
  offloader » vers une mémoire externe ; WP2 p.19 dit la même chose côté outils (« *insert it
  into a temporary table and return the table name* » → passer un **nom de fichier**, pas le
  contenu).
- **Stable vs transitoire** (WP3 p.61) : les règles fixes d'un agent vont dans son prompt
  système ; l'état du projet passe par les fichiers. Ne jamais mettre l'état mouvant dans le
  prompt système.

---

## Couche 3 — Outils / MCP : une gateway unique, task-level, maths externalisées

- **Un seul point d'entrée MCP** vers Unreal, avec **allowlist explicite** et outils
  **épinglés** (WP2 p.41). `mcp-inventory.json` devient la porte : outil absent = bloqué.
- **Publier des tâches, pas des appels d'API** (WP2 p.18) : exposer
  `place_prop_from_grid(cell_id, preset)` plutôt que `place_actor(x,y,z,…)`. Moins de
  paramètres = moins d'hallucination (WP2 p.15).
- **Aucun LLM ne calcule une coordonnée.** WP2 p.9 est formel : le calcul « *is not their
  strong suit… best to call on an external function* ». Toute position/bounds/overlap passe
  par la couche **Python déterministe** (qui lit `03_grid.json` et applique les Z-slices).
  C'est l'arme n°1 anti-map-plate et anti-hallucination.
- **Double schéma** : `inputSchema` + `outputSchema` validé **côté client** avant de
  considérer un call comme réussi (WP2 p.26/p.29).
- **Seul le Producer parle aux humains ; seuls les agents techniques appellent MCP.**
  Least privilege (WP2 p.47) + secrets hors contexte.

---

## Couche 4 — Modèles : routing Frontier/Flash + un juge bon marché

- **Frontier = Producer uniquement** : planification, validation de contrat, arbitrage des
  3 pivots, questions utilisateur (WP1 p.20).
- **Flash = les 20** : génération de payload, rédaction, exécution MCP bornée, extraction
  structurée.
- **Ajouter un étage de tri Flash-Lite / « Gemini as a Judge »** (WP1 p.38) : un passage très
  bon marché qui filtre les sorties Flash **avant** que le Frontier ne dépense son attention
  dessus. Économise du temps-producteur et rattrape les JSON cassés en amont.

---

## Couche 5 — Contrôle, anti-boucle & qualité (le garde-fou est du CODE, pas du prompt)

Point crucial : **le WP ne fournit aucun compteur d'itération** (WP1 p.12 ne donne que « *plan
complete / Mission achieved* »). Donc la protection anti-boucle doit être **déterministe, dans
la couche d'orchestration** (WP1 p.35 : « *hardcoded rules… a security chokepoint outside the
model's reasoning* ») :

- **Cap d'itérations par phase** + **détection de delta** : si deux tours produisent le même
  payload sans changement → STOP (cible : *repetitive output loops*, WP4 p.20). `[adaptation maison]`
- **`before_tool_callback`** (WP1 p.38) : valider les paramètres d'un dispatch **avant** de
  l'exécuter.
- **Validateurs Python, pas auto-check du modèle** : ne jamais demander à un Flash de vérifier
  son propre JSON. Un validateur externe coche le schéma + l'`acceptance` (`0_overlap`,
  `0_floating`, spawn atteignable). Le WP4 p.20 prévient que les modèles « ne reconnaissent pas
  un état d'erreur et continuent comme si le call avait réussi » → seule une vérif déterministe
  protège.
- **Generator-Critic** (WP1 p.25) **uniquement sur les 3 pivots** (`Creative_Director`,
  `Game_Designer`, `Lead_Programmer`), pas sur les 20 — sinon on double le coût pour rien.
- **4 gates HITL** (WP1 p.26 ; WP2 p.36/p.43 ; WP5 p.14/p.18) : validation du brief, du GDD,
  de l'archi technique, et avant toute écriture destructrice dans Unreal.

---

## Couche 6 — Observabilité (version jam, allégée)

Le WP5 p.19-20 décrit la boucle **Observe → Act → Evolve**. Pour une jam, ne garder que
l'essentiel : **logger chaque handoff + chaque appel MCP + son résultat** dans un fichier de
trajectoire. Le WP4 p.21 appelle ça passer du **Black Box** (« la réponse est fausse ») au
**Glass Box** (« elle est fausse *parce que* l'agent X a mal lu le tool result Y »). Sans ce
log, on débogue 20 agents à l'aveugle.

---

## Ce qu'il faut ABSOLUMENT éviter (et pourquoi)

| À éviter | Pourquoi | Source |
|---|---|---|
| Un mesh / agents qui se parlent en direct | communication loops + context rot | WP4 p.20, WP3 p.9 |
| Une hiérarchie profonde (sous-managers) | tours d'inférence + latence sans gain sur 16 Go | WP1 p.48 |
| Passer les transcripts entre agents | black-box output-only imposé | WP3 p.18 |
| LLM qui calcule des coordonnées | le calcul n'est pas son fort | WP2 p.9 |
| LLM qui valide son propre JSON | ne reconnaît pas l'état d'erreur | WP4 p.20 |
| Tree-of-Thoughts / Self-Consistency multiple | jamais nommé dans les docs + multiplicateur d'inférences = hors budget RAM | (absent des WP) |

---

## Mapping concret sur les 21 agents

Chaîne de production recommandée (tout en Sequential piloté par le hub) :

```
Producer
  └─ DESIGN : Creative_Director → Game_Designer
              → (System / Economy / Mission / Narrative / Writer / UX_UI : un par un)
              → Level_Designer
  └─ BUILD  : Engine_Programmer (preflight)
              → Lead_Tech_Director (palette PID)
              → Physics_Programmer (batch géométrie via Python)
              → Gameplay / AI / UI / Graphics_Programmer (Verse)
  └─ POLISH/QA : Audio (Director / Composer / Sound / Voice)
              + validateurs déterministes
              + Producer qui rejoue Generator-Critic sur les pivots
```

Le Producer reste le **seul** à toucher l'utilisateur et le **seul** à lire/écrire
`project-state.json`. Les 20 autres sont des **fonctions pures** :
`handoff_in.json → travail → handoff_out.json`.
