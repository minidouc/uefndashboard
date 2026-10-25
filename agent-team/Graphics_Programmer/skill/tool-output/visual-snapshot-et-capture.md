# Tool output — `visual-snapshot` et capture caméra relue

> **Tool Outputs** (WP3 p.8). La seule preuve qui me concerne vraiment : **ce que l'éditeur montre**.
> Formes réelles du run UEFN documenté (2026-10-24, CP05 et CP09) et du code
> `script/uefn_spatial_cli.py` (`cmd_visual_snapshot`) + `tools/capture_view.py`.

## 1. `visual-snapshot` — sortie sur le fond, image inutilisable (code `0` quand même)

```json
{
  "status": "PASSED",
  "snapshot_path": "C:\\…\\ws_corpo_plaza\\topdown_structure.png",
  "bytes": 269547,
  "camera_requested": {
    "location": { "x": 6912.0, "y": 6912.0, "z": 14131.2 },
    "rotation": { "pitch": -90.0, "yaw": 0.0, "roll": 0.0 },
    "scale": { "x": 1.0, "y": 1.0, "z": 1.0 }
  },
  "camera_read_back": { "…": "relu par GetCameraTransform" },
  "note": "Pas de grille A1/B2 dessinee : reperer les tuiles via X = ligne*512, Y = colonne*512."
}
```

**Lecture :** la caméra est calculée par le CLI, pas par moi (`03_grid.json` réel : matrice 23×23,
`origin_tile: [2, 2, 0]`, tuiles `512 × 512 × 384`) :

```
X = (origine + lignes/2) × 512,  Y = (origine + colonnes/2) × 512
Z = origine_z × 384 + max(lignes, colonnes) × 512 × 1,2   au-dessus du centre, pitch -90
→ ici (6912, 6912, 14131.2)
```

Sur la scène de référence, ce `Z` était **trop proche** : image **surexposée et coupée** — code CLI
`0`, mais **preuve échouée** (ANNEXE B ligne 4). Un PNG n'existe pas parce que le CLI a rendu
`PASSED` : il existe parce qu'il est **lisible**.

## 2. Capture corrective — la chaîne qui compte

```python
cam = {"location": {"x": 6912.0, "y": 6912.0, "z": 35000.0},
       "rotation": {"pitch": -90.0, "yaw": 0.0, "roll": 0.0},
       "scale": {"x": 1.0, "y": 1.0, "z": 1.0}}
# EditorApp.SetCameraTransform -> EditorApp.GetCameraTransform -> EditorApp.CaptureViewport
```

Résultat : `topdown_structure_wide.png`, **497 635 octets**, caméra relue conforme, carré central
complet et bordure dégagée. Même suite d'appels, **caméra reculée**. Les trois captures CP09 du run
(plateforme 21×21 + couronne de 16 tours + mobilier) :

| Fichier | Caméra demandée | Octets | Ce que la lecture de l'image a donné |
|---|---|---|---|
| `topdown.png` | `6912 6912 35000`, `pitch -90`, `yaw 0` | 908 861 | plateforme complète, couronne de 16 tours, bassin central, **trois anneaux** lisibles, deux poissons opposés, 4 enseignes |
| `oblique.png` | `-2000 14000 8000`, `pitch -30`, `yaw -35` | 1 298 074 | couronne vue de l'extérieur, place centrale avec émetteur holo et poisson émissif vert/cyan |
| `player.png` | `3328 6912 260`, `pitch 12`, `yaw 0` | 1 357 369 | vue depuis le spawner sud : les deux enseignes néon encadrent le champ ; le grand mannequin translucide central est **l'aperçu éditeur du Player Spawner**, pas un décor |

## 3. `<nom>_camera.json` — la trace relue (forme réelle, `oblique_camera.json`)

```json
{
  "requested": {
    "location": { "x": -2000.0, "y": 14000.0, "z": 8000.0 },
    "rotation": { "pitch": -30.0, "yaw": -35.0, "roll": 0.0 },
    "scale": { "x": 1.0, "y": 1.0, "z": 1.0 }
  },
  "read_back": {
    "location": { "x": -2000, "y": 14000, "z": 8000 },
    "rotation": { "pitch": -30.000000000000025, "yaw": -35.00000000000003, "roll": 0 },
    "scale": { "x": 1, "y": 1, "z": 1 }
  }
}
```

**Lecture :** le bruit flottant de l'éditeur (`-30.000000000000025`) est **normal** ; `read_back`
absent ou franchement différent = la caméra n'a pas bougé, et l'image ne prouve rien. C'est pour ça
que `capture_view.py` écrit systématiquement ce fichier à côté du PNG.

## 4. La chaîne `tools/capture_view.py` (fourni, hors CLI)

```bash
export UEFN_MCP_URL="http://127.0.0.1:8001/mcp"
python "$WS/tools/capture_view.py" --skill "$SKILL" --workspace "$WS" \
  --output "$WS/oblique.png" --location -2000 14000 8000 --pitch -30 --yaw -35
```

Sortie : `{"status": "PASSED", "output": "…\\oblique.png", "read_back": {…}}`, journalisation dans
`_mcp_calls.jsonl`, PNG écrit **seulement** si `CaptureViewport` rend un `data` base64 non vide.

## 5. Échecs que je sais reconnaître

| Sortie | Code | Signification | Conduite |
|---|---|---|---|
| `{"status": "FAILED", "error": "CaptureViewport sans image en ligne"}` | **1** | l'éditeur n'a rendu **aucune** image | aucune preuve : rien n'est annoncé, on re-examine l'état de la vue |
| `error_kind: "OFFLINE"` / `editeur injoignable sur http://127.0.0.1:8000/mcp` | **2** | rien d'exécuté ; le pont du run documenté était sur **8001** | vérifier `UEFN_MCP_URL` (règle appliquée à **chaque** shell) |
| `McpTimeout` / `WinError 10054` (`TIMEOUT_OUTCOME_UNKNOWN`) | **3** | état inconnu | relire avant de relancer ; chercher un acteur **sans label** si l'appel suivait une pose |
| `RuntimeError: CaptureViewport sans image` (script) | — | PNG non écrit | la capture n'existe pas |
| image surexposée / coupée avec `status: "PASSED"` | **0** | **fausse réussite** : caméra par défaut trop proche | reculer la caméra, relire, re-contrôler les octets, relire l'image |
| dérivé de contraste (ex. `topdown_structure_contrast.png`, 47 975 o) insuffisant | **0** | retoucher l'image ne remplace pas une bonne prise de vue | recapturer, pas filtrer |

## 6. Le verdict se lit dans l'image, pas dans le rapport

Le run de référence compare ses captures aux références du brief (`mp01.png`, `mp02.png`) et rend :

- **critère émissif satisfait** : les deux poissons sont des enseignes néon **visiblement lumineuses**
  (matériaux émissifs, pas des meshes opaques) ;
- **critère holographique non satisfait** : ce ne sont **pas** des poissons holographiques
  translucides ; les requêtes catalogue (« koi », « cyan fish », « orange fish », « hologram fish »)
  n'ont rien donné de mieux → verdict **`approxime`**, écrit comme tel, **jamais** `proven`.

Un verdict `conforme` exige donc : le fichier, sa taille, la caméra relue, et la **description de ce
que l'image montre** (jour/nuit, ambiance, couleurs dominantes) confrontée à `00_vision.json`.
