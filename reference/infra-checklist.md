# Infrastructure checklist — lookup data

Not a detection crutch — a capable model already knows these misconfiguration classes.
This file is the **lookup data** it won't recall verbatim: exact signatures, the
workflow-injection sink list, and per-tool defaults. The five dimensions live inline in
`agents/infra-auditor.md`; consult this for the specifics. CLAUDE.md's documented
infrastructure posture overrides anything here. Severity stays exposure-gated: no path
from an attacker or an outage to the resource → `Potential`, drop a tier.

## Per-tool misconfiguration signatures (one line each)

- **IAM wildcards** — `Action: "*"`, `Principal: "*"` / `AWS: "*"`, `Resource: "*"` on
  write-capable actions, unscoped `iam:PassRole`, `sts:AssumeRole` trust to any account.
- **Public exposure** — security group / firewall ingress from `0.0.0.0/0` or `::/0` on
  non-public ports, `publicly_accessible = true`, bucket ACL `public-read`/policy with
  `Principal: "*"`, K8s `Service type: LoadBalancer` or `Ingress` without auth in front.
- **Missing encryption** — no `encrypted`/`storage_encrypted`/`kms_key_id` on volumes,
  DBs, queues, topics; TLS disabled or `enforce_ssl = false`; unencrypted state backend.
- **Stateful-resource safety** — no `deletion_protection`, no backup/versioning/PITR on
  databases and buckets, `force_destroy = true`, `skip_final_snapshot = true`.
- **Blast radius** — a rename or immutable-field change that forces destroy/replace
  (Terraform plan would show `-/+`; `moved` blocks / CDK logical-ID retention absent);
  state migrations without a documented path.

## Workflow-injection sinks (GitHub Actions and kin)

- Untrusted event fields interpolated into `run:` or `script:` — `${{ github.event.issue.title }}`,
  `${{ github.event.pull_request.title }}`, `${{ github.event.comment.body }}`,
  `${{ github.head_ref }}` — attacker-controlled text becomes shell. Fix: pass via `env:`.
- `pull_request_target` (or `workflow_run`) combined with a checkout of the PR head
  (`ref: ${{ github.event.pull_request.head.sha }}`) — secrets + attacker code.
- Third-party actions pinned to a tag or branch (`uses: some/action@v3`) instead of a
  commit SHA — the tag can move under you.
- `permissions:` absent (legacy default is write-all) or broader than the job needs;
  `GITHUB_TOKEN` with `write` handed to steps that only read.
- Secrets reachable from fork-triggered runs; `secrets: inherit` passed to a reusable
  workflow that doesn't need them.
- Self-hosted runners on public-PR workflows.

## Container signatures

- No `USER` directive (runs as root); `:latest` or unpinned base image; secrets via
  `ARG`/`ENV`/`COPY .env`; `ADD` from a URL; `curl | sh` installs; package installs
  without version pins where the ecosystem supports them (`apt-get install -y pkg`
  vs `pkg=1.2.*`).

## Per-tool defaults

The tool sets what "missing" means — detect it from the changed files before rating a
finding.

| Tool | Encryption | Public access | Deletion safety |
|---|---|---|---|
| Terraform (raw) | Off unless set — absence is the finding | Provider default (usually private); explicit `0.0.0.0/0` is the finding | Off unless set |
| CDK (L2+) | Many constructs encrypt by default — verify the construct level before flagging | `blockPublicAccess` on by default for S3 | `RemovalPolicy` defaults to DESTROY on some constructs — verify stateful ones |
| CloudFormation | Off unless set | Off unless set | `DeletionPolicy` absent = delete |
| Kubernetes | N/A (cluster concern) | `Service`/`Ingress` exposure is explicit — judge the auth in front | PDB/replicas absent = single-replica |
| Docker/Compose | N/A | `ports:` binds 0.0.0.0 unless an address is given | N/A |
| GitHub Actions | N/A | fork/PR trigger surface | `permissions:` absent = legacy write-all |

If the tool can't be determined, say so in the residual line and rate defaults-dependent
findings `Potential`.
