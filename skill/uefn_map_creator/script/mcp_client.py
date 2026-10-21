#!/usr/bin/env python3
"""Client MCP serie pour l'editeur UEFN (unreal-mcp, http://127.0.0.1:8000/mcp).

Portage Python du client Node teste le 2026-10-19 (mcp_tests/tools/mcp.js).
Un seul appel a la fois : l'editeur execute tout sur le game thread.

CLI :
  python mcp_client.py ping
  python mcp_client.py call <Toolset> <tool> ['{"json": "args"}' | @fichier.json] [--max N]
  python mcp_client.py list
Options : --max N (troncature, 4000 par defaut), --log FICHIER (journal JSONL).
Toolset : nom complet ou alias court (Scene, Actor, Device, Prog, EditorApp, ...).
Code retour : 0 ok, 1 erreur outil, 2 editeur injoignable, 3 timeout (etat inconnu).
Sans --log ni UEFN_MCP_LOG, un appel direct n'est PAS journalise : passer
`--log <workspace>/_mcp_calls.jsonl` pour garder la trace (le CLI spatial le fait deja).
"""

import json
import os
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.request

URL = os.environ.get("UEFN_MCP_URL", "http://127.0.0.1:8000/mcp")
TIMEOUT_S = float(os.environ.get("UEFN_MCP_TIMEOUT", "60"))
SESSION_FILE = os.path.join(tempfile.gettempdir(), "uefn_mcp_session.txt")

TOOLSETS = {
    "EditorApp": "EditorToolset.EditorAppToolset",
    "Logs": "EditorToolset.LogsToolset",
    "Verse": "ValkyrieToolset.VerseToolset",
    "Session": "ValkyrieToolset.SessionToolset",
    "Device": "ValkyrieToolset.DeviceToolset",
    "Entity": "ValkyrieToolset.EntityToolset",
    "Python": "ValkyrieToolset.ValkyriePythonToolset",
    "Actor": "editor_toolset.toolsets.actor.ActorTools",
    "Asset": "editor_toolset.toolsets.asset.AssetTools",
    "Object": "editor_toolset.toolsets.object.ObjectTools",
    "Primitive": "editor_toolset.toolsets.primitive.PrimitiveTools",
    "Prog": "editor_toolset.toolsets.programmatic.ProgrammaticToolset",
    "Scene": "editor_toolset.toolsets.scene.SceneTools",
    "SMesh": "editor_toolset.toolsets.static_mesh.StaticMeshTools",
}


class McpError(Exception):
  """Erreur renvoyee par l'outil ou le serveur (l'appel a ete traite)."""


class McpOffline(McpError):
  """Editeur eteint ou port ferme : rien n'a ete execute."""


class McpTimeout(McpError):
  """Pas de reponse a temps : l'action a PEUT-ETRE eu lieu, relire l'etat."""


def _parse_body(text: str, content_type: str):
  if "text/event-stream" in content_type:
    found = None
    for line in text.splitlines():
      if line.startswith("data:"):
        try:
          j = json.loads(line[5:].strip())
        except ValueError:
          continue
        if isinstance(j, dict) and "id" in j:
          found = j
    return found
  if not text:
    return None
  try:
    return json.loads(text)
  except ValueError:
    return {"raw": text}


