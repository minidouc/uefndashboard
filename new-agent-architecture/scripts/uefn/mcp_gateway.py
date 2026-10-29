# -*- coding: utf-8 -*-
"""
mcp_gateway.py -- LA SEULE PORTE vers l'editeur UEFN (WP2 p.41 : point d'entree unique).

Garanties par construction (pas par discipline du modele) :
  1. Allowlist : lecture = outil VERIFIE de l'inventaire (ou lecture prouvee) ;
     ecriture = outil liste dans studio.json/ecritures_prouvees. Sinon UNKNOWN_TOOL_BLOCKED.
  2. Circuit breaker (WP5 p.21) : config/circuit_breakers.json relu a CHAQUE appel.
  3. Schema d'entree verifie avant envoi (WP2 p.26/29) : champs requis + types de base.
  4. Erreur = STOP (WP4 p.20) : isError / HTTP / vide / timeout => rc != 0, jamais "OK".
     Seul le message "Wait 15 seconds" donne lieu a une attente puis un nouvel essai (max 3).
  5. Sorties hors contexte (WP2 p.19, WP3 p.38) : reponse COMPLETE sur disque, seul un
     resume borne est renvoye. Les images de capture sont decodees en PNG, jamais gardees en base64.
  6. Trace Glass Box (WP4 p.21) : chaque appel -> une ligne dans trace.jsonl.
  7. Appels strictement serialises : un seul appel en vol par processus.

Codes retour : 0 OK | 1 erreur outil | 2 editeur injoignable (rien execute) |
               3 timeout (etat INCONNU) | 4 refuse par politique | 5 arret jauge RAM |
               6 reponse hors contrat (vide / illisible)

Usage CLI (LECTURE SEULE -- les ecritures passent par les scripts-taches) :
  python -m scripts.uefn.mcp_gateway ping
  python -m scripts.uefn.mcp_gateway call SceneTools get_current_level "{}"
"""
import base64
import hashlib
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

from .config import CONFIG_DIR, Projet, ecrire_json, lire_json, maintenant
from .ram_gate import JaugeRAM

TIMEOUT_S = 120
COOLDOWN_S = 16
TENTATIVES_MAX = 3
TYPES_JSON = {"string": str, "number": (int, float), "integer": int,
              "boolean": bool, "object": dict, "array": list}


class Resultat:
    def __init__(self, rc, payload=None, erreur=None, preuve=None, png=None, ms=None):
        self.rc, self.payload, self.erreur = rc, payload, erreur
        self.preuve, self.png, self.ms = preuve, png, ms

    @property
    def ok(self):
        return self.rc == 0

    @property
    def valeur(self):
        """returnValue de l'outil, ou None. Ne JAMAIS remplacer None par une valeur calculee."""
        if isinstance(self.payload, dict):
            return self.payload.get("returnValue")
        return None

    def resume(self, n=600):
        d = {"rc": self.rc, "erreur": self.erreur, "preuve": self.preuve, "png": self.png}
        v = self.valeur
        if isinstance(v, list):
            d["valeur"] = {"len": len(v), "exemples": v[:2]}
        else:
            d["valeur"] = v
        s = json.dumps(d, ensure_ascii=False)
        return s if len(s) <= n else s[:n] + "...[TRONQUE, voir preuve]"


