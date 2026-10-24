# Suivi d'évolution des runs

Une ligne par run. Le but est de voir la courbe, pas de tout documenter.

**Trois règles** :

1. **Même spec gelée** d'un run à l'autre, sinon un écart de temps mesure la taille de la
   carte et pas l'amélioration. Si la spec change, changer `spec` et recommencer la série.
2. **Un seul changement à la fois** entre deux runs, écrit dans la dernière colonne. Sans ça,
   la courbe est illisible : on ne sait pas ce qui a produit l'écart.
3. Toute case vide = **non mesuré**, jamais « zéro » ni « bon ».

---

## Table

| Run | Date | Modèle | Pilote | Spec | Temps (min) | Appels MCP | Mo journal | Posées/dem. | Passes correct. | Illégaux | Erreurs transport | Interv. humaines | Visuel /5 | Verdict | Changement apporté |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R01 | 2026-10-23 | Kimi | mcp388 + sonde | corpo-plaza-v1 | ~240 | 5 376 | 11,27 | 128/128 | 3 | 0 | 1 | — | — | PARTIEL | baseline |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

---

## Comment lire les colonnes

| Colonne | Ce qu'elle révèle quand elle bouge |
| --- | --- |
| Temps | le débit réel du système |
| Appels MCP | le volume de relectures — 92 % chez R01, c'est le poste à attaquer |
| Mo journal | le coût en contexte ; diviser par 4 pour un ordre de grandeur en tokens |
| Posées/dem. | la fiabilité du placement, `fallback` compris |
| Passes correct. | 3 = un défaut de **mesure** (bounds rotatifs), pas de conception |
| Illégaux | la légalité par construction tient-elle |
| Erreurs transport | OFFLINE / TIMEOUT / TOOL_ERROR ; un timeout exige une relecture avant de rejouer |
| Interv. humaines | 0 = autonome, c'est la cible |
| Visuel /5 | la seule note humaine, par le même juge à chaque run |
| Verdict | PASSED / PARTIEL / FAILED |

---

## R01 — baseline du 2026-10-23

Run de référence, non reproductible en l'état car la spec n'était pas encore gelée.

- Construction : 441 sols + 128 entités posées, 0 fallback, 582 acteurs live, **0 illégal**.
- Audits : chevauchements 0 après 3 passes, navigation PASSED, symétrie `axis:null` (ne prouve
  rien), Verse 0 diagnostic, propriétés et câblage PASSED en `allow-empty`.
- Session : `StartSession` timeout 60 s, état relu `UpdatingContent`, validation locale sans
  erreur, session finalement lancée. `12_session_report.json` **perdu** avant écriture.
- Gaspillage mesuré : `list_toolsets` 923 Ko en un seul appel, `get_actor_bounds` 668 o × 4 089,
  `chercher_playsets` 10 494 o × 50.
- Écarts assumés : koïs holographiques → enseignes néon émissives ; plateforme carrée sous une
  composition circulaire ; mannequin d'aperçu du spawner en vue joueur.
- Périmètre tenu : aucune sauvegarde, publication, cleanup, second `StartSession`, ni
  modification du skill.

Critère complet d'audit (si un run mérite d'être disséqué) : voir le journal du run, pas ce
fichier.
