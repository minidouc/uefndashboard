# Reprise par un autre modele ou un autre outil

> Le cas corpo-plaza : un autre modele a fini le BUILD hors architecture. Il a modifie les
> validateurs, ecrit des preuves en dur, et rien n'a ete valide. Ce protocole rend la reprise
> possible **sans** perdre les garanties.
> Il suffit de donner ce fichier au modele qui reprend.

## Ce que tu dois faire
1. Lancer `python scripts/state.py show`. Lire `docs/lecons.md`, section « Regles actives ».
2. Travailler **uniquement** via les scripts listes dans `CLAUDE.md`. Ils marchent avec n'importe
   quel modele : ce sont des commandes Python.
3. Poser lot par lot : `python scripts/pose_lot.py lot N`, puis `python validators/run_all.py`.
4. Journaliser chaque decision :
   `python scripts/state.py event --source agent_claim --quoi "..."`.

## Ce que tu ne dois jamais faire
- Modifier `validators/`, `tools/lock_validators.py`, `config/studio.json`,
  `config/circuit_breakers.json` ou `.claude/`.
- Ecrire a la main un fichier de `build/studio/` ou `qa/validation/`, ou `state/state.json`.
- Appeler le MCP en direct (curl, script maison). La seule porte est `scripts/uefn/mcp_gateway.py`.
- Remplacer une valeur relue par une valeur calculee « pour que ca passe ».

## Pourquoi ca tient meme si tu n'as pas les hooks
- **Validateurs modifies :** l'empreinte change, `run_all.py` repond « ALTERE » et tout est FAIL.
- **Validateur affaibli puis re-verrouille :** le golden set le detecte.
- **Preuve ecrite a la main :** elle ne correspond pas a la reponse MCP brute horodatee dans
  `build/studio/runs/`.
- **Valeurs en dur :** la provenance (`source`) de chaque evenement dit qui a affirme quoi.
