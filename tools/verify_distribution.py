"""Exercise an installed wheel or container without providers or existing user data.

All logs and fingerprints stay in a new private output directory. Only a reduced
report is printed. Docker resources are unique and removed on exit; native data
and the clean virtual environment are retained for diagnosis.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler
import venv


# Authored inspection code, never supplied by an agent. The installed package
# validates the schema before fixed internal table names are used in SQL.
SNAPSHOT = '''
import hashlib, json, sys
from contextlib import closing
from hidden_lab.migrations import EXPECTED_TABLES, check_database, connect_existing
status = check_database(sys.argv[1])
with closing(connect_existing(sys.argv[1])) as db:
    db.execute("BEGIN")
    rows = {name: sorted(db.execute('SELECT * FROM "' + name + '"').fetchall(), key=repr)
            for name in sorted(EXPECTED_TABLES)}
    result = {"schema_version": status["schema_version"],
              "counts": {name: len(values) for name, values in rows.items()},
              "fingerprint": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
              "sessions": [row[0] for row in db.execute("SELECT session_id FROM arena_trials ORDER BY session_id")]}
print(json.dumps(result))
'''

INSTALLATION = '''
import importlib.util, json, sys
from pathlib import Path
import hidden_lab
assert Path(hidden_lab.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert all(importlib.util.find_spec(name) is None for name in ("openai", "anthropic"))
try:
    gemini = importlib.util.find_spec("google.genai")
except ModuleNotFoundError:
    gemini = None
assert gemini is None
print(json.dumps({"version": hidden_lab.__version__, "installed_outside_checkout": True, "provider_sdks_absent": True}))
'''


def clean_environment():
    env = dict(os.environ)
    for key in list(env):
        if key.upper() in {"PYTHONPATH", "PYTHONHOME", "ZONE_OPERATOR_TOKEN", "ZONE_ENV"} or key.upper().endswith(("API_KEY", "API_TOKEN")):
            env.pop(key)
    env.update(MPLBACKEND="Agg", ZONE_ENV="local", PYTHONDONTWRITEBYTECODE="1")
    return env


def new_output(path):
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=False, mode=0o700)
    return path


def public_report(mode, installation, initial):
    # Deliberate allowlist: no fingerprint, session IDs, token or world content.
    return {"verification_version": 1, "mode": mode,
            "zone_version": installation["version"], "provider_sdks_absent": installation["provider_sdks_absent"],
            "schema_version": initial["schema_version"], "table_counts": initial["counts"],
            "restart_equal": True, "live_backup_restore_equal": True, "api_replay_equal": True,
            "real_provider_calls": 0}


def http_read(port, path, token=None):
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("Local absolute route required")
    headers = {"X-Zone-Arena-Version": "1"}
    if token is not None:
        headers["X-Zone-Token"] = token
    # Ignore ambient HTTP proxies: the verifier must only contact its own server.
    opener = build_opener(ProxyHandler({}))
    request = Request(f"http://127.0.0.1:{port}{path}", headers=headers)
    try:
        with opener.open(request, timeout=3) as response:
            return response.status, response.headers, response.read()
    except HTTPError as error:
        return error.code, error.headers, error.read()


def available_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Verification:
    def __init__(self, args):
        self.args = args
        self.out = new_output(args.out)
        self.env = clean_environment()
        self.env["MPLCONFIGDIR"] = str(self.out / "mpl-cache")
        self.env["ZONE_OPERATOR_TOKEN"] = secrets.token_urlsafe(32)
        self.port = available_port()
        self.process = None
        self.server_log = None
        self.container_created = False
        self.volume_created = False
        suffix = secrets.token_hex(8)
        self.container = "zone-verify-" + suffix
        self.volume = "zone-verify-" + suffix
        self.counter = 0

    def run(self, command, *, timeout=300):
        self.counter += 1
        result = subprocess.run(command, cwd=self.out, env=self.env, capture_output=True, timeout=timeout)
        log = self.out / f"command-{self.counter:03d}.log"
        log.write_bytes(result.stdout + result.stderr)
        log.chmod(0o600)
        if result.returncode:
            raise RuntimeError(f"Verification command failed; see private log {log.name}")
        return result.stdout.decode("utf-8")

    def prepare(self):
        if self.args.mode == "wheel":
            target = self.out / "venv"
            venv.EnvBuilder(with_pip=True).create(target)
            self.python = str(target / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
            self.run([self.python, "-m", "pip", "install", "--disable-pip-version-check", "-c",
                      str(self.args.constraints.resolve()), str(self.args.wheel.resolve()) + "[backend]"])
            installation = json.loads(self.run([self.python, "-c", INSTALLATION]))
            self.root = str(self.out / "demo")
        else:
            self.run(["docker", "volume", "create", self.volume])
            self.volume_created = True
            # Runtime package is installed, even though image also has its source.
            installation = json.loads(self.run(["docker", "run", "--rm", "--workdir", "/tmp",
                "--entrypoint", "python", self.args.image, "-c", INSTALLATION]))
            self.root = "/data/demo"
        self.lab("ops", "demo", "--out", self.root)
        return installation

    def lab(self, *arguments):
        if self.args.mode == "wheel":
            return self.run([self.python, "-m", "hidden_lab", *arguments])
        return self.run(["docker", "run", "--rm", "-v", self.volume + ":/data", self.args.image, *arguments])

    def snapshot(self, database):
        if self.args.mode == "wheel":
            command = [self.python, "-c", SNAPSHOT, database]
        else:
            command = ["docker", "run", "--rm", "-v", self.volume + ":/data", "--entrypoint", "python",
                       self.args.image, "-c", SNAPSHOT, database]
        return json.loads(self.run(command))

    def start(self, database):
        if self.args.mode == "wheel":
            command = [self.python, "-m", "hidden_lab", "serve", "--db", database, "--port", str(self.port)]
            if self.args.web_dir:
                command += ["--web-dir", str(self.args.web_dir.resolve())]
            self.server_log = (self.out / "server.log").open("ab")
            self.process = subprocess.Popen(command, cwd=self.out, env=self.env, stdout=self.server_log, stderr=subprocess.STDOUT)
        else:
            self.run(["docker", "run", "-d", "--name", self.container, "--read-only", "--tmpfs", "/tmp",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "-e", "ZONE_OPERATOR_TOKEN",
                "-v", self.volume + ":/data", "-p", f"127.0.0.1:{self.port}:8765", self.args.image,
                "serve", "--db", database, "--host", "0.0.0.0", "--container-local", "--web-dir", "/app/web"])
            self.container_created = True
        deadline = time.monotonic() + 75
        while time.monotonic() < deadline:
            try:
                if http_read(self.port, "/health/ready")[0] == 200:
                    if self.args.mode == "wheel":
                        return
                    state = json.loads(self.run(["docker", "inspect", self.container]))[0]
                    if state["State"]["Health"]["Status"] == "healthy":
                        assert state["Config"]["User"] == "10001:10001"
                        assert state["HostConfig"]["ReadonlyRootfs"]
                        return
            except (URLError, TimeoutError, ConnectionError):
                pass
            if self.process and self.process.poll() is not None:
                raise RuntimeError("Server exited; see private server.log")
            time.sleep(0.5)
        raise RuntimeError("Readiness/healthy timeout")

    def stop(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
            self.process = None
        if self.server_log:
            self.server_log.close()
            self.server_log = None
        if self.container_created:
            self.run(["docker", "logs", self.container])
            self.run(["docker", "rm", "--force", self.container])
            self.container_created = False

    def api_snapshot(self, initial):
        for route in ("/health/live", "/health/ready", "/v1/worlds", "/v1/modes"):
            status, headers, _ = http_read(self.port, route)
            assert status == 200, route
            assert headers["X-Content-Type-Options"] == "nosniff"
            assert "no-store" in headers["Cache-Control"]
        if self.args.mode == "docker" or self.args.web_dir:
            status, headers, body = http_read(self.port, "/")
            assert status == 200 and b"<!doctype html>" in body.lower()
            assert "Content-Security-Policy" in headers
        for route in ("/private/pack.json", "/arena.sqlite3", "/.env", "/pyproject.toml"):
            assert http_read(self.port, route)[0] == 404
        token = self.env["ZONE_OPERATOR_TOKEN"]
        sessions = []
        assert initial["sessions"], "Demo must include an Arena session"
        for session in initial["sessions"]:
            route = "/v1/arena/sessions/" + session
            assert http_read(self.port, route)[0] == 401
            status, _, body = http_read(self.port, route, token)
            assert status == 200
            sessions.append(json.loads(body))
        return sessions

    def verify(self):
        installation = self.prepare()
        database = self.root + "/arena.sqlite3"
        self.start(database)
        initial = self.snapshot(database)
        api = self.api_snapshot(initial)
        assert self.snapshot(database) == initial, "Read checks changed persisted state"
        self.stop()
        self.start(database)
        assert self.api_snapshot(initial) == api, "Restart changed replay"
        assert self.snapshot(database) == initial, "Restart changed database rows"
        backup, restored = self.root + "/live.sqlite3", self.root + "/live-restored.sqlite3"
        self.lab("ops", "backup", "--db", database, "--out", backup)
        self.stop()
        self.lab("ops", "restore", "--backup", backup, "--out", restored)
        self.lab("ops", "check", "--db", restored)
        assert self.snapshot(restored) == initial, "Restore changed database rows"
        self.start(restored)
        assert self.api_snapshot(initial) == api, "Restore changed replay"
        assert self.snapshot(restored) == initial
        return public_report(self.args.mode, installation, initial)

    def cleanup(self):
        try:
            self.stop()
        finally:
            if self.volume_created:
                self.run(["docker", "volume", "rm", self.volume])
                self.volume_created = False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("wheel", "docker"), required=True)
    parser.add_argument("--out", type=Path, required=True, help="New private directory, e.g. benchmark_data/distribution-01")
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--constraints", type=Path, default=Path("constraints-ci.txt"))
    parser.add_argument("--web-dir", type=Path)
    parser.add_argument("--image", default="zone:ci")
    args = parser.parse_args()
    if args.mode == "wheel" and (not args.wheel or not args.wheel.is_file() or not args.constraints.is_file()):
        parser.error("wheel mode requires an existing wheel and constraints")
    verifier = Verification(args)
    try:
        report = verifier.verify()
    finally:
        verifier.cleanup()
    (verifier.out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