class McpClient:

  def __init__(self, url: str = URL, log_path: str | None = None):
    self.url = url
    self.log_path = log_path
    self._id = int(time.time() * 1000) % 1_000_000_000

  def _post(self, body: dict, sid: str | None):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if sid:
      headers["Mcp-Session-Id"] = sid
    req = urllib.request.Request(
        self.url, data=json.dumps(body).encode("utf-8"), headers=headers,
        method="POST")
    try:
      with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        text = resp.read().decode("utf-8", errors="replace")
        return (resp.status, resp.headers.get("mcp-session-id"),
                _parse_body(text, resp.headers.get("content-type", "")))
    except urllib.error.HTTPError as exc:
      text = exc.read().decode("utf-8", errors="replace")
      return exc.code, None, _parse_body(text, exc.headers.get("content-type", ""))
    except (socket.timeout, TimeoutError) as exc:
      raise McpTimeout(f"timeout {TIMEOUT_S}s : {exc}") from exc
    except urllib.error.URLError as exc:
      if isinstance(exc.reason, (socket.timeout, TimeoutError)):
        raise McpTimeout(f"timeout {TIMEOUT_S}s : {exc}") from exc
      raise McpOffline(f"editeur injoignable sur {self.url} : {exc.reason}") from exc
    except ConnectionError as exc:
      raise McpOffline(f"editeur injoignable sur {self.url} : {exc}") from exc

  def _next_id(self) -> int:
    self._id += 1
    return self._id

  def _session(self, fresh: bool = False) -> str:
    if not fresh and os.path.exists(SESSION_FILE):
      with open(SESSION_FILE, "r", encoding="utf-8") as f:
        sid = f.read().strip()
      if sid:
        return sid
    status, sid, _ = self._post({
        "jsonrpc": "2.0", "id": self._next_id(), "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "uefn-map-creator", "version": "2.0"}},
    }, None)
    if status != 200 or not sid:
      raise McpError(f"initialize refuse : HTTP {status}, session={sid}")
    self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
      f.write(sid)
    return sid

  def raw(self, method: str, params: dict) -> dict:
    t0 = time.time()
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "method": method,
             "params": params}
    try:
      sid = self._session()
      body = {"jsonrpc": "2.0", "id": self._next_id(), "method": method,
              "params": params}
      status, _, j = self._post(body, sid)
      if status in (400, 404):
        sid = self._session(fresh=True)
        body["id"] = self._next_id()
        status, _, j = self._post(body, sid)
      entry.update(http_status=status, response=j)
      if status != 200:
        raise McpError(f"HTTP {status} : {json.dumps(j)[:500]}")
      if j and "error" in j:
        raise McpError(f"JSON-RPC : {json.dumps(j['error'])[:500]}")
      return (j or {}).get("result", {})
    except McpError as exc:
      entry["error"] = f"{type(exc).__name__}: {exc}"
      raise
    finally:
      entry["duration_ms"] = int((time.time() - t0) * 1000)
      self._log(entry)

  def _log(self, entry: dict) -> None:
    if not self.log_path:
      return
    def scrub(o):
      if isinstance(o, dict):
        return {k: (f"<b64 {len(v)}>" if k == "data" and isinstance(v, str)
                    and len(v) > 200 else scrub(v)) for k, v in o.items()}
      if isinstance(o, list):
        return [scrub(x) for x in o]
      return o
    os.makedirs(os.path.dirname(os.path.abspath(self.log_path)), exist_ok=True)
    with open(self.log_path, "a", encoding="utf-8") as f:
      f.write(json.dumps(scrub(entry), ensure_ascii=False) + "\n")

  def call(self, toolset: str, tool: str, args: dict | None = None) -> dict:
    """Renvoie {"value": returnValue ou contenu, "content": brut, "images": [...]}.

    Leve McpError si isError. ATTENTION : un retour vide ou null ne prouve
    rien (14 appels invalides sur 211 n'ont renvoye aucune erreur).
    """
    res = self.raw("tools/call", {
        "name": "call_tool",
        "arguments": {"toolset_name": TOOLSETS.get(toolset, toolset),
                      "tool_name": tool, "arguments": args or {}},
    })
    items = res.get("content", []) if isinstance(res, dict) else []
    texts = []
    for c in items:
      if c.get("type") == "text":
        try:
          texts.append(json.loads(c.get("text", "")))
        except ValueError:
          texts.append(c.get("text", ""))
    images = [{"mimeType": c.get("mimeType"), "data": c.get("data", "")}
              for c in items if c.get("type") == "image"]
    content = texts[0] if len(texts) == 1 else texts
    if res.get("isError"):
      raise McpError(f"{toolset}.{tool} : {json.dumps(content, ensure_ascii=False)[:800]}")
    value = content.get("returnValue", content) if isinstance(content, dict) else content
    return {"value": value, "content": content, "images": images}

  def value(self, toolset: str, tool: str, args: dict | None = None):
    return self.call(toolset, tool, args)["value"]

  def script(self, source: str):
    """execute_tool_script : renvoie le dict retourne par run() (chaine JSON parsee)."""
    v = self.value("Prog", "execute_tool_script", {"script": source})
    if isinstance(v, str):
      try:
        return json.loads(v)
      except ValueError:
        return v
    return v

  def ping(self) -> dict:
    t0 = time.time()
    level = self.value("Scene", "get_current_level", {})
    return {"level": level, "ms": int((time.time() - t0) * 1000)}


def _main(argv: list[str]) -> int:
  max_len = 4000
  log_path = os.environ.get("UEFN_MCP_LOG")
  if "--max" in argv:
    i = argv.index("--max")
    max_len = int(argv[i + 1])
    del argv[i:i + 2]
  if "--log" in argv:
    i = argv.index("--log")
    log_path = argv[i + 1]
    del argv[i:i + 2]
  if not argv:
    print(__doc__)
    return 2
  cli = McpClient(log_path=log_path)
  try:
    if argv[0] == "ping":
      out = cli.ping()
    elif argv[0] == "list":
      out = cli.raw("tools/call", {"name": "list_toolsets", "arguments": {}})
    elif argv[0] == "call" and len(argv) >= 3:
      raw = argv[3] if len(argv) > 3 else "{}"
      if raw.startswith("@"):
        with open(raw[1:], "r", encoding="utf-8") as f:
          raw = f.read()
      r = cli.call(argv[1], argv[2], json.loads(raw))
      out = {"value": r["value"], "images": [
          {"mimeType": i["mimeType"], "b64_len": len(i["data"])} for i in r["images"]]}
    else:
      print(__doc__)
      return 2
  except McpOffline as exc:
    print(json.dumps({"status": "OFFLINE", "error": str(exc)}))
    return 2
  except McpTimeout as exc:
    print(json.dumps({"status": "TIMEOUT_OUTCOME_UNKNOWN", "error": str(exc)}))
    return 3
  except McpError as exc:
    print(json.dumps({"status": "TOOL_ERROR", "error": str(exc)}, ensure_ascii=False))
    return 1
  s = json.dumps(out, ensure_ascii=False)
  print(s if len(s) <= max_len else s[:max_len] + " ...[tronque]")
  return 0


if __name__ == "__main__":
  sys.exit(_main(sys.argv[1:]))
