from flask import Flask, request, jsonify, render_template, abort
from database import init_db, get_db
import uuid, time, os
from datetime import datetime, timezone

app = Flask(__name__)
init_db()

# ---------- Force JSON for API routes ----------
@app.after_request
def add_json_header(response):
    if request.path.startswith("/api/"):
        response.headers["Content-Type"] = "application/json"
    return response

# ---------- Deterministic Time ----------
def current_time():
    if os.getenv("TEST_MODE") == "1":
        header = request.headers.get("x-test-now-ms")
        if header:
            return int(header) // 1000
    return int(time.time())

# ---------- Health Check ----------
@app.route("/api/healthz")
def health():
    try:
        get_db().execute("SELECT 1")
        return jsonify({"ok": True}), 200
    except:
        return jsonify({"ok": False}), 500

# ---------- Create Paste ----------
@app.route("/api/pastes", methods=["POST"])
def create_paste():
    data = request.get_json()

    if not data or not isinstance(data.get("content"), str) or not data["content"].strip():
        return jsonify({"error": "Invalid input"}), 400

    ttl = data.get("ttl_seconds")
    max_views = data.get("max_views")

    if ttl is not None and (not isinstance(ttl, int) or ttl < 1):
        return jsonify({"error": "Invalid ttl_seconds"}), 400

    if max_views is not None and (not isinstance(max_views, int) or max_views < 1):
        return jsonify({"error": "Invalid max_views"}), 400

    paste_id = str(uuid.uuid4())
    created_at = int(time.time())

    db = get_db()
    db.execute("""
        INSERT INTO pastes (id, content, created_at, ttl_seconds, max_views, views_used)
        VALUES (?, ?, ?, ?, ?, 0)
    """, (paste_id, data["content"], created_at, ttl, max_views))
    db.commit()

    return jsonify({
        "id": paste_id,
        "url": request.host_url.rstrip("/") + "/p/" + paste_id
    }), 201

# ---------- Fetch Paste (API) ----------
@app.route("/api/pastes/<paste_id>")
def fetch_paste(paste_id):
    db = get_db()
    paste = db.execute("SELECT * FROM pastes WHERE id=?", (paste_id,)).fetchone()

    if not paste:
        return jsonify({"error": "Not found"}), 404

    now = current_time()

    # TTL check
    if paste["ttl_seconds"] and now > paste["created_at"] + paste["ttl_seconds"]:
        return jsonify({"error": "Expired"}), 404

    # View limit check
    if paste["max_views"] and paste["views_used"] >= paste["max_views"]:
        return jsonify({"error": "View limit exceeded"}), 404

    # Increment view count
    db.execute(
        "UPDATE pastes SET views_used = views_used + 1 WHERE id=?",
        (paste_id,)
    )
    db.commit()

    remaining_views = None
    if paste["max_views"]:
        remaining_views = max(0, paste["max_views"] - (paste["views_used"] + 1))

    expires_at = None
    if paste["ttl_seconds"]:
        expires_at = datetime.fromtimestamp(
            paste["created_at"] + paste["ttl_seconds"],
            tz=timezone.utc
        ).isoformat()

    return jsonify({
        "content": paste["content"],
        "remaining_views": remaining_views,
        "expires_at": expires_at
    }), 200

# ---------- View Paste (HTML) ----------
@app.route("/p/<paste_id>")
def view_paste(paste_id):
    db = get_db()
    paste = db.execute("SELECT * FROM pastes WHERE id=?", (paste_id,)).fetchone()

    if not paste:
        abort(404)

    now = current_time()

    if paste["ttl_seconds"] and now > paste["created_at"] + paste["ttl_seconds"]:
        abort(404)

    if paste["max_views"] and paste["views_used"] >= paste["max_views"]:
        abort(404)

    return render_template("view.html", content=paste["content"])

# ---------- Run ----------
if __name__ == "__main__":
    app.run(debug=True)
