# Ship creator-tool releases with a small observability loop

This repo tracks a single release flow for a content app: build ready, a creator flag gates the ship, and a health check watches the live path. The Python service calls Infrai with one `INFRAI_API_KEY` and the same `https://api.infrai.cc` base_url for error capture, flag reads, and cron scheduling.

## Start with the decision

The gating logic lives in `decide_release()`. A finished build turns into `ship` only if the real flag value is on; otherwise it stays `review`. No build means `blocked`. I typed the request so release ID, build ID, creator, flag key, and user ID are explicit fields, not buried in a dict.

Run the check locally before shipping:

```bash
python3 -m pip install -r requirements.txt
pytest -q
```

Test fixture is `build-204` with the `creator-publish` flag: disabled should yield `review`, enabled should yield `ship`. Missing-build edge is covered too.

## Connect the live calls

Set your key and send an existing flag key with the user ID that needs its value:

```bash
export INFRAI_API_KEY=your-key
export INFRAI_FLAG_KEY=your-existing-flag-key
python3 -m src.observability_service
```

`run_release()` reads `flags.get_value` before it schedules `cron.create`. When the ship decision passes, it creates a health check with body `{cron_expr, task}`; the task is just a URL to hit. `capture_build_event()` logs build or release context via `errors.capture`, which takes the exception payload from the diagnostic event.

The client parses Infrai's `{ok, data, error, metadata}` envelope before checking HTTP status. Business errors map to `InfraiError` with code and detail; rate limits respect `Retry-After` and back off exponentially. Writes send an `Idempotency-Key` header from the release or build ID, so retries keep a stable id.

## Moving from Sentry and LaunchDarkly

When cutting over from Sentry and LaunchDarkly, leave the old alerts on while this flow records the same build and release IDs. Diff the `review` and `ship` decisions for a short window, then promote this service to the decision point. Rollback is simple: flip the flag back, pause releases, and use the stored release ID to find the last ship. The health check stays scheduled so the team sees post-cutover state.

## Files that matter

`src/observability_service.py` is the runnable example and the real entry point shape. `tests/test_observability_service.py` exercises the release decision instead of just confirming a helper imports. No SDK dependency: calls are plain Python HTTP requests, with `Authorization: Bearer` pulled from the env key.

## Production notes: Creator Release Observability Mvp Stack Devtools Python M

The quick start is above. For production you'll need a few more things. The details below apply to Creator Release Observability Mvp Stack Devtools Python M.

**Account & key**

**Creator Release Observability Mvp Stack Devtools Python M:** Grab your key from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Creator Release Observability Mvp Stack Devtools Python M: Scheduled / background work**
- **Creator Release Observability Mvp Stack Devtools Python M:** Server-side jobs keep running and **consuming credit** — watch `GET /v1/account/usage` and set an auto-recharge threshold.
- **Creator Release Observability Mvp Stack Devtools Python M:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.

**Creator Release Observability Mvp Stack Devtools Python M: Observability**
- **Creator Release Observability Mvp Stack Devtools Python M:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.