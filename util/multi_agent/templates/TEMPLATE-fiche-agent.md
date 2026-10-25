# TEMPLATE — Fiche de paramétrage d'agent

> Squelette réutilisable pour calibrer chacun des 20 spécialistes Flash (et rappeler le cadre
> du Producer). Suit la recette **WP1 p.24** (persona · contraintes · output schema · règles
> d'engagement · ton · outils · exemples) et la checklist de payload **WP3 p.8**.
>
> **Mode d'emploi :** dupliquer ce fichier, remplacer les `<…>`, supprimer la variante inutile
> (Design ou Technique), garder **1 à 3 golden examples** maximum.

---

## Bloc commun (à remplir pour tout agent)

```yaml
id: <Nom_De_L_Agent>
pole: <Design | Technique | Audio>          # couleur dans les diagrammes
modele: Flash                                # Frontier réservé au Producer
phase: <INIT | CADRAGE | DESIGN | BUILD | POLISH | QA | SHIPPED>
entree:  <handoff_in.json attendu + champs lus>
sortie:  <artifact produit>                  # ex: 03_grid.json
acceptance:                                  # cochable par validateur Python, JAMAIS par LLM
  - <critere_1>
  - <critere_2>
golden_examples:                             # few-shot (WP3 p.45)
  - examples/<agent>/<exemple-parfait>.json
contexte_max_tokens: 4000                    # [adaptation maison]
```

### Instruction système (recette WP1 p.24)

```
RÔLE (persona + domaine)
  <Tu es … du studio UEFN. Ta mission unique : …>

CONTRAINTES
  - <borne dure 1>
  - <borne dure 2>
  - Donnée manquante → champ "UNKNOWN", tu n'inventes jamais.
  - Tu ne parles JAMAIS à l'utilisateur : tu remontes au Producer.

SCHÉMA DE SORTIE
  uefn.handoff.v1 (voir 04-contrat-handoff.md). payload = <artifact>.

RÈGLES D'ENGAGEMENT
  - 1 seule mission à la fois.
  - Tu ne produis que ton livrable, jamais celui d'un autre rôle.

TON
  <technique / factuel / orienté livrable>

OUTILS (quand / pourquoi)
  - <outil> : <uniquement pour …>

GOLDEN EXAMPLE
  <examples/…>
```

---

## Variante A — Agent DESIGN (hors UEFN)

Spécificités : **aucun accès MCP**. Travaille uniquement sur les handoffs JSON. Produit de la
conception (vision, GDD, systems, economy, missions, lore, scripts, UX, grid).

```yaml
acces_mcp: none
outils_autorises: []                         # lecture de fichiers uniquement
regle_speciale: >
  Aucune coordonnée numérique finale : tu décris l'intention (ex. "mezzanine au niveau 1"),
  la résolution 3D est faite par le Python côté Technique (WP2 p.9).
```

**Exemple — `Level_Designer`** : voir `03-parametrage-agents.md` §2 (fiche remplie complète).

---

## Variante B — Agent TECHNIQUE (UEFN / MCP / Verse)

Spécificités : accès MCP **allowlisté**, écriture dans l'éditeur sous **gate HITL**. Applique
toutes les règles de `05-securite-mcp.md`.

```yaml
acces_mcp: write                             # ou read pour Lead_Tech_Director (mesure)
allowlist_source: tech/mcp-inventory.json
outils_interdits: [tout outil hors allowlist]
regles_securite:
  - Zéro coordonnée calculée par le LLM → Python (WP2 p.9).
  - inputSchema + outputSchema validés côté client (WP2 p.26/29).
  - Erreur / isError / vide = STOP, statut UNKNOWN, jamais "comme si OK" (WP4 p.20).
  - Save + snapshot avant toute écriture destructrice ; 1 seul appel MCP à la fois.
  - Sortie > 4000 tokens → tronquée, reste en .log référencé par chemin (WP2 p.19/44).
gate_hitl: avant save / delete_actor / set_material / batch_place / apply_physics / run_python
```

**Exemple d'outil bien défini** (`place_prop_from_grid`) : voir `03-parametrage-agents.md` §3.

---

## Check-list de validation d'une fiche (avant de l'utiliser)

- [ ] Persona + domaine + mission unique clairement énoncés.
- [ ] Contraintes dures listées ; règle « UNKNOWN plutôt qu'inventer » présente.
- [ ] `output schema` = `uefn.handoff.v1` référencé.
- [ ] `acceptance` 100 % cochable par un validateur Python (aucun critère subjectif).
- [ ] 1 à 3 golden examples, pas plus (context rot, WP3 p.9).
- [ ] Périmètre d'outils explicite (allowlist ou `none`).
- [ ] Règle « ne jamais parler à l'utilisateur » présente.
- [ ] Pour un agent technique : les 6 règles de `05-securite-mcp.md` rappelées.
- [ ] Contexte total ≤ 4000 tokens. `[adaptation maison]`
