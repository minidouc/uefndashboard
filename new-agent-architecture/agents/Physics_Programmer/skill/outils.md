# Physics_Programmer — outils (allowlist)

> **Tool Definitions** (WP3 p.8) + borne de sécurité (WP2 p.47 *least privilege*,
> `util/multi_agent/05-securite-mcp.md`).
> Point d'entrée unique : `python script/uefn_spatial_cli.py <commande> --workspace <absolu>`.
> Le CLI est le gateway : **commande absente de cette page = appel refusé**, pas « à tenter quand même ».
> Codes retour : `0` PASSED · `1` FAILED (**traité** : relire avant de rejouer) · `2` OFFLINE
> (rien d'exécuté) · `3` TIMEOUT (état inconnu : relire, jamais relancer à l'aveugle).

## Autorisé — lecture et validation (aucun effet de bord)

| Commande | Quand / pourquoi | Entrée | Sortie à savoir lire |
|---|---|---|---|
| `validate-grid` | **avant** tout spawn : matrice, bornes, politique de bord | `03_grid.json` | erreurs de matrice, `FLOOR_NOT_TILE_SIZED` |
| `validate-scene` | **avant** tout spawn : cohérence specs ↔ palette, légalité des chemins | `02_palette.json`, `04`, `05` | `ILLEGAL_ASSET_PATH`, labels en double |
| `compile-transforms` | produit les transforms **définitives** (le LLM ne calcule pas de XYZ) | `03`, `04`, `05`, `02` | `_compiled_scene.json`, `_compiled_structure.json` |
| `audit-scene` *(hors ligne)* | contrôle de spécification uniquement — **ne prouve pas** la gravité | specs + `_placed.json` | `06_audit_report.json` avec `source: "spec"` |
| `check-navigation` | couloirs < 100 cm entre acteurs d'une même tuile | scène + grille | `06_navigation_report.json` |
| `list-devices` / `search-playsets` | retrouver un `asset_key` ou une classe de device **déjà dans la palette** | requête | liste d'`asset_path` `PID_`/`PPID_` |
| `visual-snapshot` | preuve visuelle d'une pose (vue de dessus, oblique) | workspace | PNG + caméra relue |

## Autorisé — écriture dans l'éditeur (gate HITL, save préalable)

| Commande | Quand / pourquoi | Paramètres clés | Effet de bord | Relecture obligatoire |
|---|---|---|---|---|
| `build-structure` | sols + murs de périmètre, **lots de 10** | `--workspace`, `--dry-run` d'abord | crée des acteurs | transform relue par lot |
| `place-scene` | props et devices (devices : `PlaceDevice` puis transform forcée) | specs compilées, `_placed.json` persiste les `refPath` | crée/déplace des acteurs | `requested` vs `placed`, `missing`, `fallback_count` |
| `audit-scene --live` | **la seule preuve recevable** d'overlap / gravité | scène ouverte dans l'éditeur | lecture seule live | `source: "live"`, `gravity_scope` |
| `check-symmetry --live` | si `03_grid.json` déclare `symmetric` + `symmetry_axis` | `04` / `05` | lecture seule live | `checked_pairs`, `drift_errors`, pas de `MIRROR_PARTNER_MISSING` |
| `audit-legality` | avant toute demande de session | scène live | lecture seule | `valid_actors`, `illegal_count: 0` |
| `cleanup` | **reconstruction complète seulement**, sur décision Producer | workspace | **destructif** | inventaire des acteurs retirés |

## Interdit pour ce rôle

| Outil / commande | Propriétaire | Pourquoi |
|---|---|---|
| `verse-scan`, `verse-write`, `verse-build`, `list-editables`, `wire-devices` | 12 / 13 / 14 | aucun Verse, aucun câblage |
| `measure-palette` | `Lead_Programmer` | les tailles/pivots ne sont pas ma source |
| `apply-properties` | `Graphics_Programmer` (ambiance) / 12 (gameplay) | je ne règle pas les devices |
| `launch-session`, `Save`/`SaveAll`, `Publish` | Producteur via gate HITL utilisateur | destructeur / publication |
| `GetDynamicInputSchema` hors session | — | crashe l'éditeur (mémoire de projet) |
| `batch.exec`, `editor.undo`, `validate_folder` | — | **n'existent pas** : mentions caduques |
| `Asset.find_assets` dans `/Game/Athena`, `/Game/Environments` | — | assets Epic non exposés → échec de validation d'île |
| Toolsets `effets-ui` (Niagara/UMG/MVVM) | hors périmètre | deux outils sur trois y sont inconnus |

## Toolsets MCP sous le CLI (pour comprendre, pas pour appeler en direct)

- **SceneTools / ActorTools / EntityToolset / PrimitiveTools** — poser, chercher, déplacer, supprimer
  un acteur (`add_to_scene_from_asset`, `get_actor_bounds`, `get_actor_transform`, `set_actor_transform`).
- **DeviceToolset** — cataloguer et poser un device (`ListDeviceAssets`, `PlaceDevice`).
- **ObjectTools / VerseFieldsToolset** — lire/écrire une propriété (`list_properties`,
  `set_properties`, `get_properties`) : je m'en sers **uniquement** pour relire une transform ou un
  label, jamais pour régler un device.
- **EditorAppToolset** — caméra et capture (`SetCameraTransform`, `GetCameraTransform`,
  `CaptureViewport`) pour la preuve visuelle.

**Règle transversale** : `inputSchema` **et** `outputSchema` sont validés côté client avant de
tenir un appel pour réussi (WP2 p.26/p.29). Une sortie > 4000 tokens est redirigée vers un fichier
et je ne transmets que son chemin (WP2 p.19/p.44). `isError`, sortie vide ou incohérente = STOP et
statut `UNKNOWN`, jamais « continuer comme si ça avait marché » (WP4 p.20).
