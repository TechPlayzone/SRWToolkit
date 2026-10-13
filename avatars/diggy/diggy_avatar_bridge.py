"""Flask add-on that lets a robot dashboard drive the Diggy avatar page.

Register the blueprint on your existing Flask app, then call publish() wherever the
dashboard listens, thinks, speaks, or changes the robot's LED color:

    from diggy_avatar_bridge import avatar_bp, publish
    app.register_blueprint(avatar_bp)

    publish({"type": "state", "state": "listening"})
    publish({"type": "state", "state": "thinking"})
    publish({"type": "speak", "text": reply_text})
    publish({"type": "led", "color": "#ff8800"})

Open http://<dashboard-ip>:<port>/avatar/ on the tablet. Run this file directly to try the
avatar without the dashboard: python diggy_avatar_bridge.py
"""
import json
import queue
import threading
from pathlib import Path

from flask import Blueprint, Response, jsonify, request, send_from_directory

_HERE = Path(__file__).resolve().parent
_STATES = {"idle", "listening", "thinking"}
_REPLAYED = {"state", "led", "subtitles"}  # a tablet that joins late gets the latest of each

avatar_bp = Blueprint("diggy_avatar", __name__, url_prefix="/avatar")

_subscribers = set()
_latest = {}
_lock = threading.Lock()


def publish(event: dict) -> int:
    """Send an event to every open avatar page. Returns how many pages received it."""
    payload = json.dumps(event)
    with _lock:
        if event.get("type") in _REPLAYED:
            _latest[event["type"]] = payload
        targets = list(_subscribers)
    for q in targets:
        try:
            q.put_nowait(payload)
        except queue.Full:
            pass  # a stalled tablet should never block the dashboard
    return len(targets)


@avatar_bp.get("/")
@avatar_bp.get("/index.html")
def page():
    return send_from_directory(_HERE, "index.html")


@avatar_bp.get("/events")
def events():
    q = queue.Queue(maxsize=100)
    with _lock:
        _subscribers.add(q)
        backlog = list(_latest.values())

    def stream():
        try:
            for payload in backlog:
                yield f"data: {payload}\n\n"
            while True:
                try:
                    yield f"data: {q.get(timeout=15)}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            with _lock:
                _subscribers.discard(q)

    resp = Response(stream(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Access-Control-Allow-Origin"] = "*"  # lets the page load from another origin via ?server=
    return resp


@avatar_bp.post("/say")
def say():
    """Test helper: curl -X POST -H 'Content-Type: application/json' -d '{"text":"Woof!"}' .../avatar/say"""
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()
    if not text:
        return jsonify(error="Send JSON with a non-empty \"text\" field."), 400
    event = {"type": "speak", "text": text}
    for key in ("audio_url", "duration_ms", "led"):
        if key in data:
            event[key] = data[key]
    return jsonify(delivered_to=publish(event))


@avatar_bp.post("/state")
def state():
    """Test helper: send {"state": "listening" | "thinking" | "idle"}."""
    data = request.get_json(silent=True) or {}
    if data.get("state") not in _STATES:
        return jsonify(error=f"\"state\" must be one of {sorted(_STATES)}."), 400
    event = {"type": "state", "state": data["state"]}
    if "led" in data:
        event["led"] = data["led"]
    return jsonify(delivered_to=publish(event))


if __name__ == "__main__":
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(avatar_bp)
    print("Diggy avatar: http://localhost:5051/avatar/")
    app.run(host="0.0.0.0", port=5051, threaded=True)
