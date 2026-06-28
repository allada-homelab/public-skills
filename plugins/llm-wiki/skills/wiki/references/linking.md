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
*writing*, the Doctor reports broken links as `R4` link-health **warnings** — never blocking, since OKF
tolerates dangling links. A capture that leaves a dangling link still lands; fix it in a follow-up if it
matters.
