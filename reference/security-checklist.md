# Security checklist — lookup data

**Lookup data only**: exact sinks, secret regexes, the JWT attack list, per-stack defaults — not the vulnerability classes themselves, which a capable model already knows. Core dimensions and the extended-class checklist live inline in `agents/security-auditor.md`. CLAUDE.md's documented security posture overrides this file. Severity stays reachability-gated: no user-controlled path to the sink → `Potential`, drop a tier.

## Extended-class signatures (one line each)

- **SSRF** — user-supplied URL/host reaches a server-side fetch (`requests.get`, `fetch`, image/webhook/PDF fetchers); check allow-listing + blocked metadata IP `169.254.169.254`.
- **Insecure deserialization** — `pickle.loads`, `yaml.load` (non-`safe_load`), Ruby `Marshal.load`, PHP `unserialize`, Java `ObjectInputStream` on untrusted bytes.
- **Path traversal** — user input in file paths, missing `../` normalization, archive extraction without zip-slip guards.
- **SSTI** — user input concatenated into a template string (Jinja2, Handlebars, Twig, ERB).
- **XXE** — XML parsers with external-entity resolution enabled.
- **Crypto failures** — MD5/SHA1 for passwords, ECB mode, hardcoded IV/salt/key, `Math.random()` for tokens, disabled TLS verification.
- **Mass assignment** — request bodies bound to models/ORM objects without a field allow-list.
- **File upload** — missing type/extension/size validation, executable upload, content-type spoofing, files under a web-served path.
- **ReDoS** — user input against a catastrophically-backtracking regex.
- **Open redirect** — user-controlled redirect target without an allow-list.
- **Business logic** — price/quantity manipulation, negative amounts, workflow/step bypass, replay on money-touching paths. No signature — trace the intended invariant.

## JWT attacks

`alg:none` accepted · RS256→HS256 confusion (public key used as HMAC secret) · signature not verified (decode-without-verify / wrong key) · missing `exp`/`nbf`/`aud`/`iss` validation · weak or hardcoded HMAC secret.

## Injection sinks by language

- **SQL** — Python `cursor.execute(f"...")`, Node template-literal queries, `.raw()` / `.query(string)`, Go `fmt.Sprintf` into a query, ORM `.where("raw " + x)`.
- **Command** — `os.system`, `subprocess(..., shell=True)`, `exec`/`execSync`/`spawn(..., {shell:true})`, backticks, `Runtime.exec`.
- **XSS** — `dangerouslySetInnerHTML`, `innerHTML`/`outerHTML`, `v-html`, `|safe` / `mark_safe`, `document.write`.
- **NoSQL** — user objects passed into Mongo operators (`$where`, `$ne` injection).
- **LDAP / XPath** — unescaped user input in filter strings.

## Secret patterns

Scan **git history**, not just HEAD (`git log -p` or a history-aware scanner). A secret live in history but removed from HEAD is Confirmed-exposed; remediation is **rotate, then purge history**.

- AWS `AKIA…` · GitHub `ghp_…` · Slack `xox[baprs]-…` · Stripe `sk_live_…` · GCP service-account JSON · private keys (`-----BEGIN … PRIVATE KEY-----`).
- High-entropy strings assigned to `secret`/`token`/`password`/`api_key`; `.env` committed; secrets inlined in client bundles.
- Also: **dependency confusion** (internal package names resolvable from a public registry) and lockfile-integrity gaps.

## PII signatures

Severity stays exposure-gated per the core rubric: rate on where the data actually lands and who can read it — a third-party sink or shared log store is live exposure; a guarded, internal-only path drops a tier and is marked `Potential`.

- **PII in logs** — user identifiers, emails, phone numbers, or session/API tokens interpolated into `logger.*` / `console.log` / `print` calls; whole request, user, or session objects dumped on error paths; auth headers echoed into access logs.
- **PII stored without retention** — a new table/column/bucket persisting emails, names, addresses, or free-text user content with no TTL, purge job, or documented retention decision; PII copied into analytics or backup stores that outlive the source record.
- **PII in error messages to third-party trackers** — exception messages or breadcrumbs carrying emails/IDs/tokens shipped to a tracker (Sentry, Datadog, Bugsnag, Rollbar) without a scrubber — `before_send`/`beforeSend` absent, attribute allow-lists missing, default PII filtering disabled.

## Per-stack defaults

The framework sets what "missing" means — detect it from the manifest before rating CSRF/header/session findings.

| Stack | CSRF | Headers | Session/cookie |
|---|---|---|---|
| Django | Middleware on by default — absence/exemption is the finding | Some via `SecurityMiddleware`; verify HSTS/CSP | Secure/HttpOnly need explicit settings |
| Rails | `protect_from_forgery` default — verify not disabled | Verify `force_ssl`, CSP initializer | `secure`/`httponly` via config |
| Express/Node | **No built-in CSRF** — verify a library is wired | **None by default** — verify `helmet` | Verify cookie flags set explicitly |
| Flask | None unless Flask-WTF — verify enabled | None by default | Verify `SESSION_COOKIE_*` flags |
| Spring | On by default for browser flows — verify not disabled | Some defaults; verify CSP/HSTS | Verify cookie flags |

If the stack can't be determined, say so in the residual line and rate header/CSRF findings `Potential`.
