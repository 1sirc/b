# HITV OGAds receiver — disabled cPanel package

Prepared 14 November 2026, release-identity revision 3. Target: `/home/onekfuxn/upxp.store/hitv-ogads/`.

This is an isolated deployment of HITV's existing callback parser, direct-peer verifier and disabled endpoint. It is **not an active monetization service**. It has no database connection, conversion writer, campaign client, entitlement issuer, simulation route, login, catalog or player code. Adding a key, setting an environment variable or setting `live_enabled=true` cannot activate it.

## Routing revision and current deployment

Revision 3 preserves routing-v2 behavior and adds a non-secret health build object with version and payloadSha256. The payload digest identifies the source file set; it is NOT the ZIP checksum. The archive checksum and complete manifest checksum are recorded outside the ZIP in release.json. BuildInfo.php is generated during the build and loaded by the existing bootstrap. A matching health marker helps identify stale code but cannot prove every deployed file matches. Use the separate operator-only verify-deployed.php tool and the expected manifest checksum from the verified artifact for that purpose; never upload development tools into this web directory.

The public health URL returned HTTP 200 with disabled mode during the read-only check on 14 November 2026. The previously reported public `ROUTE_NOT_FOUND` was not reproduced. This revision is a locally tested portability fix, not proof of the historical hosting failure or a reason to replace a currently working deployment immediately.

The old adapter hard-coded `/hitv-ogads`. The new adapter derives the URL mount from PHP's `SCRIPT_NAME`, verifies the executing script matches the selected entry, and compares complete request paths. Both `/health.php` at a root mount and `/hitv-ogads/health.php` at a subdirectory mount are supported. The rewritten callback alias is relative to that same mount. Directory segments must use ASCII letters, digits, hyphens or underscores. No request header can supply or override the mount. Missing/invalid script paths, nonempty `PATH_INFO`, encoded path aliases and prefix-only matches are rejected.

The callback contract, direct-peer verification, HTTPS/host/method checks, private configuration path and disabled conversion behavior are unchanged. Neither `.htaccess` nor the PHP entry points were changed. The package has no publicly accessible diagnostic script.

## URLs after deployment (not deployed by this task)

Assuming cPanel's document root for `upxp.store` is `/home/onekfuxn/upxp.store`:

- Health: `https://upxp.store/hitv-ogads/health.php`
- Preferred callback, no rewrite dependency: `https://upxp.store/hitv-ogads/postback.php`
- Exact optional REST alias: `https://upxp.store/hitv-ogads/api/v1/offers/ogads/postback`
- Future OGAds template, **do not activate yet**:

```text
https://upxp.store/hitv-ogads/postback.php?offer_id={offer_id}&aff_sub4={aff_sub4}&ip={session_ip}
```

The existing receiver uses `aff_sub4`, not `aff_sub`; do not append `payout`. It accepts exactly three callback fields once live processing is implemented. No API token, session bearer or shared secret belongs in the URL. Visitor `ip` is not the connecting callback server's identity.

## Hosting requirements

- PHP 8.2+ with standard JSON support. No Composer, MySQL, SQLite, cURL or shell access is required for this disabled artifact.
- A valid TLS certificate for `upxp.store` and direct HTTPS termination visible to PHP as `HTTPS=on` or `1`. It does not trust `X-Forwarded-Proto`, `Forwarded`, `X-Forwarded-For` or `X-Real-IP`.
- Apache 2.4 with permission for these per-directory directives, or a compatible server verified by the hosting operator. `mod_rewrite` is needed only for the optional REST alias; the direct PHP URLs still work when that module is absent. `.htaccess` directives require the appropriate AllowOverride/AllowOverrideList settings. A host that ignores or rejects these files must be reviewed before deployment is accepted.
- Confirm this subdirectory runs the required PHP version without changing the PHP behavior of the parent UPXP website. Check cPanel Domains for the actual document root. The target directory alone does not prove the domain maps there.
- No CDN/reverse-proxy trust is configured. If one is present, stop before live activation; a reviewed trusted-proxy design is needed for source-IP authentication.

