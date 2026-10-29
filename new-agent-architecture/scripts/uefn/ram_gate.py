# -*- coding: utf-8 -*-
"""Jauge RAM avant ecriture. Reprise du gate v2 de corpo-plaza, avec deux corrections :
  - mesure mise en cache `cache_s` secondes (avant : 1 PowerShell par ecriture = lent) ;
  - plafond du working set editeur OPTIONNEL (il grossit avec le niveau : un plafond fixe
    bloquait le BUILD lui-meme).
Mesure impossible => UNKNOWN, jamais une valeur inventee."""
import subprocess
import time

from .config import maintenant

PS = (
    "$os=Get-CimInstance Win32_OperatingSystem;"
    "$free=[math]::Round($os.FreePhysicalMemory/1024);"
    "$tot=[math]::Round($os.TotalVisibleMemorySize/1024);"
    "$eds=Get-Process | Where-Object {$_.ProcessName -like 'UnrealEditorFortnite*'};"
    "$ws=-1;"
    "if($eds){$e=$eds|Sort-Object WorkingSet64 -Descending|Select-Object -First 1;"
    "$ws=[math]::Round($e.WorkingSet64/1MB)}"
    "Write-Output \"$free|$tot|$ws\""
)


class JaugeRAM:
    def __init__(self, cfg_ram):
        self.cfg = cfg_ram
        self._cache = None
        self._cache_t = 0.0

    def mesurer(self, forcer=False):
        if not forcer and self._cache and time.time() - self._cache_t < self.cfg["cache_s"]:
            return dict(self._cache, cache=True)
        m = {"ts_utc": maintenant()}
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command", PS],
                                 capture_output=True, text=True, timeout=60)
            free, tot, ws = (int(x) for x in out.stdout.strip().split("|"))
        except Exception as e:  # noqa: BLE001 - toute erreur = UNKNOWN
            m.update(statut="UNKNOWN", raison="mesure impossible : %s" % e)
            return m
        m.update(free_mo=free, total_mo=tot, editeur_ws_mo=ws if ws >= 0 else None)
        if ws < 0:
            m.update(statut="UNKNOWN", raison="processus UnrealEditorFortnite introuvable")
            return m
        ok = free >= self.cfg["free_mo_min"]
        plafond = self.cfg.get("editeur_ws_mo_max")
        if plafond is not None:
            ok = ok and ws < plafond
        m["statut"] = "OK" if ok else "FRANCHI"
        self._cache, self._cache_t = m, time.time()
        return m

    def attendre(self):
        """Fenetre d'attente avant ecriture. Retourne (ok, derniere_mesure)."""
        fin = time.time() + self.cfg["fenetre_max_s"]
        m = self.mesurer()
        while m["statut"] == "FRANCHI" and time.time() < fin:
            time.sleep(self.cfg["polling_s"])
            m = self.mesurer(forcer=True)
        return m["statut"] == "OK", m
