"""Accept a successful default-branch build from this repository before fetching it."""
import json
import os
import re
import urllib.request
from health_check import NoRedirect


def validate_run(run, repo, branch, run_id):
    if not (
        str(run.get("id")) == run_id
        and run.get("repository", {}).get("full_name") == repo
        and run.get("head_branch") == branch
        and run.get("path") == ".github/workflows/verify.yml"
        and run.get("event") in ["push", "workflow_dispatch"]
        and run.get("status") == "completed" and run.get("conclusion") == "success"
        and re.fullmatch(r"[a-f0-9]{40}", run.get("head_sha", ""))
    ):
        raise ValueError("UNAPPROVED_BUILD_RUN")
    return {"accepted": True, "runId": run_id, "commit": run["head_sha"]}


def main():
    repo, branch, run_id = (os.environ[k] for k in ["GITHUB_REPOSITORY", "DEFAULT_BRANCH", "BUILD_RUN_ID"])
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or not re.fullmatch(r"[1-9][0-9]{0,17}", run_id):
        raise ValueError("INVALID_RUN_INPUT")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/runs/{run_id}",
        headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"], "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=15) as response:
            run = json.loads(response.read(1024 * 1024))
        print(json.dumps(validate_run(run, repo, branch, run_id)))
    except Exception:
        raise SystemExit("BUILD_RUN_VERIFICATION_FAILED")


if __name__ == "__main__":
    main()
