import unreal
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, threading, traceback, queue, time

# Queue pour passer les scripts du thread HTTP au main thread
script_queue = queue.Queue()
results = {}
results_lock = threading.Lock()

class BridgeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {'status': 'ok', 'editor': 'UEFN'}
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path != '/run-script':
            self.send_response(404)
            self.end_headers()
            return
        
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length))
        script = body.get('script', '')
        
        # Génère un ID unique pour cette requête
        request_id = f"{id(script)}_{threading.get_ident()}_{time.time()}"
        
        # Met le script dans la queue pour exécution sur le main thread
        script_queue.put((request_id, script))
        
        # Attend le résultat (avec timeout)
        timeout = 60
        start = time.time()
        while True:
            with results_lock:
                if request_id in results:
                    break
            if time.time() - start > timeout:
                self.send_response(504)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Timeout waiting for result'
                }).encode())
                return
            time.sleep(0.05)
        
        with results_lock:
            result = results.pop(request_id)
        
        status_code = 200 if result.get('success') else 500
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())
    
    def log_message(self, format, *args):
        unreal.log(f"[Bridge] {format % args}")

def execute_on_main_thread(*args):
    """Fonction appelée sur le main thread - accepte les args d'Unreal"""
    while not script_queue.empty():
        try:
            request_id, script = script_queue.get_nowait()
        except queue.Empty:
            break
        
        try:
            exec_globals = {
                'unreal': unreal,
                'json': json,
                'result': {'status': 'ok', 'operations': 0}
            }
            exec(script, exec_globals)
            with results_lock:
                results[request_id] = {
                    'success': True,
                    'result': exec_globals.get('result', {})
                }
        except Exception as e:
            with results_lock:
                results[request_id] = {
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                }

def start():
    # Démarre le serveur HTTP dans un thread
    server = HTTPServer(('127.0.0.1', 8790), BridgeHandler)
    unreal.log("[Bridge] HTTP server running on http://127.0.0.1:8790")
    
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    
    # Enregistre le callback sur le main thread
    unreal.register_slate_post_tick_callback(execute_on_main_thread)
    unreal.log("[Bridge] Main thread executor registered")

start()
unreal.log("[Bridge] Started with main thread execution")