# Tool output — `search-playsets` & `audit-legality` (la chasse, puis le verdict)

> **Tool Outputs** (WP3 p.8). Sorties **brutes réelles** du run UEFN documenté (Corpo Plaza,
> 2026-10-23/24, niveau `claudtest`), archivées dans `ws_corpo_plaza\search_*.json` et
> `ws_corpo_plaza\06_legality_report.json`, puis la lecture que j'en fais.

## 1. Une recherche qui marche : le verbatim à connaître

```json
// python script/uefn_spatial_cli.py search-playsets --workspace <ws> --query "bench"
// fichier archive : search_bench.json — count: 80, results: 80 entrees ; ci-dessous 2 sur 80
{"status": "PASSED",
 "command": "search-playsets",
 "query": "bench",
 "count": 80,
 "results": [
   {"name": "PPID_AlleyT_Comp_Asteria_NeonCity_Bench_A_a0afeeec",
    "asset_path": "/AlleyT_Comp/SetupAssets/Maps/PPIDs/PPID_AlleyT_Comp_Asteria_NeonCity_Bench_A_a0afeeec.PPID_AlleyT_Comp_Asteria_NeonCity_Bench_A_a0afeeec",
    "class": "FortPlaysetPropItemDefinition"},
   {"name": "PPID_CRP_Chonkers_HotelBench_02",
    "asset_path": "/CRP_Chonkers/SetupAssets/Maps/PPIDs/PPID_CRP_Chonkers_HotelBench_02.PPID_CRP_Chonkers_HotelBench_02",
    "class": "FortPlaysetPropItemDefinition"}
 ],
 "note": "Tous ces chemins sont des PPID_ / PID_ legaux exposes aux createurs UEFN."}
```

**Lecture :** trois choses sont exploitables et rien ne doit être déduit du reste.
(1) `count` et le nombre d'entrées revenues coïncident ici (80 = 80) : la liste est exhaustive.
Quand ils divergent, c'est un plafond — voir §3. (2) `class` est la preuve de légalité :
`FortPlaysetPropItemDefinition` ⇒ `PPID_`, `FortPlaysetItemDefinition` ⇒ `PID_`. Une classe
différente n'est pas un asset Créatif, elle sort de la palette. (3) le `asset_path` complet,
avec son suffixe `…_<hash>`, est **recopié caractère par caractère** dans `02_palette.json` ;
je ne le reconstruis jamais et je ne le raccourcis pas.

## 2. Les playsets éditeur `/CRP_*` font partie de la chasse

Deux familles coexistent dans les résultats ci-dessus : `/AlleyT_Comp/…` (thème commercial) et
`/CRP_Chonkers/…` (playset d'éditeur). Les `/CRP_*` sont **légaux et exposés** — les ignorer
revient à se priver d'un tiers du catalogue. Preuve réelle : `--query "CRP tree"` ⇒ `count: 100`,
`--query "CRP planter"` ⇒ `count: 86`, là où la même recherche sans le préfixe thematic
s'est arrêtée beaucoup plus bas.

## 3. Le vrai piège : la requête multi-mots est un ET, pas un OU

Verbatims du run, tous avec `status: "PASSED"` :

```json
{"command":"search-playsets","query":"fountain basin","count":0,"results":[]}
{"query":"bench planter tree lamp bollard","count":0,"results":[]}
{"query":"hologram projector","count":0,"results":[]}
{"query":"cyan fish","count":0,"results":[]}
{"query":"CRP Katsura","count":0,"results":[]}
// la meme idee, en un seul mot :
{"query":"basin","count":6,"results":[{"name":"PPID_CR_Legacy_Athena_Prop_WildWest_WashBasin_630fe9dc", …}]}
{"query":"fish","count":100,"results":[… 100 entrees …]}
```

**Lecture :** la sémantique est un **ET**, pas un OU. `Probe.chercher_playsets` exige que **tous**
les mots soient présents dans le nom. `fountain basin` échoue alors que `fountain` et `basin`
réussissent séparément, parce qu'aucun nom ne porte les deux.

**Deuxième lecture, autant de piège : `count: 100` est un plafond, pas un total.** Cinq requêtes
du run reviennent à exactement 100 (`fish`, `holo`, `neon`, `lamp`, `CRP tree`) ; aucune ne
remonte à 101. Un `count` strictement inférieur à 100 (`bench` = 80, `CRP planter` = 86,
`basin` = 6) est en revanche exhaustif. Conduite : sur un plateau à 100, je resserre le motif
avant de conclure que j'ai vu tout le catalogue.

**Comptage réel du run :** 50 fichiers `search_*.json` archivés, **20 revenues à `count: 0`** ;
sur les 30 requêtes multi-mots, **18 sont revenues à 0**. Conséquence méthodologique, non
négociable : **`count: 0` sur une requête multi-mots ne prouve pas l'inexistence d'un asset.**
Conduite imposée — redécouper en un seul mot, relancer, et consulter les variantes de thème
(`CRP_`, `AlleyT_`, `Sunburst_`, …) avant d'écrire une absence dans la palette. Je ne déclare un
asset introuvable qu'après avoir montré les requêtes tentées.

## 4. `PID` vs `PPID` : `--type`, et pourquoi le choix n'est pas neutre

```json
// search_building_pid.json --type PID
{"query":"Building","count":56,
 "results":[{"name":"PID_CP_Sunburst_Building_a",
             "asset_path":"/CRP_Sunburst/SetupAssets/Maps/PID_CP_Sunburst_Building_a.PID_CP_Sunburst_Building_a",
             "class":"FortPlaysetItemDefinition"}]}
```

Un `PID_` de bâtiment est un **conteneur de playset** : son `FortPlaysetRoot` rend des bornes
nulles à la mesure (`{0,0,0}` avec `isValid: true`, voir `measure-palette.md` §3) et son contenu
réel n'est pas addressable prop par prop. `--type PID` sert pour les **devices** (spawner,
granter, zone, tracker, audio, skydome), pas pour la géométrie mesurable. Sur ce run, **quatre
`PID` consécutifs** ont produit des bornes nulles (23:54:24 → 23:58:04) : remplacement par le
`PPID` de la même famille (`PPID_CRP_Sunburst_CP_Building_Scifi_01`, mesuré 9561.23 × 3141.13 ×
24484.3) et trace dans la palette avec `NULL_BOUNDS`.

