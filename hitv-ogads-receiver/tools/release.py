"""Build one deterministic disabled receiver ZIP, then test its extracted bytes."""
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_STORED
import argparse
import hashlib
import io
import json
import re
import stat
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = {
    ".htaccess", ".user.ini", "README.md", "health.php", "postback.php",
    "config/.htaccess", "config/receiver.example.php",
    "src/.htaccess", "src/Receiver.php", "src/Kernel.php", "src/bootstrap.php",
}
DEPLOY_FILES = SOURCE_FILES | {"src/BuildInfo.php", "package-manifest.json"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def file_inventory(directory):
    paths = list(directory.rglob("*"))
    if directory.is_symlink() or any(p.is_symlink() for p in paths):
        raise ValueError("SYMLINK_NOT_ALLOWED")
    return {p.relative_to(directory).as_posix(): p for p in paths if p.is_file()}


def payload_digest(files):
    listing = {name: sha(files[name]) for name in sorted(SOURCE_FILES)}
    return sha(json.dumps(listing, sort_keys=True, separators=(",", ":")).encode())


def build_bytes():
    paths = file_inventory(ROOT / "package")
    if set(paths) != SOURCE_FILES:
        raise ValueError("SOURCE_ALLOWLIST_MISMATCH")
    files = {name: path.read_bytes() for name, path in paths.items()}
    if any(len(data) > 65536 for data in files.values()):
        raise ValueError("SOURCE_SIZE_LIMIT")
    version = (ROOT / "VERSION").read_text().strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.\d+", version):
        raise ValueError("INVALID_VERSION")
    provenance = json.loads((ROOT / "provenance.json").read_text())
    if sha(files["src/Receiver.php"]) != provenance["receiverFileSha256"]:
        raise ValueError("FROZEN_RECEIVER_CHANGED")
    for name, data in files.items():
        if name.endswith(".php") and (
            re.search(rb"\b(?:PDO|curl_init|file_put_contents|fopen|exec|shell_exec|sqlite3)\s*\(", data, re.I)
            or b"getenv(" in data
            or b"OgAdsConversionLedger" in data
        ):
            raise ValueError("DISALLOWED_RUNTIME_DEPENDENCY")
    digest = payload_digest(files)
    files["src/BuildInfo.php"] = (
        "<?php\ndeclare(strict_types=1);\nnamespace Hitv;\n"
        "if(!defined('HITV_POSTBACK_ENTRY')){http_response_code(404);exit;}\n"
        "final class BuildInfo {\n"
        f"    public const VERSION='{version}';\n"
        f"    public const PAYLOAD_SHA256='{digest}';\n"
        "    public static function metadata():array {\n"
        "        return ['version'=>self::VERSION,'payloadSha256'=>self::PAYLOAD_SHA256];\n"
        "    }\n}\n"
    ).encode()
    manifest = {
        "package": "HITV OGAds disabled cPanel receiver", "version": version,
        "payloadSha256": digest,
        "payloadDigestDefinition": "SHA-256 of canonical sorted JSON name-to-SHA-256 map of the eleven source package files; generated BuildInfo and manifest excluded.",
        "targetDirectory": "/home/onekfuxn/upxp.store/hitv-ogads/",
        "phpMinimum": "8.2", "phpExtensions": ["json"],
        "liveEnabled": False, "conversionWriterIncluded": False,
        "databaseRequired": False, "composerRequired": False,
        "baselineVersion": provenance["baselineVersion"],
        "baselineZipSha256": provenance["baselineZipSha256"],
        "existingClassProvenance": provenance["existingClassProvenance"],
        "files": {name: sha(data) for name, data in sorted(files.items())},
    }
    files["package-manifest.json"] = json_bytes(manifest)
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            entry = ZipInfo("hitv-ogads/" + name, (2000, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(entry, data)
    raw = buffer.getvalue()
    receipt = {
        "file": f"HITV-OGAds-cPanel-{version}.zip",
        "version": version, "payloadSha256": digest, "zipSha256": sha(raw),
        "manifestSha256": sha(files["package-manifest.json"]), "files": len(files),
        "liveEnabled": False, "conversionRecording": False,
    }
    return raw, receipt


def verify_bytes(raw, receipt):
    if sha(raw) != receipt["zipSha256"]:
        raise ValueError("ZIP_CHECKSUM_MISMATCH")
    with ZipFile(io.BytesIO(raw)) as archive:
        expected = {"hitv-ogads/" + name for name in DEPLOY_FILES}
        if len(archive.infolist()) != len(expected) or set(archive.namelist()) != expected:
            raise ValueError("ZIP_ALLOWLIST_MISMATCH")
        if archive.testzip() is not None:
            raise ValueError("ZIP_CRC_FAILURE")
        if any(e.file_size > 65536 or stat.S_ISLNK(e.external_attr >> 16) for e in archive.infolist()):
            raise ValueError("ZIP_ENTRY_REJECTED")
        files = {name.removeprefix("hitv-ogads/"): archive.read(name) for name in archive.namelist()}
    manifest_raw = files["package-manifest.json"]
    if sha(manifest_raw) != receipt["manifestSha256"]:
        raise ValueError("MANIFEST_CHECKSUM_MISMATCH")
    manifest = json.loads(manifest_raw)
    if set(manifest["files"]) != DEPLOY_FILES - {"package-manifest.json"}:
        raise ValueError("MANIFEST_ALLOWLIST_MISMATCH")
    if any(sha(files[name]) != digest for name, digest in manifest["files"].items()):
        raise ValueError("FILE_CHECKSUM_MISMATCH")
    if (manifest["version"] != receipt["version"]
        or manifest["payloadSha256"] != receipt["payloadSha256"]
        or payload_digest(files) != receipt["payloadSha256"]):
        raise ValueError("IDENTITY_MISMATCH")
    if any(manifest[k] is not False for k in ["liveEnabled", "conversionWriterIncluded", "databaseRequired"]):
        raise ValueError("DISABLED_CONTRACT_CHANGED")
    if receipt["liveEnabled"] is not False or receipt["conversionRecording"] is not False:
        raise ValueError("DISABLED_RECEIPT_CHANGED")
    return files


def extract_verified(files, parent):
    target = parent / "hitv-ogads"
    for name, data in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return target


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--out", type=Path, default=ROOT / "dist")
    build.add_argument("--php", default="php")
    verify = sub.add_parser("verify")
    verify.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "verify":
        receipt = json.loads((args.directory / "release.json").read_text())
        if Path(receipt["file"]).name != receipt["file"]:
            raise ValueError("INVALID_ARTIFACT_NAME")
        verify_bytes((args.directory / receipt["file"]).read_bytes(), receipt)
        print(json.dumps({"verified": True, **receipt}))
        return
    if args.out.exists():
        raise ValueError("OUTPUT_ALREADY_EXISTS_USE_NEW_DIRECTORY")
    raw, receipt = build_bytes()
    files = verify_bytes(raw, receipt)
    args.out.mkdir(parents=True)
    from regression import verify_package
    with tempfile.TemporaryDirectory(prefix="hitv-receiver-") as staging:
        package = extract_verified(files, Path(staging))
        result = verify_package(package, args.php, args.out / "evidence", receipt)
        if {name: p.read_bytes() for name, p in file_inventory(package).items()} != files:
            raise ValueError("TESTS_MODIFIED_PACKAGE")
    # The only archive written is the exact in-memory artifact already extracted and tested.
    (args.out / receipt["file"]).write_bytes(raw)
    (args.out / (receipt["file"] + ".sha256")).write_text(sha(raw) + "  " + receipt["file"] + "\n")
    (args.out / "package-manifest.json").write_bytes(files["package-manifest.json"])
    (args.out / "release.json").write_bytes(json_bytes(receipt))
    (args.out / "verification.json").write_bytes(json_bytes(result))
    print(json.dumps({"artifact": str(args.out / receipt["file"]), **receipt, "tests": result}, indent=2))


if __name__ == "__main__":
    main()
