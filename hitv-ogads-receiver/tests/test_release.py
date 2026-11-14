from pathlib import Path
from zipfile import ZipFile, ZIP_STORED
import io
import json
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import release
import health_check
from check_ci_run import validate_run


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw, cls.receipt = release.build_bytes()

    def test_deterministic_build(self):
        self.assertEqual((self.raw, self.receipt), release.build_bytes())

    def test_manifest_and_allowlist(self):
        self.assertEqual(set(release.verify_bytes(self.raw, self.receipt)), release.DEPLOY_FILES)

    def test_raw_corruption(self):
        with self.assertRaises(ValueError):
            release.verify_bytes(self.raw[:-1] + b"x", self.receipt)

    def mutated(self, extra=None, change=None):
        with ZipFile(io.BytesIO(self.raw)) as old:
            files = {n: old.read(n) for n in old.namelist()}
        if extra:
            files[extra] = b"unexpected"
        if change:
            files[change] += b"\nchanged\n"
        buf = io.BytesIO()
        with ZipFile(buf, "w", ZIP_STORED) as new:
            for name, data in files.items():
                new.writestr(name, data)
        receipt = dict(self.receipt, zipSha256=release.sha(buf.getvalue()))
        return buf.getvalue(), receipt

    def test_unlisted_secret_file(self):
        with self.assertRaises(ValueError):
            release.verify_bytes(*self.mutated(extra="hitv-ogads/.env"))

    def test_zip_slip(self):
        with self.assertRaises(ValueError):
            release.verify_bytes(*self.mutated(extra="../outside.php"))

    def test_file_tamper_despite_new_zip_checksum(self):
        with self.assertRaises(ValueError):
            release.verify_bytes(*self.mutated(change="hitv-ogads/health.php"))

    def test_manifest_tamper(self):
        with self.assertRaises(ValueError):
            release.verify_bytes(*self.mutated(change="hitv-ogads/package-manifest.json"))

    def test_receipt_disabled_guard(self):
        with self.assertRaises(ValueError):
            release.verify_bytes(self.raw, dict(self.receipt, liveEnabled=True))


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.expected = {"version": "2026-11-14.3", "payloadSha256": "a"*64}
        self.body = {"success": True, "service": "HITV OGAds postback", "mode": "disabled",
                     "liveCampaigns": False, "conversionRecording": False, "build": dict(self.expected)}

    def validate(self, body=None, status=200, content_type="application/json"):
        return health_check.validate(status, content_type, json.dumps(self.body if body is None else body).encode(), self.expected)

    def test_exact_disabled_identity(self):
        self.assertTrue(self.validate()["verified"])
        self.assertFalse(self.validate()["fullDeployedFileIdentityVerified"])

    def test_enabled_campaigns_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(dict(self.body, liveCampaigns=True))

    def test_conversion_recording_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(dict(self.body, conversionRecording=True))

    def test_boolean_type_confusion(self):
        with self.assertRaises(ValueError):
            self.validate(dict(self.body, conversionRecording=0))

    def test_old_healthy_build_rejected(self):
        body = dict(self.body);body.pop("build")
        with self.assertRaises(ValueError):
            self.validate(body)

    def test_wrong_identity(self):
        with self.assertRaises(ValueError):
            self.validate(dict(self.body, build={"version": "old", "payloadSha256": "a"*64}))

    def test_wrong_payload(self):
        with self.assertRaises(ValueError):
            self.validate(dict(self.body, build=dict(self.expected, payloadSha256="b"*64)))

    def test_redirect_status_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(status=302)
        self.assertIsNone(health_check.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example"))

    def test_html_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(content_type="text/html")

    def test_oversize_rejected(self):
        with self.assertRaises(ValueError):
            health_check.validate(200, "application/json", b" " * 4097, self.expected)

    def test_non_object_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(body=[])


class RunGateTests(unittest.TestCase):
    def setUp(self):
        self.run = {"id": 123, "repository": {"full_name": "owner/receiver"}, "head_branch": "main",
                    "path": ".github/workflows/verify.yml", "event": "push", "status": "completed",
                    "conclusion": "success", "head_sha": "a"*40}

    def validate(self, **changes):
        return validate_run(dict(self.run, **changes), "owner/receiver", "main", "123")

    def test_valid_run(self):
        self.assertTrue(self.validate()["accepted"])

    def test_pull_request_not_release(self):
        with self.assertRaises(ValueError):
            self.validate(event="pull_request")

    def test_wrong_repository(self):
        with self.assertRaises(ValueError):
            self.validate(repository={"full_name": "another/receiver"})

    def test_failed_run(self):
        with self.assertRaises(ValueError):
            self.validate(conclusion="failure")

    def test_nondefault_branch(self):
        with self.assertRaises(ValueError):
            self.validate(head_branch="experiment")

    def test_other_workflow(self):
        with self.assertRaises(ValueError):
            self.validate(path=".github/workflows/unrelated.yml")


if __name__ == "__main__":
    unittest.main()
