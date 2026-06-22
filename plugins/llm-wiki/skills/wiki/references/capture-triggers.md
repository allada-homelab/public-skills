# Capture triggers — the high-value categories

A finding is worth a concept when it is **durable** (true beyond this turn) and **reusable** (the next
session, or another person, would act on it). When one of these fires, capture it — most use the
**Gotcha shape** in `concept-template.md` (name what fails, what works, and *why*).

## Failure modes (capture the trap + the way out)

- **Failure→fix** — you tried an approach that failed and found the one that works. Capture the wrong
  way, the right way, and *why*, so the mistake isn't repeated.
- **Surprising root cause** — the bug's cause was far from its symptom. Capture the symptom→cause
  mapping so the same symptom routes straight to the cause next time.
- **Silent footgun** — a tool/API/config did the wrong thing *without erroring* (bypassed a check,
  swallowed an error, returned a misleading default). Silent ones are the most expensive — no error
  trail leads you back. Capture the surprising behavior and the guard against it.
- **False-done / verification gap** — a check passed but didn't actually prove the thing (a green
  build/compile, a test that doesn't exercise the path). Capture what the signal *doesn't* cover and
  what real confirmation requires.
- **Hidden precondition / environment trap** — it works only when an env var / installed tool / cwd /
  permission is present. Capture the precondition so it isn't rediscovered the hard way.
- **Stale knowledge / version drift** — the documented, remembered, or trained-in way no longer works;
  an API or default changed. Capture the current truth and the version it changed at.
- **Performance cliff** — an approach that is fine at small N degrades at scale (O(n²), N+1 queries,
  full rescans). Capture the cliff and the scalable approach.

## Also durable (not failure-shaped)

- **Decision + rejected alternative** — a fork where you chose X over Y for a reason; capture the *why
  not Y* so it isn't re-litigated.
- **Convention / schema / how-it-works** — a stable interface, data shape, or mechanism others rely on.

When nothing here fired, don't invent a finding — just stop.
