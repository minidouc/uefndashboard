// JSON-RPC 2.0 + WebSocket client for Map Creator Rust App Server

let nextId = 1;
let ws = null;
let reconnectTimer = null;
const eventListeners = new Set();
const statusListeners = new Set();
let wsStatus = 'connecting';

function setWsStatus(st) {
  wsStatus = st;
  for (const fn of statusListeners) fn(st);
}

export function getWsStatus() {
  return wsStatus;
}

export function onWsStatus(fn) {
  statusListeners.add(fn);
  fn(wsStatus);
  return () => statusListeners.delete(fn);
}

export function onServerEvent(fn) {
  eventListeners.add(fn);
  return () => eventListeners.delete(fn);
}

export function connectEventStream() {
  if (typeof window === 'undefined') return;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${proto}//${window.location.host}/ws`;
  setWsStatus('connecting');
  try {
    ws = new WebSocket(url);
  } catch {
    setWsStatus('offline');
    return;
  }

  ws.onopen = () => {
    setWsStatus('connected');
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.method === 'event' && msg.params) {
        for (const fn of eventListeners) fn(msg.params);
      }
    } catch {
      // ignore malformed frames
    }
  };

  ws.onclose = () => {
    setWsStatus('offline');
    ws = null;
    if (!reconnectTimer) {
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connectEventStream();
      }, 2500);
    }
  };

  ws.onerror = () => {
    setWsStatus('offline');
  };
}

export async function rpc(method, params = {}) {
  const id = nextId++;
  const res = await fetch('/rpc', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id, method, params })
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} lors de l'appel ${method}`);
  }
  const data = await res.json();
  if (data.error) {
    throw new Error(data.error.message || `Erreur RPC ${data.error.code}`);
  }
  return data.result;
}
