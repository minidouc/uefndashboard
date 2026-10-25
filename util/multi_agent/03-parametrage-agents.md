# 03 · Paramétrage des agents — quoi donner, comment, avec exemples

> Les White Papers ne fournissent **aucun template de fiche agent prêt à l'emploi**, mais ils
> donnent trois choses exploitables : la **liste des composants** à mettre dans un agent
> (WP3 p.8), la **recette de l'instruction système** (WP1 p.24), et les **règles de définition
> d'outils avec exemples bon/mauvais** (WP2 p.15-18). Ce fichier les traduit pour le studio.
>
> Le squelette réutilisable est dans [`templates/TEMPLATE-fiche-agent.md`](./templates/TEMPLATE-fiche-agent.md).

---

## 1. La liste canonique : que donner à chaque agent (WP3 p.8)

Le « payload » de contexte d'un agent se décompose en composants nommés. C'est la checklist
de paramétrage :

| Composant | Rôle | Dans le studio |
|---|---|---|
| **System Instructions** | persona, capacités, contraintes | le prompt système de la fiche |
| **Tool Definitions** | schémas des outils appelables | allowlist MCP (`mcp-inventory.json`) |
| **Few-Shot Examples** | exemples qui guident par in-context learning | **golden examples** (niveau 3×3 vierge) |
| **Long-Term Memory** | connaissances persistantes entre sessions | références projet, palette `PID_` |
| **External Knowledge** | données récupérées (RAG) | docs Verse, inventaire Playsets |
| **Tool Outputs** | résultats d'outils | retours MCP (sanitisés, tronqués) |
| **Sub-Agent Outputs** | résultats des agents délégués | **handoff JSON** entrant |

**Règle d'or** (WP3 p.8) : « *the model has no more and no less than the most relevant
information* ». Chaque fiche doit contenir ces composants **et rien d'autre** — tout ce qui
n'est pas utile au rôle sort du contexte (et va sur le disque, voir `01` couche 2).

---

## 2. La recette de l'instruction système (WP1 p.23-24)

Le doc appelle ça **« Instruct with Domain Knowledge and Persona »** et liste exactement quoi
fournir :

1. **Persona + domaine** — « *You are a helpful customer support agent for Acme Corp…* »
2. **Contraintes**
3. **Schéma de sortie désiré** — « *desired output schema* »
4. **Règles d'engagement** — « *rules of engagement* »
5. **Ton de voix précis**
6. **Guide explicite de QUAND et POURQUOI utiliser ses outils**
7. **Exemples de scénarios** — « *A few example scenarios in the instructions are usually very
   effective* »

### Exemple rempli — `Level_Designer`

```
RÔLE (persona + domaine)
  Tu es Level_Designer du studio UEFN. Tu conçois l'architecture 3D en Z-Slices
  (level -1 creux/bassin, 0 esplanade, 1 mezzanine, 2 objets aériens), avec vides (V),
  rampes (R_N/S/E/W), piliers (P) et 3 plans de profondeur (jouable / bordure / horizon).

CONTRAINTES
  - Z ∈ [z_floor, z_ceiling] fournis dans le handoff entrant.
  - Jamais de map plate : au moins 3 niveaux de hauteur exploitables.
  - Jamais de coordonnée calculée de tête : tu lis get_actor_bounds ou tu délègues au Python.

SCHÉMA DE SORTIE
  uefn.handoff.v1 (voir 04-contrat-handoff.md). payload = 03_grid.json (+ 04_devices, 05_props).

RÈGLES D'ENGAGEMENT
  - 1 seule mission à la fois.
  - Donnée manquante → champ "UNKNOWN", tu n'inventes jamais.
  - Tu ne parles JAMAIS à l'utilisateur : tu remontes au Producer.

TON
  Technique, factuel, orienté livrable.

OUTILS (quand / pourquoi)
  - get_actor_bounds : UNIQUEMENT pour lire des bornes existantes.
  - Aucun tool d'écriture (réservé aux Programmeurs).

GOLDEN EXAMPLE (few-shot)
  examples/level/3x3-clean.json
```

---

## 3. Définir les outils MCP — l'exemple bon/mauvais du doc (WP2 p.15-18)

