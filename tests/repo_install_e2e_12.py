#!/usr/bin/env python3
"""Proves the GitHub plugin repository works end-to-end: a fresh AeonTV
10.10.7 server (no plugins) adds the repository, installs all five
plugins from it, restarts, and every plugin answers.

    python3 repo_install_e2e.py <published-server-dir> <port>

The sandbox intercepts TLS, so the server is launched with the egress
proxy + CA env (on a normal network GitHub is directly reachable and
none of that is needed).
"""
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import os
import signal

BASE = None
passed = failed = 0
failures = []
REPO_URL = "https://raw.githubusercontent.com/aeon01100101/aeontv-plugins/main/manifest.json"


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS {name}")
    else:
        failed += 1
        failures.append(name)
        print(f"FAIL {name} {detail}")


def req(method, path, token=None, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    auth = 'MediaBrowser Client="RepoTest", Device="Python", DeviceId="repo-1", Version="1.0"'
    if token:
        auth += f', Token="{token}"'
    r.add_header("Authorization", auth)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            content = resp.read()
            return resp.status, (json.loads(content) if content else None)
    except urllib.error.HTTPError as e:
        content = e.read()
        try:
            return e.code, json.loads(content) if content else None
        except Exception:
            return e.code, None
    except urllib.error.URLError:
        return 0, None


def wait_ready(timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        code, _ = req("GET", "/System/Info/Public")
        if code == 200:
            code2, _ = req("GET", "/Startup/User")
            if code2 == 200:
                return True
        time.sleep(1)
    return False


def start_server(server_dir, tmp):
    ff = os.path.join(server_dir, "ffmpeg", "ffmpeg")
    cmd = [os.path.join(server_dir, "jellyfin"),
           "--datadir", os.path.join(tmp, "data"),
           "--configdir", os.path.join(tmp, "config"),
           "--cachedir", os.path.join(tmp, "cache"),
           "--logdir", os.path.join(tmp, "log"),
           "--ffmpeg", ff if os.path.exists(ff) else "/usr/bin/ffmpeg",
           "--webdir", os.path.join(server_dir, "jellyfin-web")]
    env = dict(os.environ)
    env["http_proxy"] = env["https_proxy"] = "http://127.0.0.1:3129"
    env["HTTP_PROXY"] = env["HTTPS_PROXY"] = "http://127.0.0.1:3129"
    env["SSL_CERT_FILE"] = "/run/hatch/egress-tls/hatch-egress-ca.pem"
    log = open(os.path.join(tmp, "server.out"), "ab")
    return subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                            preexec_fn=os.setsid, env=env)


def stop_server(proc):
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=15)
    except Exception:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass


def main():
    global BASE
    server_dir, port = sys.argv[1], sys.argv[2]
    BASE = f"http://127.0.0.1:{port}"
    tmp = os.path.expanduser("~/workspace/tmp/repo-e2e")
    subprocess.run(["rm", "-rf", tmp])
    os.makedirs(tmp, exist_ok=True)

    proc = start_server(server_dir, tmp)
    try:
        check("server becomes ready", wait_ready())
        req("POST", "/Startup/Configuration", body={"UICulture": "en-US", "MetadataCountryCode": "US", "PreferredMetadataLanguage": "en"})
        req("GET", "/Startup/User")
        req("POST", "/Startup/User", body={"Name": "Admin", "Password": "adminpw"})
        req("POST", "/Startup/Complete")
        s, auth = req("POST", "/Users/AuthenticateByName", body={"Username": "Admin", "Pw": "adminpw"})
        check("admin login", s == 200, f"-> {s}")
        token = auth["AccessToken"]

        s, plugins = req("GET", "/Plugins", token=token)
        pname = lambda p: p.get("name", p.get("Name"))
        ours = [p for p in plugins if pname(p) in
                ("Bandwidth Tracker", "Aeon Profiles", "Aeon Home", "Aeon Identify", "AeonPS1")]
        check("no Aeon plugins preinstalled", len(ours) == 0, f"-> {[pname(p) for p in ours]}")

        s, _ = req("POST", "/Repositories", token=token,
                   body=[{"Name": "AeonTV Plugins", "Url": REPO_URL, "Enabled": True}])
        check("repository added", s in (200, 204), f"-> {s}")

        s, packages = req("GET", "/Packages", token=token)
        names = sorted(p.get("name", p.get("Name", "?")) for p in (packages or []))
        expected = ["Aeon Home", "Aeon Identify", "Aeon Profiles", "AeonPS1", "Bandwidth Tracker"]
        check("catalog lists all 5 plugins", all(e in names for e in expected), f"-> {names}")

        for name in expected:
            s, _ = req("POST", f"/Packages/Installed/{urllib.parse.quote(name)}", token=token)
            check(f"install {name} from repository", s in (200, 204), f"-> {s}")

        plugins_dir = os.path.join(tmp, "data", "plugins")
        landed = sorted(d for d in os.listdir(plugins_dir)
                        if "_" in d) if os.path.isdir(plugins_dir) else []
        check("5 plugin folders landed on disk", len(landed) == 5, f"-> {landed}")
    finally:
        stop_server(proc)

    # restart: plugins must load and answer
    proc = start_server(server_dir, tmp)
    try:
        check("server restarts with plugins", wait_ready())
        s, auth = req("POST", "/Users/AuthenticateByName", body={"Username": "Admin", "Pw": "adminpw"})
        token = auth["AccessToken"]
        # plugin statuses settle a few seconds after the API first answers;
        # poll briefly until all five report Active (or use the last fetch)
        plugins = []
        for _ in range(15):
            s, plugins = req("GET", "/Plugins", token=token)
            settled = {(p.get("name") or p.get("Name")): (p.get("status") or p.get("Status")) for p in plugins}
            if all(settled.get(n) == "Active" for n in
                   ("Bandwidth Tracker", "Aeon Profiles", "Aeon Home", "Aeon Identify", "AeonPS1")):
                break
            time.sleep(2)
        active = {(p.get("name") or p.get("Name")): (p.get("status") or p.get("Status")) for p in plugins}
        versions = {(p.get("name") or p.get("Name")): (p.get("version") or p.get("Version")) for p in plugins}
        expected_versions = {"Bandwidth Tracker": "1.1.0.0", "Aeon Profiles": "1.2.0.0",
                               "Aeon Home": "1.1.1.0", "Aeon Identify": "1.1.0.0", "AeonPS1": "1.1.0.0"}
        for name in ["Bandwidth Tracker", "Aeon Profiles", "Aeon Home", "Aeon Identify", "AeonPS1"]:
            check(f"{name} active after restart", active.get(name) == "Active", f"-> {active.get(name)}")
            check(f"{name} is the 12.x build ({expected_versions[name]})",
                  str(versions.get(name)) == expected_versions[name], f"-> {versions.get(name)}")

        for label, path in [
            ("Bandwidth API", "/Bandwidth/Summary"),
            ("Profiles API", "/Profiles/MyFamily"),
            ("Home API", "/Home/ForYou"),
            ("Identify API", "/Identify/Inbox"),
            ("AeonPS1 API", "/PS1/Games"),
        ]:
            s, _ = req("GET", path, token=token)
            check(f"{label} answers (200)", s == 200, f"-> {s}")
    finally:
        stop_server(proc)

    print(f"\n{passed} passed, {failed} failed")
    if failures:
        print("FAILURES:", failures)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
