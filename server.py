# from flask import Flask, request, jsonify, Response, send_from_directory, send_file
# from flask_cors import CORS
# import subprocess
# import json
# import os
# import sys
# import threading
# import queue

# app = Flask(__name__, static_folder="frontend/dist", static_url_path="")
# CORS(app)

# SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")

# # Outputs always land in a predictable folder next to server.py
# OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "outputs")
# os.makedirs(OUTPUTS_DIR, exist_ok=True)

# # Active process registry
# active_processes = {}
# log_queues = {}

# # Per-job output file tracking (so frontend knows what to download)
# job_output_files = {}

# # WhatsApp ready-signal: use threading.Event for proper thread-safe signaling
# # (avoids the busy-sleep loop blocking a Flask thread)
# _whatsapp_ready_event = threading.Event()


# def stream_process(job_id, cmd):
#     q = log_queues[job_id]
#     try:
#         proc = subprocess.Popen(
#             cmd,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.STDOUT,
#             stdin=subprocess.DEVNULL,   # prevent accidental blocking on stdin
#             text=True,
#             bufsize=1
#         )
#         active_processes[job_id] = proc
#         for line in proc.stdout:
#             q.put(line.rstrip())
#         proc.wait()
#         q.put(f"__EXIT__{proc.returncode}")
#     except Exception as e:
#         q.put(f"[ERROR] {e}")
#         q.put("__EXIT__1")


# @app.route("/api/run/<tool>", methods=["POST"])
# def run_tool(tool):
#     data = request.json
#     job_id = tool

#     if job_id in active_processes:
#         proc = active_processes.get(job_id)
#         if proc and proc.poll() is None:
#             return jsonify({"error": "Job already running"}), 400

#     script_map = {
#         "scrape": "gmaps_scraper.py",
#         "email": "bulk_email.py",
#         "whatsapp": "bulk_whatsapp.py"
#     }

#     if tool not in script_map:
#         return jsonify({"error": "Unknown tool"}), 400

#     # For scraper: always save output to outputs/ dir with a safe filename
#     if tool == "scrape":
#         raw_name = data.get("output_file", "leads.csv")
#         # Strip any directory component the user may have typed
#         safe_name = os.path.basename(raw_name)
#         if not safe_name.lower().endswith(".csv"):
#             safe_name += ".csv"
#         output_path = os.path.join(OUTPUTS_DIR, safe_name)
#         data["output_file"] = output_path
#         job_output_files[job_id] = safe_name

#     # Reset WhatsApp ready event when a new WhatsApp job starts
#     if tool == "whatsapp":
#         _whatsapp_ready_event.clear()

#     script = os.path.join(SCRIPTS_DIR, script_map[tool])
#     cmd = [sys.executable, script, json.dumps(data)]

#     log_queues[job_id] = queue.Queue()
#     t = threading.Thread(target=stream_process, args=(job_id, cmd), daemon=True)
#     t.start()

#     return jsonify({"status": "started", "job_id": job_id})


# @app.route("/api/logs/<job_id>")
# def stream_logs(job_id):
#     def generate():
#         if job_id not in log_queues:
#             yield "data: [ERROR] No job found\n\n"
#             return
#         q = log_queues[job_id]
#         while True:
#             try:
#                 line = q.get(timeout=30)
#                 if line.startswith("__EXIT__"):
#                     code = line.replace("__EXIT__", "")
#                     # Tell the frontend whether there's a downloadable file
#                     output_file = job_output_files.get(job_id, "")
#                     yield f"data: __EXIT__{code}|{output_file}\n\n"
#                     break
#                 yield f"data: {line}\n\n"
#             except queue.Empty:
#                 yield "data: [PING]\n\n"

#     return Response(generate(), mimetype="text/event-stream",
#                     headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# @app.route("/api/stop/<job_id>", methods=["POST"])
# def stop_job(job_id):
#     proc = active_processes.get(job_id)
#     if proc and proc.poll() is None:
#         proc.terminate()
#         return jsonify({"status": "stopped"})
#     return jsonify({"status": "not running"})


