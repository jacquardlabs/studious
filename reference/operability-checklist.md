# Operability checklist — lookup data

Not a detection crutch — a capable model already knows these failure classes. This
file is the **lookup data** it won't recall verbatim: per-library timeout defaults,
per-delivery-guarantee idempotency signatures, and per-runtime shutdown idioms. The
five dimensions live inline in `agents/operability-auditor.md`; consult this for the
specifics. CLAUDE.md's documented operational posture overrides anything here.
Severity stays exposure-gated: no path from the failure to user or operator impact →
`Potential`, drop a tier.

## Outbound-call timeout defaults

The library sets what "missing" means — absence of an explicit timeout is the finding
only where the default is none.

| Library | Default | Absence is the finding? |
|---|---|---|
| Python `requests` | none — hangs forever | yes |
| Python `httpx` | 5 s | no — flag explicit `timeout=None` instead |
| Python `boto3`/botocore | 60 s connect / 60 s read | no |
| Python `urllib.request` | none | yes |
| JS `fetch` | none from the API itself | yes on server-side code |
| JS `axios` | none | yes |
| Node `undici` | 300 s headers / 300 s body | borderline — flag on user-facing paths |
| Go `http.Client{}` / `http.DefaultClient` | zero value = none | yes |
| Java `OkHttp` | 10 s connect/read/write | no |
| Java `HttpURLConnection` | none (0 = infinite) | yes |
| JDBC | driver-specific, often none | verify per driver before flagging |
| Ruby `Net::HTTP` | 60 s open/read | no |

Retry hygiene at any layer: a retry without exponential backoff and jitter, without a
cap, or wrapping a non-idempotent operation is a finding — including resilience
libraries left at aggressive defaults.

## Idempotency signatures per delivery guarantee

At-least-once delivery means every handler eventually re-runs. What non-idempotent
looks like:

- **SQS/SNS** — standard queues redeliver; a handler that inserts/charges/sends
  without a dedup key duplicates on redelivery. FIFO dedup IDs cover a 5-minute
  window only.
- **Kafka** — offset committed after side effects = at-least-once; side effects
  re-run on rebalance. Look for a transactional producer or consumer-side dedup.
- **Celery** — `acks_late=True` redelivers on worker death: external writes need an
  idempotency key. The default (early ack) *loses* work instead — a different
  finding, same dimension.
- **Sidekiq** — retries by design; a job with external side effects and no
  uniqueness/idempotency guard duplicates on every retry.
- **HTTP clients** — retrying POST (non-idempotent by contract) without an
  idempotency key; retrying an ambiguous failure as if it never happened (a timeout
  is not a "didn't happen").

## Graceful-shutdown idioms per runtime

The deploy manifest's grace period (infra-auditor's lane) only helps if the
application uses it:

- **Node** — `process.on('SIGTERM')` → `server.close()` to stop accepting and drain
  in-flight work; no handler means in-flight requests are dropped.
- **Python** — `signal.signal(SIGTERM, ...)`; gunicorn/uvicorn drain the server but
  not background threads or tasks the app spawned itself.
- **Go** — `signal.NotifyContext` + `srv.Shutdown(ctx)`; a bare `ListenAndServe`
  never drains.
- **JVM** — shutdown hooks; Spring's graceful shutdown is opt-in before Boot 2.3 and
  property-controlled after.
- **Workers/consumers** — a stop flag checked between messages; a consumer that
  can't be interrupted mid-batch re-processes the batch (see idempotency above).

## Structured-logging detection

Determine the codebase's convention before flagging a line for breaking it:

- A configured JSON/structured logger (structlog, pino, zap, logrus, slog, Serilog,
  a JSON formatter on stdlib logging) means structured is the convention; new
  `print`/`console.log`/string-interpolated-only lines in server code break it.
- Correlation: if existing request-scoped logging carries a request/trace ID
  (middleware, MDC, contextvars), new request-path logs that drop it are the finding.
- No logging convention at all in a service codebase is a single Track-tier
  observation, not a per-line finding.
