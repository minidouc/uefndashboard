# -*- coding: utf-8 -*-
"""
garde.py -- hook PreToolUse : le "security chokepoint outside the model's reasoning" (WP1 p.35)
et le before_tool_callback (WP1 p.38). S'execute AVANT chaque Edit/Write/Bash/PowerShell de
Claude ET de ses sous-agents. Code 2 = action bloquee, le message est renvoye au modele.

Ce qu'il empeche (lecons de corpo-plaza) :
  - modifier les validateurs, leur MANIFEST, le golden set ou ces hooks eux-memes ;
  - ecrire l'etat, les lots, les traces, les rapports de validation a la main
    (seuls les scripts les produisent : provenance garantie) ;
  - parler au MCP en direct (curl, python -c, ancien mcp_probe) au lieu de la passerelle ;
  - lancer les actions reservees a l'humain (re-verrouillage des validateurs).
"""
import json
import re
import sys

_DEBUT = r"(?:^|[\\/\s\"'=])"  # debut de chemin : absolu, relatif apres une espace, entre guillemets
PROTEGES_ECRITURE = [_DEBUT + m for m in (
    r"validators[\\/]",                       # regles, golden, MANIFEST
    r"\.claude[\\/](hooks[\\/]|settings)",    # hooks + settings : le garde ne se desactive pas lui-meme
    r"tools[\\/]lock_validators\.py",
    r"config[\\/]studio\.json",               # allowlist des ecritures MCP : decision humaine
    r"config[\\/]circuit_breakers\.json",
    r"state[\\/](state\.json|events\.jsonl)",
    r"build[\\/]studio[\\/](lots|runs|captures|spikes)[\\/]",
    r"build[\\/]studio[\\/](trace\.jsonl|baseline_preexistants\.json|lot_plan\.json|preflight\.json)",
    r"qa[\\/]validation[\\/]",
)]
HUMAIN_SEULEMENT = [r"tools[\\/]lock_validators\.py", r"tools[\\/]make_golden\.py"]
MCP_DIRECT = [r"127\.0\.0\.1:8000", r"localhost:8000", r"mcp_probe", r"ep_build", r"run_build_all",
              r"import\s+.*mcp_gateway", r"from\s+scripts\.uefn"]
OPS_ECRITURE = r"(\btee\b|\bsed\s+-i|\brm\b|\bmv\b|\bcp\b|\bdel\b|\bcopy\b|\bmove\b|Remove-Item|Set-Content|" \
               r"Out-File|Add-Content|Copy-Item|Move-Item|New-Item|\bopen\(|write_text|\btruncate\b|\bchmod\b)"


sys.stderr.reconfigure(encoding="utf-8")


def bloquer(msg):
    sys.stderr.write("BLOQUE PAR LE GARDE DU STUDIO : " + msg +
                     "\nSi c'est legitime, c'est une decision HUMAINE (voir docs/runbook.md).")
    sys.exit(2)


def main():
    try:
        evt = json.load(sys.stdin)
    except ValueError:
        bloquer("entree du hook illisible : par securite, l'action est refusee (fail-closed).")
    outil = evt.get("tool_name", "")
    entree = evt.get("tool_input") or {}

    if outil in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        chemin = entree.get("file_path") or entree.get("notebook_path") or ""
        for motif in PROTEGES_ECRITURE:
            if re.search(motif, chemin, re.I):
                bloquer("%s est protege (produit par un script ou reserve a l'humain)." % chemin)
        sys.exit(0)

    if outil in ("Bash", "PowerShell"):
        cmd = entree.get("command") or ""
        for motif in HUMAIN_SEULEMENT:
            if re.search(motif, cmd, re.I):
                bloquer("action reservee a l'humain : %s" % motif)
        for motif in MCP_DIRECT:
            if re.search(motif, cmd, re.I) and "python -m scripts.uefn.mcp_gateway" not in cmd:
                bloquer("acces MCP direct interdit : passer par scripts/*.py (passerelle unique).")
        for cible in re.findall(r">{1,2}\s*([^\s;&|]+)", cmd):
            for motif in PROTEGES_ECRITURE:
                if re.search(motif, cible, re.I):
                    bloquer("redirection vers un chemin protege (%s)." % cible)
        if re.search(OPS_ECRITURE, cmd, re.I):
            for motif in PROTEGES_ECRITURE:
                if re.search(motif, cmd, re.I):
                    bloquer("commande d'ecriture visant un chemin protege (%s)." % motif)
    sys.exit(0)


if __name__ == "__main__":
    main()