# @app.route("/api/download/<filename>")
# def download_file(filename):
#     """Serve a CSV from the outputs directory as a file download."""
#     safe_name = os.path.basename(filename)
#     file_path = os.path.join(OUTPUTS_DIR, safe_name)
#     if not os.path.exists(file_path):
#         return jsonify({"error": "File not found"}), 404
#     return send_file(file_path, as_attachment=True, download_name=safe_name,
#                      mimetype="text/csv")


# @app.route("/api/preview/<filename>")
# def preview_file(filename):
#     """Return first 50 rows of a CSV as JSON for the frontend preview table."""
#     import csv
#     safe_name = os.path.basename(filename)
#     file_path = os.path.join(OUTPUTS_DIR, safe_name)
#     if not os.path.exists(file_path):
#         return jsonify({"error": "File not found"}), 404
#     rows = []
#     try:
#         with open(file_path, encoding="utf-8-sig") as f:
#             reader = csv.DictReader(f)
#             for i, row in enumerate(reader):
#                 if i >= 50:
#                     break
#                 rows.append(dict(row))
#         return jsonify({"rows": rows})
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


# @app.route("/api/whatsapp/ready", methods=["POST"])
# def whatsapp_ready():
#     """
#     Frontend calls this when the user clicks 'QR Scanned – Continue'.
#     Sets the threading.Event so the waiting /api/whatsapp/wait response unblocks.
#     """
#     _whatsapp_ready_event.set()
#     return jsonify({"status": "ok"})


# @app.route("/api/whatsapp/wait")
# def whatsapp_wait():
#     """
#     The bulk_whatsapp.py script calls this endpoint and blocks (via
#     threading.Event.wait) until the user confirms QR scan via /api/whatsapp/ready.
#     Uses a proper threading primitive instead of a busy-sleep loop, so it
#     doesn't consume a Flask thread spinning on time.sleep().
#     """
#     timeout = 300  # 5 minutes
#     confirmed = _whatsapp_ready_event.wait(timeout=timeout)
#     if confirmed:
#         return jsonify({"status": "ready"})
#     return jsonify({"status": "timeout"}), 408


# @app.route("/", defaults={"path": ""})
# @app.route("/<path:path>")
# def serve(path):
#     dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
#     if path and os.path.exists(os.path.join(dist, path)):
#         return send_from_directory(dist, path)
#     return send_from_directory(dist, "index.html")


# if __name__ == "__main__":
#     print(f"Loop Dashboard running at http://localhost:5000")
#     print(f"Outputs directory: {OUTPUTS_DIR}")
#     app.run(port=5000, debug=False, threaded=True)


from flask import Flask, request, jsonify, Response, send_from_directory, send_file
from flask_cors import CORS
import subprocess
import json
import os
import sys
import threading
import queue
import time

app = Flask(__name__, static_folder="frontend/dist", static_url_path="")
CORS(app)

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")

OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

active_processes = {}
log_queues = {}
job_output_files = {}

# ── WhatsApp QR signal ────────────────────────────────────────────────────────
# Use a run-ID so that stale /wait threads from old runs never steal the signal
# meant for the current run.
_wa_lock        = threading.Lock()
_wa_event       = threading.Event()   # set() when user clicks "QR Scanned"
_wa_current_run = 0                   # incremented on every new WA job start


def stream_process(job_id, cmd):
    q = log_queues[job_id]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1
        )
        active_processes[job_id] = proc
        for line in proc.stdout:
            q.put(line.rstrip())
        proc.wait()
        q.put(f"__EXIT__{proc.returncode}")
    except Exception as e:
        q.put(f"[ERROR] {e}")
        q.put("__EXIT__1")


