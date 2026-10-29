# Légalité des assets UEFN — règle commune aux 21 agents

> **Source unique** pour toute question « cet asset est-il autorisé ? ». Les agents ne recopient
> pas cette règle de mémoire : ils renvoient à ce fichier et au catalogue
> [`catalogue-verifie.json`](./catalogue-verifie.json).
> Établi le 2026-10-29 sur le projet `MyProjectArtyu` (map 1v1 build fight), preuves en §3.

## 1. La règle

1. **Le préfixe d'un chemin ne prouve rien.** Ni `PPID_`/`PID_` (légal ?), ni `/Game/Athena`
   (illégal ?). Les deux croyances ont été démenties par le validateur (§3).
2. **Seul juge : le validateur UEFN** (`FortValidator_FortExposedActors` /
   `FortValidator_FortExposedAssets`). Il tourne à **chaque sauvegarde** du niveau et au
   lancement de session (`FlowStep_RunLocalValidation`).
3. Un asset est :
   - `VERIFIED_LEGAL` : présent dans `catalogue-verifie.json → acceptes`, avec date et preuve ;
   - `ILLEGAL_ASSET_PATH` : présent dans `catalogue-verifie.json → refuses`, **ou** cité dans une
     ligne `AssetCheck: Error … references disallowed object <chemin>` du journal ;
   - `UNVERIFIED` : tout le reste. Un asset `UNVERIFIED` peut être **essayé**, mais la pose n'est
     `DONE` qu'après une validation propre (§2), et l'asset est alors ajouté au catalogue.
4. Le **design** (Creative_Director, Game_Designer, …) ne juge jamais la légalité : il demande une
   fonction (« un fusil à pompe », « un conteneur ») ; c'est `Lead_Programmer` qui choisit un
   chemin `VERIFIED_LEGAL` ou en fait vérifier un nouveau.

## 2. Procédure de vérification (code, pas jugement de modèle)

**Commande outillée** (tout ce qui suit, en un appel) :

```
python skill/uefn_map_creator/script/uefn_spatial_cli.py check-validator --workspace <ws> [--update-catalogue]
→ 06b_validator_report.json : status PASSED | FAILED | UNKNOWN, refused_paths, error_lines
```

- La commande **sauvegarde** le niveau : c'est une écriture, donc gate HITL (lancée par le
  `Producer_Orchestrator` après accord). `--no-save` relit le journal sans sauvegarder.
- `--update-catalogue` ajoute les chemins refusés à `catalogue-verifie.json → refuses` (sans doublon).
- `UNKNOWN` = aucune trace de validation après la sauvegarde (niveau non modifié ?) : **ce n'est
  pas une preuve de légalité**.
- Côté palette, `validate-scene` / `measure-palette` appliquent le catalogue : `ILLEGAL_ASSET_PATH`
  pour un chemin `refuses`, `UNVERIFIED_ASSET_PATH` pour un `/Game/…` non prouvé (bloqué par défaut ;
  `UEFN_ALLOW_UNVERIFIED=1` permet de l'essayer avant de le faire juger).

Procédure détaillée (ce que fait la commande) :

```
1. poser / référencer l'asset (acteur posé, ou objet dans la liste d'un device)
2. AssetTools.save_assets  {"asset_paths": []}           → déclenche la validation
3. LogsToolset.GetLogEntries {"category": "",
       "pattern": "AssetCheck: Error|disallowed", "maxEntries": 50}
4. ne garder QUE les lignes dont l'horodatage est postérieur à la sauvegarde de l'étape 2
5. aucune ligne  → VERIFIED_LEGAL (ajouter au catalogue avec la date)
   une ligne qui cite le chemin → ILLEGAL_ASSET_PATH (ajouter à refuses, retirer l'asset)
```

Pièges prouvés :
- **Les vieilles erreurs restent dans le journal.** Une ligne `disallowed` antérieure à la dernière
  sauvegarde ne concerne plus forcément la scène. Toujours filtrer par horodatage (étape 4).
- **La sortie peut être énorme** (> 100 Ko) : filtrer par motif, ne passer que le chemin du fichier
  dans un handoff.
- **Une erreur de type n'est pas une erreur de légalité** : `set_properties` peut refuser un objet
  « *is not valid FortWorldItemDefinition (asset is FortGameFeatureData)* ». C'est un mauvais
  asset (un plugin, pas un objet), code `WRONG_ASSET_CLASS`, pas `ILLEGAL_ASSET_PATH`.
- **La preuve finale** est le lancement de session : `FlowStep_RunLocalValidation(): Complete`
  puis `Module upload completed`. Un projet avec un asset refusé n'arrive pas jusque-là.

## 3. Preuves (verbatim du journal, 2026-10-29)

Validation **en échec** (13:42:34) — armes et soins posés dans des devices :

```
AssetCheck: Error: Fournisseur d'objets (...) Package Actor 'Fournisseur d'objets' in World
/2dcda1aa-.../MyProjectArtyu.MyProjectArtyu references disallowed object
/BlastBerryWeapons/Gameplay/PumpShotgun/WID_Shotgun_Pump_Athena_BB_SR.WID_Shotgun_Pump_Athena_BB_SR.
(FortValidator_FortExposedActors)
AssetCheck: Error: Générateur d'objets (...) references disallowed object
/Figment_Athena_Shields/Gameplay/Figment_Athena_Shields.Figment_Athena_Shields. (FortValidator_FortExposedActors)
```

Validation **propre** (13:49:20) après remplacement par `/Game/Athena/Items/...`, alors que la
scène contenait ~460 acteurs posés depuis `/Game/Creative/...`, `/Game/Athena/BuildingActors/...`,
`/Game/Athena/Apollo/...` et `/Game/Building/...` : aucune ligne `AssetCheck: Error`.
Puis lancement de session (13:50) :

```
LogValkyrie: FlowStep_RunLocalValidation(): Complete
LogValkyrie: Module upload completed [MyProjectArtyu](2dcda1aa-...)
```

## 4. Ce qui reste inconnu (ne pas extrapoler)

- Les **maillages bruts** `/Game/Athena/.../SM_*` et `/Game/Environments/...` n'ont **pas** été
  testés : ils restent `UNVERIFIED` (ni autorisés ni interdits par ce document).
- Les objets refusés l'ont été **dans la liste d'un device**. Le verdict pour le même objet posé
  autrement n'a pas été testé.
- Le catalogue vaut pour la version d'UEFN du 2026-10-29 : Epic peut exposer ou retirer des objets.
  Une entrée datée de plus de 30 jours se revérifie avant une publication.