## cPanel installation, for the owner to perform later

For an **existing installation**, first save a private backup of the actual deployed `hitv-ogads/` directory outside all website document roots. Do not assume it is byte-identical to an earlier ZIP. Compare `package-manifest.json` locally with the replacement. Only after approving an update, replace the files listed in this ZIP within that directory, including its own hidden files. Preserve the external private configuration file; never replace the parent site's `.htaccess`. Relative to routing-v2, this release adds generated `src/BuildInfo.php`, loads it from the bootstrap, and adds a health build marker; the README and manifest also change. Receiver behavior and routing remain unchanged. No database migration is involved. Then run the no-conversion checks. The steps below apply to a new installation.

1. Verify the ZIP's SHA-256 against the separate `.sha256` file. Confirm this target folder is new/empty; do not overwrite an existing installation or parent `.htaccess`.
2. In File Manager enable **Show Hidden Files**, navigate to `/home/onekfuxn/upxp.store/`, upload the ZIP and extract it there. Its one top-level folder is `hitv-ogads/`, so the result is the requested target. **Do not extract the outer folder into the target again** or create `hitv-ogads/hitv-ogads/`.
3. Confirm `postback.php`, `health.php`, root `.htaccess`, and the `src/` and `config/` deny files are present. Expected permissions: directories 0755, packaged files 0644; never use 0777. Do not change permissions on the parent website.
4. No config or API credential is needed for the disabled health/callback checks. Optional example: `config/receiver.example.php`. If future operator configuration is needed, place a private copy at `/home/onekfuxn/hitv-private/ogads-postback.php`, outside every website document root, readable by this site's PHP identity (normally 0600). Keep `live_enabled=false`. Never put `.env`, database passwords or the Offer API key in this web folder.
5. Run the no-conversion checks below. Remove the uploaded ZIP from the web directory afterwards (keep the original Windows copy). Do not change the OGAds global postback or enable campaigns at this stage.

The package affects routing only within `hitv-ogads/`. It does not edit or replace the parent UPXP application, `hitv.website`, DNS, TLS, PHP version or cPanel settings. If the parent application's routing intercepts these URLs, stop and report that routing conflict rather than editing the parent blindly.

## Test without recording a conversion

These commands are instructions for **after an approved upload**. Only the already-deployed public health endpoint was read during this review; no public callback was sent and this revision was not deployed. `curl.exe` on Windows or a regular browser can perform the GET checks. Do not use `-k` or disable certificate validation.

```powershell
curl.exe --proto '=https' --max-time 15 -i 'https://upxp.store/hitv-ogads/health.php'
curl.exe --proto '=https' --max-time 15 -i 'https://upxp.store/hitv-ogads/postback.php?offer_id=910001&aff_sub4=00000000000000000000000000000000&ip=192.0.2.20'
```

Expected health: **HTTP 200**, JSON with `service: "HITV OGAds postback"`, `mode: "disabled"`, `liveCampaigns: false`, `conversionRecording: false`.

Expected dummy callback: **HTTP 503**, JSON with `error: "OGADS_ACTIVATION_INCOMPLETE"`, `mode: "disabled"`, `conversionRecorded: false`. This intentional 503 is the successful safety check, not a successful OGAds conversion. The dummy ID is not an issued viewing binding and the address is documentation-only. No offer page, OGAds API, advertiser or real viewing session is involved. More importantly, there is no database/crediting code or conversion handler in the package at all.

Also check:

- The REST alias with the same dummy query returns the same disabled response when rewriting is supported.
- `/hitv-ogads/src/Receiver.php`, `/hitv-ogads/config/receiver.example.php`, `/hitv-ogads/package-manifest.json`, `/hitv-ogads/README.md` and directory listings return **403 or 404**, with no file contents. PHP dependency files additionally have direct-access guards.
- Plain HTTP must not reach a health/crediting success response; PHP returns **426 HTTPS_REQUIRED**, unless the host itself redirects to HTTPS. Callback POST is **405**. No untrusted forwarded header can make HTTP trusted HTTPS.
- Any result displaying UPXP HTML, source code, a directory listing, a PHP exception or a TLS warning is a failed hosting check. Do not activate anything.