@app.route("/api/run/<tool>", methods=["POST"])
def run_tool(tool):
    global _wa_current_run

    data = request.json
    job_id = tool

    if job_id in active_processes:
        proc = active_processes.get(job_id)
        if proc and proc.poll() is None:
            return jsonify({"error": "Job already running"}), 400

    script_map = {
        "scrape":    "gmaps_scraper.py",
        "email":     "bulk_email.py",
        "whatsapp":  "bulk_whatsapp.py"
    }

    if tool not in script_map:
        return jsonify({"error": "Unknown tool"}), 400

    if tool == "scrape":
        raw_name  = data.get("output_file", "leads.csv")
        safe_name = os.path.basename(raw_name)
        if not safe_name.lower().endswith(".csv"):
            safe_name += ".csv"
        output_path = os.path.join(OUTPUTS_DIR, safe_name)
        data["output_file"] = output_path
        job_output_files[job_id] = safe_name

    if tool == "whatsapp":
        with _wa_lock:
            # Bump the run-ID so any lingering old /wait thread
            # recognises it belongs to a dead run and exits cleanly.
            _wa_current_run += 1
            # Clear AFTER bumping so the old thread sees the new ID first.
            _wa_event.clear()

    script = os.path.join(SCRIPTS_DIR, script_map[tool])
    cmd    = [sys.executable, script, json.dumps(data)]

    log_queues[job_id] = queue.Queue()
    t = threading.Thread(target=stream_process, args=(job_id, cmd), daemon=True)
    t.start()

    return jsonify({"status": "started", "job_id": job_id})


@app.route("/api/logs/<job_id>")
def stream_logs(job_id):
    def generate():
        if job_id not in log_queues:
            yield "data: [ERROR] No job found\n\n"
            return
        q = log_queues[job_id]
        while True:
            try:
                line = q.get(timeout=30)
                if line.startswith("__EXIT__"):
                    code        = line.replace("__EXIT__", "")
                    output_file = job_output_files.get(job_id, "")
                    yield f"data: __EXIT__{code}|{output_file}\n\n"
                    break
                yield f"data: {line}\n\n"
            except queue.Empty:
                yield "data: [PING]\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/stop/<job_id>", methods=["POST"])
def stop_job(job_id):
    proc = active_processes.get(job_id)
    if proc and proc.poll() is None:
        proc.terminate()
        return jsonify({"status": "stopped"})
    return jsonify({"status": "not running"})


@app.route("/api/download/<filename>")
def download_file(filename):
    safe_name = os.path.basename(filename)
    file_path = os.path.join(OUTPUTS_DIR, safe_name)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(file_path, as_attachment=True, download_name=safe_name,
                     mimetype="text/csv")


@app.route("/api/preview/<filename>")
def preview_file(filename):
    import csv
    safe_name = os.path.basename(filename)
    file_path = os.path.join(OUTPUTS_DIR, safe_name)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    rows = []
    try:
        with open(file_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= 50:
                    break
                rows.append(dict(row))
        return jsonify({"rows": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/whatsapp/ready", methods=["POST"])
def whatsapp_ready():
    """
    Called when user clicks 'QR Scanned – Continue'.
    Sets the event so the active /wait thread unblocks.
    """
    _wa_event.set()
    return jsonify({"status": "ok"})


@app.route("/api/whatsapp/wait")
def whatsapp_wait():
    """
    bulk_whatsapp.py calls this and blocks until the user confirms QR scan.

    Key fix: we snapshot the run-ID at the start of this request.
    If a new WA job starts while we're waiting, _wa_current_run changes
    and we exit immediately — preventing the stale thread from stealing
    the signal meant for the new run.
    """
    with _wa_lock:
        my_run_id = _wa_current_run   # capture which run WE belong to

    POLL_INTERVAL = 0.5   # seconds between checks
    TIMEOUT       = 300   # 5 minutes total

    deadline = time.time() + TIMEOUT

    while time.time() < deadline:
        # Bail out if a newer run has started — we're a zombie thread
        with _wa_lock:
            if _wa_current_run != my_run_id:
                return jsonify({"status": "superseded"}), 409

        # Check if the user clicked the button
        if _wa_event.wait(timeout=POLL_INTERVAL):
            return jsonify({"status": "ready"})

    # Genuine timeout — nobody clicked within 5 minutes
    return jsonify({"status": "timeout"}), 408


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
    if path and os.path.exists(os.path.join(dist, path)):
        return send_from_directory(dist, path)
    return send_from_directory(dist, "index.html")


if __name__ == "__main__":
    print(f"Loop Dashboard running at http://localhost:5000")
    print(f"Outputs directory: {OUTPUTS_DIR}")
    app.run(port=5000, debug=False, threaded=True)