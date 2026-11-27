import http.server
import socketserver
import webbrowser
import threading
import json
import asyncio
import sys
import urllib.parse
from pathlib import Path
from radar.config import BRIEFINGS_DIR
from radar.mcp_server.storage.db import get_all_tracked_entities, init_db
from radar.ui.generator import generate_radar_html_from_state

DEFAULT_PORT = 8844

# Global scanning state for UI polling
SCAN_STATE = {
    "status": "idle",      # "idle", "running", "completed", "error"
    "step": "",
    "topic": "",
    "error": None,
    "latest_result": None
}

def _run_engine_thread(topic: str):
    """Run the multi-agent pipeline in a separate thread so the HTTP server never blocks."""
    global SCAN_STATE
    try:
        SCAN_STATE["status"] = "running"
        SCAN_STATE["topic"] = topic
        SCAN_STATE["error"] = None
        SCAN_STATE["step"] = "Initializing Swarm..."

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(init_db())
        from radar.orchestrator.engine import RadarEngine
        engine = RadarEngine()

        def on_step(step_name: str, state):
            SCAN_STATE["step"] = step_name

        state = loop.run_until_complete(engine.run(topic=topic, on_step=on_step))
        
        # Generate the latest HTML file
        generate_radar_html_from_state(state)

        # Build payload for the frontend
        from radar.ui.generator import classify_ring
        items_payload = []
        for item in state.verified_items:
            cand = item.candidate
            sig = cand.signal
            items_payload.append({
                "title": sig.title,
                "url": sig.url,
                "category": cand.category,
                "ring": classify_ring(cand.novelty_score, cand.velocity_score),
                "novelty_score": cand.novelty_score,
                "velocity_score": cand.velocity_score,
                "source_type": sig.source_type,
                "verified_metrics": item.verified_metrics,
                "velocity_delta": sig.metrics.get("velocity_delta", {}),
                "justification": cand.justification,
                "fact_check_notes": item.fact_check_notes
            })

        SCAN_STATE["latest_result"] = {
            "topic": topic,
            "run_id": state.run_id[:8],
            "items": items_payload
        }
        SCAN_STATE["status"] = "completed"
        SCAN_STATE["step"] = "Radar Scan Completed!"
        loop.close()

    except Exception as e:
        import traceback
        traceback.print_exc()
        SCAN_STATE["status"] = "error"
        SCAN_STATE["error"] = str(e)
        SCAN_STATE["step"] = f"Failed: {str(e)}"

class RadarHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the minimal Tech Radar UI and handles live browser-driven scans."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BRIEFINGS_DIR), **kwargs)

    def _get_clean_path(self) -> str:
        parsed = urllib.parse.urlparse(self.path).path
        clean = parsed.rstrip('/')
        return clean if clean else "/"

    def _send_json(self, status: int, data: dict):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        clean_path = self._get_clean_path()

        if clean_path in ("/", "/index.html"):
            latest_file = BRIEFINGS_DIR / "radar_latest.html"
            if not latest_file.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>Preparing Radar...</h1><script>location.reload();</script>")
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(latest_file.read_bytes())
            return

        elif clean_path == "/api/scan-status":
            self._send_json(200, SCAN_STATE)
            return

        elif clean_path == "/api/radar-data":
            try:
                if sys.platform == "win32":
                    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                entities = loop.run_until_complete(get_all_tracked_entities())
                loop.close()

                self._send_json(200, {"count": len(entities), "entities": entities})
                return
            except Exception as e:
                self._send_json(500, {"error": str(e)})
                return

        elif clean_path.startswith("/api/"):
            self._send_json(404, {"error": f"API endpoint not found: {clean_path}"})
            return

        return super().do_GET()

    def do_POST(self):
        clean_path = self._get_clean_path()

        if clean_path == "/api/scan":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                try:
                    payload = json.loads(body.decode("utf-8")) if body else {}
                except Exception:
                    self._send_json(400, {"error": "Invalid JSON in request body"})
                    return

                topic = payload.get("topic", "").strip()
                if not topic:
                    self._send_json(400, {"error": "Topic is required"})
                    return

                if SCAN_STATE["status"] == "running":
                    self._send_json(409, {"error": "A scan is already in progress. Please wait for it to complete."})
                    return

                # Start background scan thread
                t = threading.Thread(target=_run_engine_thread, args=(topic,), daemon=True)
                t.start()

                self._send_json(202, {"status": "started", "topic": topic})
                return

            except Exception as e:
                self._send_json(500, {"error": str(e)})
                return

        # Unknown POST endpoint
        self._send_json(404, {"error": f"POST endpoint not found: {clean_path}"})

def start_radar_server(port: int = DEFAULT_PORT, auto_open: bool = True):
    """Start local server and open the interactive Tech Radar in the browser."""
    actual_port = port
    server = None
    for attempt in range(5):
        try:
            server = socketserver.TCPServer(("127.0.0.1", actual_port), RadarHTTPRequestHandler)
            break
        except OSError:
            actual_port += 1

    if not server:
        raise RuntimeError(f"Could not bind server to port range {port}-{actual_port}")

    url = f"http://127.0.0.1:{actual_port}/"
    print(f"\n📡 Modern Tech Radar UI running at: {url}")
    print("Type your topic directly in the browser to run live scans. Press Ctrl+C to stop.\n")

    if auto_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Radar Web Server...")
    finally:
        server.server_close()
