"""Flask add-on that lets a robot dashboard drive the Diggy avatar page.

Register the blueprint on your existing Flask app, then call publish() wherever the
dashboard listens, thinks, speaks, or changes the robot's LED color:

    from diggy_avatar_bridge import avatar_bp, publish
    app.register_blueprint(avatar_bp)

    publish({"type": "state", "state": "listening"})
    publish({"type": "state", "state": "thinking"})
    publish({"type": "speak", "text": reply_text})
    publish({"type": "led", "color": "#ff8800"})

To play the voice in the tablet's browser, save the speech as a WAV file and pass its URL:

    publish({"type": "speak", "text": reply_text, "audio_url": stage_audio("reply.wav")})

Open http://<dashboard-ip>:<port>/avatar/ on the tablet. Run this file directly to try the
avatar without the dashboard: python diggy_avatar_bridge.py
"""
import json
import queue
import re
import shutil
import tempfile
import threading
import uuid
from pathlib import Path

from flask import Blueprint, Response, jsonify, request, send_from_directory

_HERE = Path(__file__).resolve().parent
AUDIO_DIR = Path(tempfile.gettempdir()) / "diggy_avatar_audio"
_AUDIO_NAME = re.compile(r"^[0-9a-f]{32}\.wav$")
_KEEP_AUDIO = 20
_STATES = {"idle", "listening", "thinking"}
_REPLAYED = {"state", "led", "subtitles"}  # a tablet that joins late gets the latest of each

avatar_bp = Blueprint("diggy_avatar", __name__, url_prefix="/avatar")

_subscribers = set()
_latest = {}
_lock = threading.Lock()


def listener_count() -> int:
    """How many avatar pages are connected right now."""
    with _lock:
        return len(_subscribers)


def stage_audio(wav_path) -> str:
    """Copy a WAV file where the tablet can fetch it and return its URL for a speak event.

    Only the newest few files are kept, so the folder never grows.
    """
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.wav"
    shutil.copyfile(wav_path, AUDIO_DIR / name)
    old = sorted(AUDIO_DIR.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)[_KEEP_AUDIO:]
    for p in old:
        try:
            p.unlink()
        except OSError:
            pass
    return f"/avatar/audio/{name}"


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
    return send_from_directory(_HERE, "diggy_avatar.html")


@avatar_bp.get("/audio/<name>")
def audio(name):
    if not _AUDIO_NAME.match(name):
        return jsonify(error="Not found."), 404
    resp = send_from_directory(AUDIO_DIR, name, mimetype="audio/wav")
    resp.headers["Cache-Control"] = "no-store"
    return resp


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
