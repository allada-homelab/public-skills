# Cross-linking (OKF v0.1)

Concepts form a graph by linking to each other with ordinary markdown links. The graph is richer than
the directory tree — any concept may link to any other.

## Use the relative `./` form

Write links **relative to the linking file**:

```markdown
Joined with [customers](./customers.md) on `customer_id`.
See the [deploy runbook](../runbooks/deploy.md).
```

- Relative links are OKF-valid **and** resolve correctly when the bundle is rendered on GitHub.
- Do **not** use bundle-absolute `/customers.md` links: a leading `/` does not resolve on GitHub's
  file view, which would fail the wiki's portability bar. (OKF permits the `/` form, but `/llm-wiki`
  standardizes on `./` for this reason.)
- This applies everywhere links appear: concept bodies, `index.md` bullets, and `log.md` entries.

## Edges are undirected; convey the relationship in prose

A markdown link records that two concepts are related, not *how*. State the relationship in the
surrounding text:

```markdown
# Joins
Joined with [customers](./customers.md) on `customer_id` (many orders → one customer).
```

## Broken links are tolerated on read

When reading, a link whose target is missing must not stop navigation — note it and continue. When
*writing*, `/llm-wiki:capture` runs a report-only link check and surfaces any dangling link in the
confirm diff so you can fix it before committing. (The Doctor also reports broken links as `R4`
link-health **warnings** — surfaced in its report, never blocking, since OKF tolerates dangling links.)
