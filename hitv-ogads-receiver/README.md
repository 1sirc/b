# HITV receiver — build and release verification

This standalone project packages the existing disabled PHP receiver. It does not deploy, connect a database, request offers or record conversions. Android and the main PHP backend are not dependencies of this build.

## Windows build

Requires Python 3.10+ and PHP 8.2+ with JSON. No Composer, pip dependencies, database or credentials are needed.

From this directory:

    python -m unittest discover -s tests -p "test_*.py" -v
    python tools/release.py build --out dist --php "D:\HITV-Development\Projects\hitv\.tools\php\php.exe"
    python tools/release.py verify --directory dist

Use a new output directory if dist already exists. Builds never overwrite a previous delivery. Linux CI uses php from PATH. Local validation used PHP 8.4.27; the prepared Ubuntu 24.04 workflow uses its installed PHP and records the actual version. A PHP 8.2 host is still subject to staging verification.

The deployment ZIP is generated once in memory, verified, extracted and tested. Only those exact bytes are written as the deliverable. Fixed timestamps, byte-preserved package inputs and ZIP_STORED remove timestamp, checkout line-ending and zlib differences. Package inputs are marked -text in .gitattributes so Git does not alter the frozen PHP classes; build tools use LF. A regression checks byte-for-byte reproducibility. Tests and tools are excluded from the 13-file deployment ZIP. The separate source ZIP is for a repository, not cPanel.

## Identity and receipts

- release.json records release version, source payload digest, ZIP SHA-256 and manifest SHA-256.
- package-manifest.json lists every deployed file hash except itself; its hash is recorded externally.
- Health adds build.version and build.payloadSha256 without exposing secrets, paths or account data.
- The payload digest is the SHA-256 of canonical sorted JSON mapping the eleven source package names to file hashes. Generated BuildInfo.php and the manifest are excluded to avoid a circular hash.
- A correct health marker is correlation evidence, not proof of all installed files. Pair it with private file verification and the CI artifact/run record.

Keep release.json and the checksum from a trusted successful CI run; hashes do not authenticate an artifact if an attacker can replace both the archive and its receipt. GitHub's pinned artifact actions also reject transfer-digest mismatches.

## GitHub workflow

The owner selected 1sirc/b. HITV is isolated under hitv-ogads-receiver/ there, with its two workflows under the repository's root .github/workflows/. Existing unrelated files are preserved. This standalone source layout keeps its own .github templates; the repository copy adjusts working directories and artifact paths for the subdirectory. No deploy workflow is included.

1. Commit the source project to the chosen repository. The workflow expects main as its default branch; adjust the push filter if the repository uses another name.
2. The Verify workflow runs on main pushes, pull requests and manual requests. Its test job runs unit/security checks, builds once and tests the extracted archive. The package job verifies the transferred artifact and uploads the same bytes as hitv-receiver-verified. There is no deployment step.
3. Download the hitv-receiver-verified artifact from a successful default-branch run. Preserve its run ID, commit, artifact ID, receipt and checksum. Pull-request artifacts are not accepted by the deployed release check.
4. Only after an approved manual deployment, run Read-only deployed receiver check with that Verify run ID. It verifies the successful default-branch run, downloads the exact artifact, checks its hashes, and requests only the fixed HTTPS health URL. Redirects, stale/missing identity, enabled modes, invalid JSON and excessive response size fail the check. It never submits a postback.

All three official actions are pinned to full commit SHAs, verified against their upstream tags. Checkout does not persist credentials. Workflow permissions are contents:read plus actions:read only for the separate manual check. No dependency cache, deployment key, Offer API token, repository secret, write token, pull_request_target trigger or scheduled workflow is used.

Configure the release-verification GitHub environment's reviewers and branch restrictions separately if your plan supports them; declaring an environment in YAML alone does not establish approval protection. No automatic activation job exists. A deployment or future OGAds activation requires a separate reviewed change.

## Private cPanel artifact verification

Do not upload this source tree to cPanel. Deploy only the approved inner hitv-ogads ZIP contents to the existing isolated directory after taking a private backup of the actual deployed files. Never edit the parent website's .htaccess or private credential configuration.

Keep tools/verify-deployed.php outside every web root, for example in an operator-only tools directory. After an approved upload, run privately in cPanel Terminal:

    php /home/onekfuxn/hitv-private-tools/verify-deployed.php /home/onekfuxn/upxp.store/hitv-ogads EXPECTED_MANIFEST_SHA256_FROM_RELEASE_JSON

This reads and hashes files without running application code, reading private configuration, writing state or connecting to OGAds. It rejects file/hash mismatches, symlinks and unexpected files. If Terminal is unavailable, ask the host to run this exact private check or privately download the deployed package files for comparison. Do not expose a public diagnostic or checksum endpoint.

Then run the read-only health check using the same verified artifact:

    python tools/health_check.py --receipt dist/release.json --output health-result.json

The pre-existing endpoint may be healthy but fail the new identity check until this exact revision is approved and deployed. That is an artifact mismatch, not evidence of a broken receiver. This task does not require an upload to keep the current health URL working.

## Hosting checks and OPcache

Local HTTP checks exercise the exact PHP entry points at both / and /hitv-ogads. Positive HTTPS and optional alias checks inject server variables; they do not validate Apache/LiteSpeed rewriting or actual TLS on this new build. Verify those separately after an approved upload. Sensitive paths must return 403/404 with no source/configuration content.

Ask the hosting operator to check the website PHP SAPI's opcache.validate_timestamps and opcache.revalidate_freq privately. PHP CLI configuration can differ from the website PHP pool. If timestamp validation is disabled, replacing files alone may leave old opcodes active; ask the host to invalidate the site's cache using its supported mechanism. Do not add a public reset/phpinfo endpoint or restart unrelated sites. OPcache has not been established as the cause of the historical routing symptom.

## Disabled callback and activation boundary

The current endpoint rejects callbacks with OGADS_ACTIVATION_INCOMPLETE before sender authentication or parsing. Dummy, malformed and repeated requests cannot write conversions because the conversion closure and ledger are absent. A disabled 503 proves no live processing, not an authentic OGAds delivery. Public request logging is controlled by the host, not this package.

Do not claim authenticated live OGAds callbacks passed. First obtain the current account-specific sender, tracking, transaction and reversal contract, approved campaign/content scope, private rotated outbound key, and an approved validation-only implementation. That future implementation must authenticate before accepting or logging a conversion. Do not activate a flag to simulate readiness; this package cannot become live through configuration.

A controlled real callback test remains blocked until those requirements are confirmed. When authorized later, record only a non-sensitive correlation identifier, timestamp, status and validation result. Never log tokens, raw callbacks, visitor IPs or private signed values. The public tutorial's aff_sub4/offer_id/ip example is not definitive evidence of current account authentication.

## Rollback and preservation

Keep the actual deployed directory backup outside web roots. Restore only those backed-up package files to the same folder, preserve private config and parent routing, and compare the old manifest/health. No database migration or data rollback is involved. The original routing-v2 ZIP remains unchanged.

## Primary references

- GitHub workflow security: https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
- Official checkout action: https://github.com/actions/checkout/tree/3d3c42e5aac5ba805825da76410c181273ba90b1
- Official artifact upload: https://github.com/actions/upload-artifact/tree/cf430e030ddbb5b0abf93d22962f4752f3646cd9
- Official artifact download: https://github.com/actions/download-artifact/tree/9000827ccba6bdab643e8b6fd33ac0654aef8333
- Ubuntu 24.04 runner software: https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md
- PHP OPcache: https://www.php.net/manual/en/opcache.configuration.php
