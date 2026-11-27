"""Mesures d'image deterministes (Pillow seul) : une capture ne vaut que par ce qu'elle montre.

Deux usages :
  - `analyser(png)` : refuse une capture inexploitable (uniforme = mur en gros plan ou viewport
    vide, noire, surexposee). Le poids du fichier ne prouve rien : un PNG uni pese des Ko.
  - `controle_lecture(png)` : les reponses attendues aux questions de lecture (quadrant le plus
    clair / le plus sombre). Elles ne sont JAMAIS affichees a l'agent : seul le validateur les
    recalcule, pour prouver que l'agent a regarde l'image au lieu de la declarer lue.

Seuils repris de la v2 (contraste 12, bords 4), calibres sur des captures de test et non encore
sur des captures UEFN reelles : a recaler au premier essai en direct.
"""
import hashlib

try:
  from PIL import Image, ImageFilter, ImageStat
except ImportError:  # pragma: no cover - signale par analyser()
  Image = None

TAILLE = (320, 180)
CONTRASTE_MIN = 12.0
BORDS_MIN = 4.0
NOIR_MAX_FRAC = 0.90
BLANC_MAX_FRAC = 0.60
ECART_QUADRANT_MIN = 10.0     # en dessous, la question est ambigue : elle n'est pas posee
QUADRANTS = ("haut_gauche", "haut_droite", "bas_gauche", "bas_droite")


def _gris(png: str):
  im = Image.open(png).convert("RGB")
  im.thumbnail(TAILLE)
  return im.convert("L")


def analyser(png: str) -> dict:
  """{"mesures": {...}, "erreurs": [{"type", "detail"}]} ; erreurs vides = image exploitable."""
  if Image is None:
    return {"mesures": None, "erreurs": [{"type": "PILLOW_ABSENT", "detail":
            "pip install pillow : sans lui, l'image ne peut pas etre jugee (UNKNOWN, pas PASSED)."}]}
  g = _gris(png)
  st = ImageStat.Stat(g)
  bords = ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).mean[0]
  hist = g.histogram()
  n = sum(hist) or 1
  m = {"luminance_moy": round(st.mean[0], 1), "contraste_std": round(st.stddev[0], 1),
       "densite_bords": round(bords, 1), "frac_noire": round(sum(hist[:16]) / n, 3),
       "frac_blanche": round(sum(hist[241:]) / n, 3),
       "empreinte": hashlib.sha256(g.resize((16, 16)).tobytes()).hexdigest()[:16]}
  err = []
  if m["contraste_std"] < CONTRASTE_MIN or m["densite_bords"] < BORDS_MIN:
    err.append({"type": "IMAGE_UNIFORME", "detail":
                f"contraste {m['contraste_std']} / bords {m['densite_bords']} : mur en gros plan, "
                "viewport vide ou capture ratee. Recadrer (camera plus haute ou reculee)."})
  if m["frac_noire"] > NOIR_MAX_FRAC:
    err.append({"type": "IMAGE_NOIRE", "detail": f"{m['frac_noire']:.0%} de pixels noirs."})
  if m["frac_blanche"] > BLANC_MAX_FRAC:
    err.append({"type": "IMAGE_SUREXPOSEE", "detail": f"{m['frac_blanche']:.0%} de pixels blancs."})
  return {"mesures": m, "erreurs": err}


def controle_lecture(png: str) -> dict:
  """Reponses attendues, seulement pour les questions non ambigues : {question: quadrant}."""
  g = _gris(png)
  w, h = g.size
  boites = {"haut_gauche": (0, 0, w // 2, h // 2), "haut_droite": (w // 2, 0, w, h // 2),
            "bas_gauche": (0, h // 2, w // 2, h), "bas_droite": (w // 2, h // 2, w, h)}
  lum = sorted(((ImageStat.Stat(g.crop(b)).mean[0], q) for q, b in boites.items()), reverse=True)
  attendu = {}
  if lum[0][0] - lum[1][0] >= ECART_QUADRANT_MIN:
    attendu["quadrant_le_plus_clair"] = lum[0][1]
  if lum[-2][0] - lum[-1][0] >= ECART_QUADRANT_MIN:
    attendu["quadrant_le_plus_sombre"] = lum[-1][1]
  return attendu
