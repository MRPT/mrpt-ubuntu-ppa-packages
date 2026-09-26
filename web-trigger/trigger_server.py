#!/usr/bin/env python3
"""Tiny local HTTP server to manually trigger run_mrpt-develop.sh / run_mrpt-master.sh
on demand, instead of waiting for their next cron slot.

Runs as the mrptppa user (same user/env as cron), bound to 127.0.0.1 only.
Apache is expected to reverse-proxy a Basic-Auth-protected path to this
server; this process does no authentication of its own. See README.md.
"""
import html
import os
import subprocess
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOME = os.path.expanduser("~")
LOG_DIR = os.path.join(HOME, "web-trigger", "logs")
KEEP_LOGS_PER_JOB = 15
BIND_ADDR = ("127.0.0.1", 8765)

JOBS = {
    "develop": {
        "label": "develop → mrpt3-develop PPA",
        "script": os.path.join(HOME, "cron", "run_mrpt-develop.sh"),
        "lockfile": os.path.join(HOME, ".mrptppa.lock"),
        "sha_cache": os.path.join(HOME, ".mrptppa.sha"),
    },
    "master": {
        "label": "master → mrpt3-stable PPA",
        "script": os.path.join(HOME, "cron", "run_mrpt-master.sh"),
        "lockfile": os.path.join(HOME, ".mrpt-master-ppa.lock"),
        "sha_cache": os.path.join(HOME, ".mrpt-master-ppa.sha"),
    },
}

STATE_LOCK = threading.Lock()
# job -> {"proc": Popen, "logfile": path, "started": float}
RUNNING = {}


def lock_is_active(lockfile):
    if not os.path.exists(lockfile):
        return False
    return (time.time() - os.path.getmtime(lockfile)) < 7200


def latest_log(job):
    try:
        files = sorted(
            (f for f in os.listdir(LOG_DIR) if f.startswith(job + "-") and f.endswith(".log")),
            reverse=True,
        )
    except FileNotFoundError:
        return None
    return files[0] if files else None


def prune_old_logs(job):
    files = sorted(f for f in os.listdir(LOG_DIR) if f.startswith(job + "-") and f.endswith(".log"))
    excess = len(files) - KEEP_LOGS_PER_JOB
    for f in files[:max(excess, 0)]:
        for suffix in ("", ".exit"):
            path = os.path.join(LOG_DIR, f + suffix) if suffix else os.path.join(LOG_DIR, f)
            try:
                os.remove(path)
            except FileNotFoundError:
                pass


