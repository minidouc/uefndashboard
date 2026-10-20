# editor_toolset.toolsets.texture.TextureTools

Famille : `assets-ressources` | Alias CLI : aucun | Outils : 4 (verifie 3, echec 0, inconnu 1, dont 1 classes DANGEREUX)

Description reprise du dump `describe_toolset`, en anglais ou en francais selon le toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, `echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est inconnu).

- **import_file**(folder_path*,asset_name*,source_file*) — Imports an image file from disk as a Texture2D asset. [DANGEREUX | inconnu]
  - motif : Importe un asset dans le Content Browser
- **export_png**(texture*,file_path*) — Exports a Texture to a PNG file on disk. [ecriture | verifie]
- **get_size**(texture*) — Returns the dimensions of a Texture2D in pixels. [lecture | verifie]
- **read_texture**(texture*) — Reads a Texture and returns it as an image. [lecture | verifie]