Shared-host access/WAF logs may record requests before PHP runs. The package does not log query strings, tokens or visitor data, but cannot configure hosting-level logs through PHP. Verify query/IP redaction and retention with the hosting operator before live callbacks containing real visitor data. Dummy test values do not contain credentials or real visitor identity.

## Contents and limits

- `postback.php`, `health.php`: guarded PHP entry points; no user data.
- `src/Receiver.php`: four verbatim class definitions extracted from the existing HITV source (`OfferError`, `OgAdsCallbackContract`, `OgAdsPeerVerifier`, `OgAdsPostbackEndpoint`), plus a direct-access guard. Class digests are in the manifest.
- `src/Kernel.php`, `src/bootstrap.php`: isolated cPanel path/HTTPS/host/method policy and optional private configuration loading. No original application bootstrap is included.
- `.htaccess` files and `.user.ini`: scoped routing, private-folder blocking, disabled directory listings and PHP error-display suppression. Security does not rely on a configurable `live_enabled` flag: the conversion writer is absent.
- `config/receiver.example.php`: non-secret defaults. No current sender IPs are assumed from historical tutorials.
- `package-manifest.json`: included file hashes, exact dependencies and provenance. No credentials, local Windows paths or database content.

Real processing still needs the current account-specific OGAds sender/transaction/reversal contract, campaign/content-monetization approvals, private rotated outbound credential, reviewed real offer binding/ledger/entitlement implementation and a provider-issued validation. Those capabilities are intentionally not enabled or simulated as live by this ZIP.

Local verification covers extracted-file hashes, ZIP integrity and exclusions, all PHP syntax, request-policy/receiver fixtures and actual loopback HTTP behavior at both root and subdirectory mounts. Complete entry/bootstrap requests with injected HTTPS server variables also exercise the exact shipped files; those fixtures are not actual TLS or Apache tests. PHP's development server does not process `.htaccess`. The optional alias is tested in PHP fixtures, not an Apache/LiteSpeed rewrite engine. **The existing public health success does not validate this undeployed revision, the complete hosting access policy or the live conversion contract.**

Do not upload generic PHP/static probes from unrelated troubleshooting instructions: this package's `.htaccess` intentionally denies unlisted paths, so a probe returning 404 would not establish a document-root failure. Do not expose `phpinfo()`, absolute filesystem paths or private configuration online. If the original error recurs, retain the exact response/time and compare the deployed `health.php` entry constant, kernel hash and hosting rewrite configuration privately before changing anything.

## Rollback

This package writes no application/database/session state. For a first deployment into a new folder, disable only this subdirectory through the hosting operator or move that folder outside the document root. Never delete/replace parent UPXP files, its `.htaccess`, databases or other sites. Do not restore catalog data as part of this package's rollback.

For an update, restore the backed-up deployed `hitv-ogads/` files to the same directory, preserving hidden deny files and external private configuration, then recheck health. Keep the old Windows ZIP and checksum for reference; use the actual deployment backup for rollback if it differs from that ZIP. No data rollback is required.

## References

- cPanel File Manager upload/extract: https://docs.cpanel.net/cpanel/files/file-manager/
- Apache per-directory routing: https://httpd.apache.org/docs/2.4/rewrite/htaccess.html
- Apache access configuration: https://httpd.apache.org/docs/2.4/howto/htaccess.html
- PHP server variables: https://www.php.net/manual/en/reserved.variables.server.php
- PHP local development server limitations: https://www.php.net/manual/en/features.commandline.webserver.php
- OGAds public callback format: https://github.com/learn-ogads/followers-landing-page/blob/version-1.0.0/README.md
- OGAds public sender-IP example: https://github.com/learn-ogads/followers-landing-page/blob/version-1.0.0/api/postback.php
