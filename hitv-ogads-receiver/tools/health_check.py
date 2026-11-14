"""Read-only public health/identity gate. Never sends callbacks or follows redirects."""
import argparse
import json
from pathlib import Path
import re
import urllib.request
import urllib.error

URL = "https://upxp.store/hitv-ogads/health.php"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate(status, content_type, body, expected):
    if status != 200:
        raise ValueError("HEALTH_HTTP_STATUS")
    if content_type.split(";")[0].strip().lower() != "application/json":
        raise ValueError("HEALTH_CONTENT_TYPE")
    if len(body) > 4096:
        raise ValueError("HEALTH_BODY_LIMIT")
    value = json.loads(body)
    if not isinstance(value, dict) or not (
        value.get("success") is True and value.get("service") == "HITV OGAds postback"
        and value.get("mode") == "disabled" and value.get("liveCampaigns") is False
        and value.get("conversionRecording") is False
    ):
        raise ValueError("DISABLED_HEALTH_CONTRACT_FAILED")
    build = {"version": expected["version"], "payloadSha256": expected["payloadSha256"]}
    if value.get("build") != build:
        raise ValueError("BUILD_IDENTITY_MISMATCH")
    return {"verified": True, "status": 200, "mode": "disabled", "build": build,
            "conversionRecorded": False, "callbackSent": False,
            "fullDeployedFileIdentityVerified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected = json.loads(args.receipt.read_text())
    if not re.fullmatch(r"[a-f0-9]{64}", expected["payloadSha256"]) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.\d+", expected["version"]):
        raise ValueError("INVALID_EXPECTED_IDENTITY")
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(urllib.request.Request(URL, headers={"Accept": "application/json", "Cache-Control": "no-cache"}), timeout=15) as response:
            result = validate(response.status, response.headers.get("Content-Type", ""), response.read(4097), expected)
    except (ValueError, OSError, urllib.error.HTTPError):
        # Response contents, redirects and environment values are intentionally not logged.
        result = {"verified": False, "error": "HEALTH_OR_BUILD_IDENTITY_CHECK_FAILED", "callbackSent": False}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    raise SystemExit(0 if result["verified"] else 1)


if __name__ == "__main__":
    main()
