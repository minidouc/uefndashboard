# Tool output — ping et découverte du pont MCP

> **Tool Outputs** (WP3 p.8). Sorties **réelles** du run UEFN documenté (2026-10-24), plus le
> reflexe d'inventaire. Ce fichier montre ce qui fait foi et ce qui ne fait pas foi.

## 1. Le port 8000 est documentaire, pas un état

```
$ python script/uefn_spatial_cli.py ping --workspace C:/Users/douco/Downloads/uefn-dashboard/ws_corpo_plaza
[OFFLINE] editeur injoignable sur http://127.0.0.1:8000/mcp
return code: 2
```

**Lecture :** code `2` = **OFFLINE**, rien n'a été exécuté. La scène est intacte, aucun acteur
n'a été touché. Ce n'est **pas** un `FAILED` : on ne « corrige » pas un port absent, on le déclare.

## 2. Le pont répond sur 8001

```
$ UEFN_MCP_URL=http://127.0.0.1:8001/mcp python script/uefn_spatial_cli.py ping --workspace ...\ws_corpo_plaza
[PASSED] pont MCP joignable sur http://127.0.0.1:8001/mcp
return code: 0
```

**Lecture :** c'est **8001** qui sert de `mcp_port_active` dans le handoff. Le handoff consigne les
deux tests (`mcp_ports_tested` : 8000 → `OFFLINE` / code 2, 8001 → `ONLINE` / code 0). Écrire 8000
« parce que c'est écrit dans la doc » inverse la charge de la preuve.

## 3. Inventaire des toolsets : sortie trop volumineuse, conservée sur fichier

```
$ python script/uefn_spatial_cli.py list-toolsets --workspace ...\ws_corpo_plaza
Output too large (790.8 KB). Full output saved to:
  C:\Users\douco\.qoder\tmp\...\tasks\bdho4iiik.output
return code: 0
```

**Lecture :**

- `return code: 0` : l'appel a **réussi**. Ce n'est pas une erreur, c'est la règle des 4000 tokens
  (WP2 p.19/p.44) : le contenu reste sur disque, seul le **chemin** entre dans le contexte.
- L'inventaire se fait ensuite par toolsets successifs ou dans le fichier, **jamais** via
  `GetDynamicInputSchema` : cet appel hors session est un crash connu de l'éditeur.
- Valeurs d'inventaire de référence : 388 outils, 30 toolsets, 182 vérifiés, 11 en échec,
  195 inconnus, 138 classés dangereux et jamais appelés.

## 4. Ce que je ne déduis pas d'un ping

| Signal | Ce qu'il prouve | Ce qu'il ne prouve PAS |
|---|---|---|
| ping 8001 code 0 | le pont répond à l'instant T | que la session est connectée, qu'un niveau est chargé |
| ping 8000 code 2 | rien n'écoute sur 8000 | que l'éditeur est cassé |
| `list_toolsets` → fichier | les toolsets sont exposés | que l'outil dont j'ai besoin est fonctionnel (195 inconnus) |

Un ping **seul** ne donne jamais `READY`. Les cases `niveau_actif`, `etat_session`,
`processus_et_ram` et `pagination_cvar` exigent chacune leur propre sortie relue.