def start_job(job):
    cfg = JOBS[job]
    os.makedirs(LOG_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    logname = f"{job}-{stamp}.log"
    logpath = os.path.join(LOG_DIR, logname)

    logfh = open(logpath, "wb", buffering=0)
    proc = subprocess.Popen(
        [cfg["script"]],
        stdout=logfh,
        stderr=subprocess.STDOUT,
        cwd=HOME,
        close_fds=True,
    )

    def reap():
        returncode = proc.wait()
        logfh.close()
        with open(logpath + ".exit", "w") as f:
            f.write(f"{returncode} {datetime.now().isoformat(timespec='seconds')}\n")
        with STATE_LOCK:
            RUNNING.pop(job, None)
        prune_old_logs(job)

    threading.Thread(target=reap, daemon=True).start()
    with STATE_LOCK:
        RUNNING[job] = {"proc": proc, "logfile": logname, "started": time.time()}
    return logname


def job_status_html(job):
    cfg = JOBS[job]
    running = lock_is_active(cfg["lockfile"])
    logname = latest_log(job)
    last_built_sha = ""
    if os.path.exists(cfg["sha_cache"]):
        with open(cfg["sha_cache"]) as f:
            last_built_sha = f.read().strip()

    status_line = '<span class="run">RUNNING</span>' if running else '<span class="idle">idle</span>'
    if logname:
        exitfile = os.path.join(LOG_DIR, logname + ".exit")
        if not running and os.path.exists(exitfile):
            with open(exitfile) as f:
                code, _, ts = f.read().strip().partition(" ")
            css = "ok" if code == "0" else "fail"
            status_line += f' &mdash; last run exit code <span class="{css}">{html.escape(code)}</span> ({html.escape(ts)})'
        log_link = f'<a href="/log?job={job}&file={html.escape(logname)}">view latest log</a>'
    else:
        log_link = "(no log yet)"

    disabled = "disabled" if running else ""
    return f"""
    <div class="job">
      <h2>{html.escape(cfg['label'])}</h2>
      <p>Status: {status_line}</p>
      <p>Last commit actually built: <code>{html.escape(last_built_sha) or '(none yet)'}</code></p>
      <form method="post" action="/trigger">
        <input type="hidden" name="job" value="{job}">
        <button type="submit" {disabled}>Trigger now</button>
      </form>
      <p>{log_link}</p>
    </div>
    """


PAGE_STYLE = """
<style>
body { font-family: sans-serif; max-width: 60em; margin: 2em auto; padding: 0 1em; }
.job { border: 1px solid #ccc; border-radius: 6px; padding: 1em; margin-bottom: 1em; }
.run { color: #b8860b; font-weight: bold; }
.idle { color: #666; }
.ok { color: #2e7d32; font-weight: bold; }
.fail { color: #c62828; font-weight: bold; }
pre { background: #111; color: #eee; padding: 1em; overflow-x: auto; white-space: pre-wrap; }
button { padding: 0.4em 1em; }
</style>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "mrpt-trigger/1.0"

    def log_message(self, fmt, *args):
        pass  # Apache already logs the proxied requests; keep stdout for the app's own diagnostics only.

    def _send_html(self, body, code=200):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = "<html><head><title>MRPT PPA trigger</title>" + PAGE_STYLE + "</head><body>"
            body += "<h1>MRPT PPA manual trigger</h1>"
            for job in JOBS:
                body += job_status_html(job)
            body += "</body></html>"
            self._send_html(body)
        elif parsed.path == "/log":
            qs = parse_qs(parsed.query)
            job = qs.get("job", [""])[0]
            fname = qs.get("file", [""])[0]
            if job not in JOBS or not fname or "/" in fname or not fname.startswith(job + "-"):
                self._send_html("<h1>Not found</h1>", code=404)
                return
            logpath = os.path.join(LOG_DIR, fname)
            if not os.path.isfile(logpath):
                self._send_html("<h1>Not found</h1>", code=404)
                return
            with open(logpath, "rb") as f:
                content = f.read().decode("utf-8", errors="replace")
            running = lock_is_active(JOBS[job]["lockfile"])
            refresh = '<meta http-equiv="refresh" content="3">' if running else ""
            status = '<span class="run">still running…</span>' if running else "<span class=\"ok\">finished</span>"
            body = f"<html><head><title>{html.escape(fname)}</title>{refresh}{PAGE_STYLE}</head><body>"
            body += f'<p><a href="/">&larr; back</a> &mdash; {html.escape(fname)} &mdash; {status}</p>'
            body += f"<pre>{html.escape(content)}</pre>"
            body += "</body></html>"
            self._send_html(body)
        else:
            self._send_html("<h1>Not found</h1>", code=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/trigger":
            self._send_html("<h1>Not found</h1>", code=404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        job = parse_qs(body).get("job", [""])[0]
        if job not in JOBS:
            self._send_html("<h1>Unknown job</h1>", code=400)
            return

        with STATE_LOCK:
            already = job in RUNNING and RUNNING[job]["proc"].poll() is None
            if already:
                logname = RUNNING[job]["logfile"]
            else:
                logname = None
        if logname is None and lock_is_active(JOBS[job]["lockfile"]):
            # Cron picked it up concurrently: don't spawn a second instance,
            # just point at whatever log already exists.
            logname = latest_log(job)
        if logname is None:
            logname = start_job(job)

        self.send_response(303)
        self.send_header("Location", f"/log?job={job}&file={logname}")
        self.end_headers()


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    server = ThreadingHTTPServer(BIND_ADDR, Handler)
    print(f"Listening on {BIND_ADDR[0]}:{BIND_ADDR[1]} (proxy this from Apache; do not expose directly)")
    server.serve_forever()


if __name__ == "__main__":
    main()