class Passerelle:
    def __init__(self, projet=None, ecriture=False, run_id=None, script="cli"):
        self.p = projet or Projet()
        self.ecriture_autorisee = ecriture
        self.url = self.p.cfg["mcp_url"]
        self.run_id = run_id or "%s_%s" % (time.strftime("%Y%m%dT%H%M%S"), script)
        self.dir_run = os.path.join(self.p.build_dir, "runs", self.run_id)
        self.dir_calls = os.path.join(self.dir_run, "calls")
        self.trace = os.path.join(self.p.build_dir, "trace.jsonl")
        self.jauge = JaugeRAM(self.p.ram)
        self._sid = None
        self._id = int(time.time() * 1000) % 1_000_000_000
        self._seq = 0
        self._charger_politique()

    # ------------------------------------------------------------------ politique
    def _charger_politique(self):
        inv = lire_json(os.path.join(CONFIG_DIR, "mcp-inventory.snapshot.json"))
        self.fq = {}       # nom court -> nom complet du toolset
        self.statut = {}   # "Toolset.outil" -> statut inventaire
        for ts in inv["toolsets"]:
            court = ts["name"].split(".")[-1]
            self.fq[court] = ts["name"]
            for t in ts["tools"]:
                self.statut["%s.%s" % (court, t["name"])] = t["statut"]
        self.schemas = lire_json(os.path.join(CONFIG_DIR, "tool_schemas.json"))
        st = self.p.studio
        self.interdits = set(st["outils_interdits_absolus"])
        self.lect_ok = set(st["statuts_autorises_lecture"])
        self.lect_prouvees = {k for k in st["lectures_prouvees"] if not k.startswith("$")}
        self.ecr_prouvees = {k for k in st["ecritures_prouvees"] if not k.startswith("$")}
        self.ecr_a_prouver = {k for k in st["ecritures_a_prouver"] if not k.startswith("$")}

    def _verifier_politique(self, cle, outil, ecriture, spike):
        cb = lire_json(os.path.join(CONFIG_DIR, "circuit_breakers.json"))
        if cle in cb.get("outils_coupes", []) or (ecriture and cb.get("ecritures_coupees")):
            return "CIRCUIT_BREAKER : %s coupe (%s)" % (cle, cb.get("raison"))
        if outil in self.interdits:
            return "INTERDIT_ABSOLU : %s" % outil
        if cle not in self.statut:
            return "UNKNOWN_TOOL_BLOCKED : %s absent de l'inventaire" % cle
        if ecriture:
            if not self.ecriture_autorisee:
                return "ECRITURE_REFUSEE : ce script n'est pas autorise a ecrire"
            if cle in self.ecr_prouvees:
                return None
            if spike and cle in self.ecr_a_prouver:
                return None
            return "UNKNOWN_TOOL_BLOCKED : ecriture %s non prouvee (studio.json)" % cle
        if self.statut[cle] in self.lect_ok or cle in self.lect_prouvees:
            return None
        return "UNKNOWN_TOOL_BLOCKED : %s statut %s" % (cle, self.statut[cle])

    def _verifier_schema(self, toolset, outil, args):
        sch = self.schemas.get(toolset, {}).get(outil)
        if not isinstance(sch, dict):
            return None  # schema non epingle : l'allowlist reste la protection
        manquants = [k for k in sch.get("required", []) if k not in args]
        if manquants:
            return "SCHEMA : champs requis manquants %s" % manquants
        for k, v in args.items():
            attendu = sch.get("properties", {}).get(k, {}).get("type")
            if attendu in TYPES_JSON and not isinstance(v, TYPES_JSON[attendu]):
                return "SCHEMA : %s doit etre %s" % (k, attendu)
        return None

    # ------------------------------------------------------------------ transport
    def _post(self, corps, sid):
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if sid:
            h["Mcp-Session-Id"] = sid
        req = urllib.request.Request(self.url, data=json.dumps(corps).encode("utf-8"),
                                     headers=h, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                txt = r.read().decode("utf-8", errors="replace")
                return r.status, r.headers.get("mcp-session-id"), _parse(txt, r.headers.get("content-type", ""))
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", errors="replace")
            return e.code, None, _parse(txt, e.headers.get("content-type", ""))
        except (socket.timeout, TimeoutError):
            return "TIMEOUT", None, None
        except (urllib.error.URLError, ConnectionError, OSError):
            return "OFFLINE", None, None

    def _session(self):
        if self._sid:
            return self._sid
        self._id += 1
        st, sid, _ = self._post({"jsonrpc": "2.0", "id": self._id, "method": "initialize",
                                 "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                            "clientInfo": {"name": "studio-gateway", "version": "2.0"}}}, None)
        if st != 200 or not sid:
            return None
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
        self._sid = sid
        return sid

    def ping(self):
        return self._session() is not None

    # ------------------------------------------------------------------ appel
    def appel(self, toolset, outil, args=None, ecriture=False, etape=None, spike=False):
        args = args or {}
        cle = "%s.%s" % (toolset, outil)
        self._seq += 1
        etape = etape or outil
        refus = self._verifier_politique(cle, outil, ecriture, spike) or \
            self._verifier_schema(toolset, outil, args)
        if refus:
            return self._clore(Resultat(4, erreur=refus), cle, etape, args, ecriture, None)

        jauge = None
        if ecriture:
            ok, jauge = self.jauge.attendre()
            if not ok:
                return self._clore(Resultat(5, erreur="JAUGE_RAM %s : rien n'a ete ecrit" % jauge.get("statut")),
                                   cle, etape, args, ecriture, jauge)

        sid = self._session()
        if not sid:
            return self._clore(Resultat(2, erreur="OFFLINE : editeur injoignable, rien execute"),
                               cle, etape, args, ecriture, jauge)
        corps_args = {"toolset_name": self.fq[toolset], "tool_name": outil, "arguments": args}
        rpc, statut, ms = None, None, None
        for tentative in range(1, TENTATIVES_MAX + 1):
            self._id += 1
            t0 = time.time()
            statut, _, rpc = self._post({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                                         "params": {"name": "call_tool", "arguments": corps_args}}, sid)
            ms = int((time.time() - t0) * 1000)
            if statut in ("OFFLINE", "TIMEOUT"):
                rc = 2 if statut == "OFFLINE" else 3
                return self._clore(Resultat(rc, erreur=statut + (" : etat INCONNU, relire avant d'agir" if rc == 3 else ""), ms=ms),
                                   cle, etape, args, ecriture, jauge)
            if "Wait 15 seconds" in _texte_erreur(rpc) and tentative < TENTATIVES_MAX:
                time.sleep(COOLDOWN_S)
                continue
            break

        if not isinstance(rpc, dict) or ("result" not in rpc and "error" not in rpc):
            return self._clore(Resultat(6, erreur="reponse hors contrat (HTTP %s)" % statut, ms=ms),
                               cle, etape, args, ecriture, jauge, rpc)
        erreur = _texte_erreur(rpc)
        payload, png_b64 = _extraire(rpc)
        res = Resultat(1 if erreur else 0, payload=payload, erreur=erreur or None, ms=ms)
        if png_b64:
            res.png = png_b64  # remplace par un chemin dans _clore
        return self._clore(res, cle, etape, args, ecriture, jauge, rpc)

    def _clore(self, res, cle, etape, args, ecriture, jauge, rpc=None):
        os.makedirs(self.dir_calls, exist_ok=True)
        base = os.path.join(self.dir_calls, "%04d_%s" % (self._seq, _nom_sur(etape)))
        if res.png and len(res.png) > 100:
            chemin_png = base + ".png"
            with open(chemin_png, "wb") as f:
                f.write(base64.b64decode(res.png))
            res.png = chemin_png
        doc = {"ts_utc": maintenant(), "run_id": self.run_id, "seq": self._seq, "etape": etape,
               "outil": cle, "ecriture": ecriture, "args": args, "rc": res.rc,
               "erreur": res.erreur, "duree_ms": res.ms, "jauge_ram": jauge,
               "payload": res.payload, "png": res.png}
        res.preuve = ecrire_json(base + ".json", doc)
        ligne = {k: doc[k] for k in ("ts_utc", "run_id", "seq", "etape", "outil", "ecriture", "rc", "erreur", "duree_ms")}
        ligne["args_sha1"] = hashlib.sha1(json.dumps(args, sort_keys=True).encode()).hexdigest()[:12]
        ligne["preuve"] = os.path.relpath(res.preuve, self.p.root).replace("\\", "/")
        os.makedirs(os.path.dirname(self.trace), exist_ok=True)
        with open(self.trace, "a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
        return res


def _parse(texte, ctype):
    if "text/event-stream" in (ctype or ""):
        trouve = None
        for l in texte.splitlines():
            if l.startswith("data:"):
                try:
                    j = json.loads(l[5:].strip())
                except ValueError:
                    continue
                if isinstance(j, dict) and "id" in j:
                    trouve = j
        return trouve
    if not texte:
        return None
    try:
        return json.loads(texte)
    except ValueError:
        return {"raw": texte[:2000]}


def _texte_erreur(rpc):
    if not isinstance(rpc, dict):
        return ""
    if rpc.get("error"):
        return json.dumps(rpc["error"], ensure_ascii=False)[:600]
    res = rpc.get("result") or {}
    if isinstance(res, dict) and res.get("isError"):
        c = res.get("content") or []
        if c and isinstance(c[0], dict):
            return str(c[0].get("text", "isError"))[:600]
        return "isError"
    return ""


def _extraire(rpc):
    """(payload JSON, image base64 eventuelle). content[0].text est du JSON encode."""
    res = rpc.get("result") if isinstance(rpc, dict) else None
    if not isinstance(res, dict):
        return None, None
    payload, image = None, None
    for c in res.get("content") or []:
        if not isinstance(c, dict):
            continue
        if c.get("type") == "text" and payload is None:
            try:
                payload = json.loads(c.get("text", ""))
            except ValueError:
                payload = {"_texte": c.get("text", "")[:2000]}
        elif c.get("type") == "image":
            image = c.get("data")
    return payload, image


def _nom_sur(s):
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(s))[:80]


def main(argv):
    if not argv:
        print(__doc__)
        return 0
    gw = Passerelle(script="cli")
    if argv[0] == "ping":
        ok = gw.ping()
        print(json.dumps({"mcp": "OK" if ok else "OFFLINE", "url": gw.url}))
        return 0 if ok else 2
    if argv[0] == "call" and len(argv) >= 3:
        args = json.loads(argv[3]) if len(argv) > 3 else {}
        r = gw.appel(argv[1], argv[2], args, ecriture=False)
        print(r.resume())
        return r.rc
    print(__doc__)
    return 4


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
