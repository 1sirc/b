"""Reuse receiver regressions against extracted deployment bytes."""
from pathlib import Path
import json
import socket
import subprocess
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]


def verify_package(package, php, evidence, receipt):
    evidence.mkdir(parents=True)

    def run(*args):
        result = subprocess.run([php, "-n", *map(str, args)], capture_output=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError("PHP_CHECK_FAILED: " + (result.stdout + result.stderr).decode(errors="replace"))
        return result.stdout

    version = run("-r", "echo PHP_VERSION;").decode()
    if tuple(map(int, version.split(".")[:2])) < (8, 2):
        raise ValueError("PHP_82_REQUIRED")
    lint = [str(p.relative_to(package)) for p in package.rglob("*.php") if run("-l", p)]
    raw = run(ROOT / "tests/checks.php", package)
    (evidence / "php-checks.log").write_bytes(raw)
    fixture = json.loads(raw.splitlines()[-1])
    entries = []
    for base in ["", "/hitv-ogads"]:
        for entry, method, alias, expected in [
            ("health", "GET", "direct", 200), ("health", "HEAD", "direct", 200),
            ("postback", "GET", "direct", 503), ("postback", "GET", "alias", 503),
        ]:
            actual = json.loads(run(ROOT / "tests/entry-check.php", package, base, entry, method, alias))
            assert actual["status"] == expected
            if method == "HEAD":
                assert actual["body"] is None and actual["outputBytes"] == 0
            elif entry == "health":
                assert actual["body"]["build"] == {"version": receipt["version"], "payloadSha256": receipt["payloadSha256"]}
                assert actual["body"]["conversionRecording"] is False
            else:
                assert actual["body"]["error"] == "OGADS_ACTIVATION_INCOMPLETE"
                assert actual["body"]["conversionRecorded"] is False
            entries.append({"mount": base or "/", "entry": entry, "method": method, "alias": alias, **actual})
    (evidence / "entry-fixtures.json").write_text(json.dumps(entries, indent=2) + "\n")

    observations = []
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for base, docroot in [("", package), ("/hitv-ogads", package.parent)]:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        with (evidence / ("http-root.log" if not base else "http-subdirectory.log")).open("wb") as log:
            proc = subprocess.Popen(
                [php, "-n", "-S", f"127.0.0.1:{port}", "-t", str(docroot)],
                stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            def request(path, expected, method="GET", headers=None):
                req = urllib.request.Request(f"http://127.0.0.1:{port}"+base+path, method=method,
                    headers={"Host": "upxp.store", **(headers or {})})
                try:
                    response = opener.open(req, timeout=8)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    status, body, h = response.code, response.read(8192), response.headers
                assert status == expected, (path, status, expected)
                assert not any(s in body for s in [b"<?php", b"Fatal error", b"Stack trace", b"/home/onekfuxn"])
                observations.append({"mount": base or "/", "path": path.split("?")[0], "status": status, "method": method})
                return body, h
            try:
                for _ in range(40):
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=.2):
                            break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise RuntimeError("LOCAL_PHP_START_FAILED")
                body, h = request("/health.php", 426)
                assert json.loads(body)["error"] == "HTTPS_REQUIRED"
                assert h["Cache-Control"] == "no-store" and h["X-Content-Type-Options"] == "nosniff"
                dummy = "offer_id=910001&aff_sub4=" + "0"*32 + "&ip=192.0.2.20"
                body, _ = request("/postback.php?" + dummy, 426)
                assert json.loads(body)["conversionRecorded"] is False
                request("/postback.php?" + dummy, 426, headers={"X-Forwarded-Proto": "https", "X-Forwarded-For": "198.51.100.7"})
                _, h = request("/postback.php", 405, method="POST")
                assert h["Allow"] == "GET"
                request("/postback.php", 403, headers={"Host": "attacker.example"})
                for source in ["Receiver.php", "Kernel.php", "bootstrap.php", "BuildInfo.php"]:
                    body, _ = request("/src/" + source, 404)
                    assert body == b""
                request("/postback.php/extra", 404)
                body, _ = request("/health.php", 426, method="HEAD")
                assert body == b""
            finally:
                proc.terminate()
                proc.wait(timeout=15)
    (evidence / "http-observations.json").write_text(json.dumps(observations, indent=2) + "\n")
    run("-l", ROOT / "tools/verify-deployed.php")
    deployed = json.loads(run(ROOT / "tools/verify-deployed.php", package, receipt["manifestSha256"]))
    assert deployed["verified"] is True and deployed["payloadSha256"] == receipt["payloadSha256"]
    # Test tampering in these known temporary fixture files, then restore exact bytes.
    original = (package / "health.php").read_bytes()
    try:
        (package / "health.php").write_bytes(original + b"\n// altered fixture\n")
        result = subprocess.run([php, "-n", str(ROOT / "tools/verify-deployed.php"), str(package), receipt["manifestSha256"]], capture_output=True)
        assert result.returncode != 0 and b'"verified":false' in result.stdout
    finally:
        (package / "health.php").write_bytes(original)
    wrong = subprocess.run([php, "-n", str(ROOT / "tools/verify-deployed.php"), str(package), "0"*64], capture_output=True)
    assert wrong.returncode != 0
    return {"phpVersion": version, "phpAssertions": fixture, "entryFixtures": len(entries),
            "loopbackHttpChecks": len(observations), "deploymentIdentityChecks": 3,
            "deployedPhpLint": len(lint), "runtimeWrites": False,
            "externalRequests": 0, "apacheOrLiteSpeedTested": False, "actualTlsTested": False}
