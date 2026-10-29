# Tool output — `audit-scene --live`

> **Tool Outputs** (WP3 p.8). Le rapport qui fait foi. Exemples **réels** du run UEFN documenté
> (2026-10-24) : d'abord le PASSED à rendre, puis le FAILED à corriger.

## 1. `06_audit_report.json` — PASSED (ce que je rends)

```json
{
  "timestamp": "2026-10-23T22:52:11.163775+00:00",
  "source": "live",
  "status": "PASSED",
  "error_count": 0,
  "overlap_errors": [],
  "gravity_errors": [],
  "scene_errors": [],
  "other_report": "passages etroits : 06_navigation_report.json (check-navigation)",
  "gravity_scope": "bounds relus dans l'editeur"
}
```

**Points de contrôle, dans cet ordre :**

1. `source` vaut **`"live"`**. Un `"spec"` ne prouve ni la gravité ni la position réelle.
2. `error_count` = 0 **et** les trois listes vides (le compteur seul ne suffit pas).
3. `gravity_scope` mentionne bien les **bounds relus**.
4. `other_report` : je cite le rapport complémentaire, je ne le recalcule pas ici.

## 2. Échec typique après un premier batch — 91 chevauchements

```json
{
  "status": "FAILED",
  "error_count": 91,
  "overlap_errors": [
    {
      "type": "OVERLAP_ERROR",
      "actor_a": "Cover_Crate_Main",
      "actor_b": "Pillar_Decor_01",
      "penetration_cm": 28.4,
      "tile": [2, 2, 0],
      "suggestion": "Placer Cover_Crate_Main en RELATIVE_TO_ACTOR avec gap_cm >= 15."
    }
  ],
  "gravity_errors": [
    {
      "type": "GRAVITY_ERROR",
      "actor": "Cover_Crate_Main",
      "distance_to_floor_cm": -12.0,
      "state": "BURIED",
      "tile": [2, 2, 0],
      "floor_reference": "bounds du sol",
      "suggestion": "Remesurer pivot_offset_cm (measure-palette --force) ou corriger snap_to_floor."
    }
  ],
  "scene_errors": [{ "type": "ACTOR_NOT_FOUND", "actor": "Pillar_Decor_01" }]
}
```

**Lecture :**

- `OVERLAP_ERROR` → `penetration_cm` décide de l'urgence ; la cause racine n°1 est le **bound
  rotatif** (une AABB tournée est plus grande que la taille théorique), pas un « petit décalage ».
- `GRAVITY_ERROR` → `state: "BURIED"` (enfoncé) ou `"FLOATING"` (flottant) ; `distance_to_floor_cm`
  négatif = enfoncé. Correction par le **pivot/le scale dans la spec**, jamais en survolant l'objet.
- `ACTOR_NOT_FOUND` → l'acteur attendu n'existe pas : soit la pose a timeouté, soit le label a été
  perdu. On relit l'Outliner avant de reposer.

## 3. Boucle réelle observée (3 passes)

| Passe | Signe | Correction dans la spec | Résultat |
|---|---|---|---|
| 1 | 91 `OVERLAP_ERROR` | tuiles du mobilier déplacées, anneaux × 0,75 | 10 erreurs restantes |
| 2 | 10 chevauchements (tours / enseignes) | `tower_c` XY × 0,55, enseignes à 0,62 | 0 chevauchement, 4 gravités |
| 3 | 4 `GRAVITY_ERROR`, enseignes enfoncées (`-3,2` → `-5,86` → `-3,07` → `+3,44` cm) | `sign_vertical.pivot_offset_cm[2] = 485.0` | `PASSED`, 0 erreur |

Chaque passe = **spéc → `compile-transforms` → `place-scene` → `audit-scene --live`**. Aucun
déplacement à la main dans l'éditeur.

## 4. Rapports voisins que je sais lire

- `06_navigation_report.json` → `navigation_errors: []` et un `navigation_scope` qui dit que seules
  les **paires d'acteurs d'une même tuile** sont contrôlées (pas de capsule, pas de murs, pas de
  passages entre tuiles). Ce scope doit être cité tel quel, pas sur-vendu.
- `11_symmetry_report.json` → `axis: null`, `checked_pairs: 0`, `status: "PASSED"` = **aucun contrôle
  de symétrie effectué** (symétrie non déclarée). Jamais présenter ce PASSED comme une preuve.
- `06_legality_report.json` → `valid_actors: 582`, `illegal_count: 0` : le nombre d'acteurs **dans la
  scène live**, pas le nombre d'entrées de mes specs.