Règles (WP2 p.15-18) :

- **Nom clair et spécifique** — `create_critical_bug_in_jira_with_priority` > `update_jira`.
- **Décrire TOUS les params** (entrée **et** sortie), avec type + usage.
- **Listes de paramètres courtes** — « *Long parameter lists can confuse the model* ».
- **Exemples ciblés** + **valeurs par défaut documentées** — « *LLMs can often use default
  values correctly, if they are well-documented* ».
- **Décrire des actions, pas des implémentations** — « *create a bug to describe the issue* »,
  pas « *use the create_bug tool* ».
- **Ne pas dupliquer** la doc de l'outil dans l'instruction système ; **ne pas dicter le
  workflow** ; **documenter les effets de bord** (« *DO explain tool interactions* »).
- **Publier des tâches, pas des API** ; outils **granulaires** ; **pas de multi-tools**.

### Bon vs mauvais (style WP2 p.16-17, traduit en UEFN)

```python
# ❌ MAUVAIS — style "fetchpd(pid)" du WP2 p.17
def place(x, y, z):
    """place un truc"""
    # nom vague, params sans type, aucun retour décrit, coordonnées portées par le LLM

# ✅ BON — style "get_product_information" du WP2 p.16
def place_prop_from_grid(cell_id: str, prop_preset: str = "crate_small") -> dict:
    """
    Place un prop dans le niveau à partir d'une case du 03_grid.json.
    Les coordonnées X/Y/Z sont résolues par le moteur (jamais passées par le modèle).

    Args:
      cell_id: identifiant de la case dans la grille (ex "L0-C12").
      prop_preset: nom du preset Playset légal (défaut: "crate_small").

    Returns:
      dict avec clés 'actor_id', 'world_pos' {x,y,z}, 'bounds', 'status'.
      Exemple:
        {'actor_id': 'A_1043',
         'world_pos': {'x': 1200, 'y': 0, 'z': 0},
         'bounds': {...},
         'status': 'placed'}

    Effet de bord: ÉCRIT dans le niveau → nécessite save + snapshot (gate HITL).
    """
```

**Le détail qui compte :** le modèle ne passe **jamais** `x/y/z` — il passe un `cell_id`, et
c'est le Python/MCP qui résout les coordonnées. On applique d'un coup WP2 p.9 (*maths
externalisées*) et WP2 p.18 (*tasks, not API calls*). C'est le meilleur rempart
anti-hallucination de coordonnées.

---

## 4. Les exemples / few-shot (WP3 p.45 + WP2 p.16)

Deux façons de calibrer un agent par l'exemple, toutes deux utiles pour les Flash :

- **Schema / template-based extraction** — on donne un schéma JSON, le modèle le remplit via
  *structured output*. Bien pour les livrables très structurés (grid, devices, economy).
- **Few-shot prompting** — « *the LLM is shown what to extract using examples … several examples
  of input text and the ideal, high-fidelity output* ». Idéal pour les sujets « difficiles à
  décrire avec un schéma » : style artistique, ton d'un lore, structure d'un GDD.

**Application studio :** le « golden example » sur un niveau vierge 3×3 = un **few-shot example**
au sens du doc. Garder **1 à 3 exemples parfaits par agent**, pas plus (pour ne pas gonfler le
contexte) ; le WP2 p.16 suggère même de les **récupérer dynamiquement** selon la tâche.

---

## 5. Anti-patterns de paramétrage (à ne jamais faire)

- Mettre l'état mouvant du projet dans le prompt système (WP3 p.61 : stable → prompt,
  transitoire → fichier).
- Redonner toute la spec du studio à chaque Flash (context rot, WP3 p.9).
- Demander à un Flash de produire des coordonnées numériques brutes (WP2 p.9).
- Écrire des instructions qui dictent une séquence rigide d'appels d'outils (WP2 p.17 :
  « *Don't dictate workflows* »).
- Dupliquer la doc de l'outil dans le prompt (WP2 p.17 : « *Don't duplicate instructions* »).
- Laisser un agent sans `output schema` explicite → JSON libre = invalide (WP3 p.45, WP4 p.20).
