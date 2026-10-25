# 04 · Contrat de handoff `uefn.handoff.v1`

> Le JSON qui circule sur le bus entre deux agents. **Un fichier par passage**, écrit par
> l'agent sortant, lu par l'agent entrant. C'est l'implémentation concrète du principe
> black-box « *an agent shares its final output, not its process* » (WP3 p.18).
>
> ⚠️ Ce schéma est une **`[adaptation maison]`** — synthèse de WP3 p.18/34/45/46. Google ne
> publie aucun schéma de handoff tout fait.
>
> Schéma machine-readable : [`templates/handoff.schema.json`](./templates/handoff.schema.json).

---

## Le contrat

```jsonc
{
  "$schema": "uefn.handoff.v1",
  "handoff_id": "H-DESIGN-004",           // unique, tracé dans le log de trajectoire
  "from": "Level_Designer",
  "to": ["Physics_Programmer"],           // destinataire(s)
  "artifact": "03_grid.json",             // nom du livrable produit
  "mission_ref": "M-NightCity-DESIGN-04", // rattachement à la mission du Producer
  "summary_short": "Esplanade L0 : 12 plots, 3 rampes N/E/S, 2 piliers P2/P7", // ≤ 200c
  "payload": { /* le livrable brut, atomique — PAS de prose */ },
  "constraints": {
    "z_floor": 0,
    "z_ceiling": 400,
    "must_preserve": ["spawn_A1", "exit_X3"],
    "forbidden": ["aucun prop au-dessus de Z=800"]
  },
  "golden_example_ref": "examples/level/3x3-clean.json", // few-shot (WP3 p.45)
  "acceptance": ["0_overlap", "0_floating", "spawn_reachable", "mcp_ok=true"],
  "next_step_hint": "Physics : batch-check collision avant tout câblage Verse",
  "context_budget_tokens": 4000            // [adaptation maison] plafond du handoff
}
```

---

## Règles impératives

1. **Output-only, black box.** Le `payload` contient le **résultat**, jamais le raisonnement ni
   un extrait de conversation (WP3 p.18). L'agent entrant ne reçoit **pas** le transcript.
2. **Plafond ≤ 4000 tokens.** `[adaptation maison]` calé sur l'exemple de token-truncation du
   WP3 p.24. Si le livrable dépasse → on le **découpe en tranches** ou on écrit un fichier
   séparé et on ne passe que **son nom** dans le handoff (WP2 p.19 : « *return the table name* »).
3. **`summary_short` = seul champ relu mot à mot** par le Producer (≤ 200 caractères). Tout le
   reste est vérifié **par schéma**, pas par lecture — c'est ce qui économise l'attention du
   Frontier et la RAM.
4. **Faits atomiques.** `payload` en JSON structuré, pas de prose (WP3 p.34, p.46 :
   `{"fact": "..."}`).
5. **`golden_example_ref` obligatoire** pour les agents de conception — c'est le few-shot /
   in-context distillation (WP3 p.45).
6. **`acceptance` exécutable.** Chaque critère doit être **cochable par un validateur Python**,
   pas par un jugement de LLM (voir `05-securite-mcp.md`). Ex : `0_overlap`, `0_floating`.
7. **`constraints` = garde-fous transmis.** Bornes Z, éléments à préserver, interdits. Le
   destinataire les applique sans avoir à redemander le contexte amont.

---

## Emplacement & nommage (git-friendly)

```
<projet>/handoff/H-<PHASE>-<seq>__<From>__to__<To>.json
```

- kebab/UPPER cohérents, pas d'espaces.
- Chaque handoff est **commité** → l'historique du projet est rejouable et auditable
  (c'est aussi le **log de trajectoire** de la couche 6, WP4 p.21 Glass Box).

---

## Chaîne typique (Design → Level → Physics → Verse)

| De | Vers | artifact | acceptance clé |
|---|---|---|---|
| `Creative_Director` | `Game_Designer` | `00_vision.json` | brief validé (HITL #1) |
| `Game_Designer` | `Level_Designer` | `01_gdd.json` | boucle de gameplay définie (HITL #2) |
| `Level_Designer` | `Physics_Programmer` | `03_grid.json` | `z_floor/z_ceiling` respectés, ≥3 niveaux |
| `Physics_Programmer` | `Gameplay_Programmer` | `06_audit_report.json` | `0_overlap`, `0_floating` |
| `Lead_Tech_Director` | `Graphics/Gameplay_Programmer` | `02_palette.json` | `PID_`/`PPID_` légaux vérifiés |

Le Producer reste **le seul** à lire/écrire `project-state.json` et à décider de l'enchaînement.
Les handoffs sont les **seuls** canaux entre agents — jamais de dialogue direct (WP4 p.20 :
*communication loops*).
