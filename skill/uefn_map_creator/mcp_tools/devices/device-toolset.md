# ValkyrieToolset.DeviceToolset

Famille : `devices` | Alias CLI : `Device` | Outils : 9 (verifie 6, echec 0, inconnu 3, dont 0 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **AddEventBinding**(sourceDevicePath*,sourceEvent*,targetDevicePath*,targetFunction*) — Bind a source device's event to a target device's function so the event triggers it (idempotent - re-binding the same pair is a no-op). [ecriture | verifie]
- **RemoveEventBinding**(sourceDevicePath*,sourceEvent*,targetDevicePath*,targetFunction*) — Remove an event binding from a source device's event to a target device's function. [ecriture | verifie]
- **SetDeviceProperty**(device*,propertyName*,value*) — Set one editable setting on a Verse creative_device. [ecriture | inconnu]
  - motif : Exige un creative_device Verse.
- **GetDeviceProperties**(device*,propertyNames*) — Read named settings from a Verse creative_device. [lecture | inconnu]
  - motif : Exige un creative_device Verse.
- **PlaceDevice**(assetPath*,transform*) — Place a catalog device (classic or Verse) into the level. [ecriture | verifie]
- **GetBindingOptions**(devicePath*) — Get the source events and target functions a device exposes for binding. [lecture | verifie]
- **ListDeviceProperties**(device*) — List a Verse creative_device's editable settings as a JSON property schema, with friendly names. [lecture | inconnu]
  - motif : Exige un creative_device Verse.
- **ListEventBindings**(devicePath*) — List the event bindings currently wired into a device's target functions. [lecture | verifie]
- **ListDeviceAssets**(nameFilter) — List the project's placeable Creative devices - classic (Blueprint) and Verse (creative_device). [lecture | verifie]