## 5. `audit-legality` : le verdict qui autorise la pose

```json
// python script/uefn_spatial_cli.py audit-legality --workspace <ws>
// 06_legality_report.json
{"timestamp": "2026-10-23T22:52:12.244645+00:00",
 "command": "audit-legality",
 "fix_applied": false,
 "status": "PASSED",
 "valid_actors": 582,
 "illegal_count": 0,
 "illegal_actors": []}
```

**Lecture :** ce que j'expose en aval, c'est `status`, `valid_actors`, `illegal_count` — pas mon
impression sur la scène. Deux subtilités :
- `fix_applied: false` **accompagné de** `illegal_count: 0` est le bon état : rien à corriger.
  Un `fix_applied: true` avec `illegal_count: 0` signifierait que l'audit a **touché** la scène
  pour rien — à signaler au Producteur, pas à célébrer.
- `valid_actors: 582` est un comptage **d'acteurs posés**, pas d'entrées de palette. Les deux
  nombres ne coïncident pas et ne doivent jamais être confondus dans un handoff.
- Le seul message d'échec qui m'arrête est `ILLEGAL_ASSET_PATH` sur `/Game/Athena/...` ou
  `/Game/Environments/...`. Un acteur dont le `nativeClass` interne est un `/Game/...` **n'est
  pas** une illégalité : ce qui compte est le `asset_path` que **j'ai** demandé.

## 6. Échecs reconnus, codes retour et conduites

| Sortie / message brut | Code | Conduite |
|---|---|---|
| `{"status":"PASSED","count":0,"results":[]}` sur multi-mots | 0 | **faux négatif** : redécouper en un mot avant toute conclusion |
| `OFFLINE` · pont injoignable (le MCP écoute sur `8001`, pas `8000`) | 2 | aucune chasse lancée, renvoi à `Engine_Programmer` |
| `WinError 10054` en pleine série de recherches | 3 | état inconnu : je relis les `search_*.json` écrits, je ne rejoue pas à l'aveugle |
| « Output too large » (ex. `list_toolsets` = 790,8 Ko) | 0 | sortie gardée sur fichier, seul le **chemin** va dans le handoff |
| `ILLEGAL_ASSET_PATH` | 1 | bloqué dans la palette, alternative légale proposée, jamais posé |
| pagination laissée à 0 (CVar) | 1 | résultat tronqué lu comme un résultat complet : la CVar est forcée à 200 avant de conclure |

**Transversal :** un seul appel MCP à la fois ; `isError` ou sortie vide = STOP et `UNKNOWN` ;
et une palette n'est rendue **que** si chaque entrée porte un `asset_path` recopié d'une sortie
archivée, jamais reformulé de mémoire.
