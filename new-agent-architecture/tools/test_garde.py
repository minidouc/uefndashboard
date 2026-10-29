# -*- coding: utf-8 -*-
"""test_garde.py -- non-regression du hook garde.py : python tools/test_garde.py"""
import os; os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import json, subprocess, sys
cas = [
 ("Edit", {"file_path": r"C:\x\new-agent-architecture\validators\regles.py"}, 2),
 ("Write", {"file_path": "C:/x/corpo-plaza/state/state.json"}, 2),
 ("Write", {"file_path": "C:/x/.claude/settings.json"}, 2),
 ("Write", {"file_path": "C:/x/corpo-plaza/design/level/cameras.json"}, 0),
 ("Write", {"file_path": "C:/x/agents/Level_Designer/persona.md"}, 0),
 ("Write", {"file_path": "C:/x/.claude/agents/critique.md"}, 0),
 ("Edit", {"file_path": "C:/x/.claude/hooks/garde.py"}, 2),
 ("Bash", {"command": "python validators/run_all.py 2>&1 | head"}, 0),
 ("Bash", {"command": "sed -i s/FAIL/PASS/ validators/regles.py"}, 2),
 ("Bash", {"command": "echo x > qa/validation/latest.json"}, 2),
 ("Bash", {"command": "curl -X POST http://127.0.0.1:8000/mcp"}, 2),
 ("Bash", {"command": 'python -c "from scripts.uefn.mcp_gateway import Passerelle"'}, 2),
 ("Bash", {"command": "python -m scripts.uefn.mcp_gateway call SceneTools get_current_level"}, 0),
 ("Bash", {"command": "python tools/lock_validators.py"}, 2),
 ("PowerShell", {"command": r"Set-Content validators\MANIFEST.json x"}, 2),
 ("Bash", {"command": "python scripts/pose_lot.py simuler 2"}, 0),
 ("Bash", {"command": "cat validators/regles.py"}, 0),
 ("Bash", {"command": "rm -rf build/studio/lots/lot_01.json"}, 2),
]
ok = True
for outil, entree, attendu in cas:
    r = subprocess.run([sys.executable, ".claude/hooks/garde.py"], input=json.dumps({"tool_name": outil, "tool_input": entree}), capture_output=True, text=True)
    bon = r.returncode == attendu
    ok &= bon
    print("OK " if bon else "KO ", r.returncode, outil, list(entree.values())[0][:70])
r = subprocess.run([sys.executable, ".claude/hooks/garde.py"], input="pas du json", capture_output=True, text=True)
print("fail-closed:", r.returncode)
print("TOUT BON" if ok and r.returncode == 2 else "ECHECS")
sys.exit(0 if ok and r.returncode == 2 else 1)
