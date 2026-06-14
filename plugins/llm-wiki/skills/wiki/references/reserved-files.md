# Reserved files: `index.md` and `log.md` (OKF v0.1)

`index.md` and `log.md` have defined structures and are **never** concept documents. The Doctor
enforces the structures below (rule R3).

## `index.md`

A directory listing for progressive disclosure — an agent reads it to see what exists before opening
files.

- **Subdirectory `index.md`: zero frontmatter.** No `---` block at all. Body is a heading + a bulleted
  list of the directory's concepts (and child directories), each with a short description.
- **Root `index.md`: frontmatter may contain only `okf_version: "0.1"`** — no other key. This is the
  one and only place the bundle declares its version. Frontmatter is optional even at the root, but if
  present it must be exactly this.

Root example:

```markdown
---
okf_version: "0.1"
---
# Sales knowledge

* [Orders](./orders.md) — One row per completed order.
* [tables/](./tables/index.md) — Warehouse table concepts.
```

Subdirectory example (`tables/index.md`, no frontmatter):

```markdown
# Tables

* [Customers](./customers.md) — One row per customer.
* [Orders](./orders.md) — One row per completed order.
```

## `log.md`

Chronological change history, **newest entries first**.

- Date headings use ISO-8601 `## YYYY-MM-DD`.
- Headings are ordered newest-first (dates non-increasing top to bottom).
- Each bullet begins with exactly one bold prefix: `**Update**`, `**Creation**`, or `**Initialization**`.

Example:

```markdown
# Directory Update Log

## 2026-06-14

* **Update**: Revised join paths in [Orders](./orders.md).
* **Creation**: Added [Customers](./customers.md).

## 2026-06-13

* **Initialization**: Bundle created.
```

Links inside `index.md` and `log.md` use the relative `./` form (see `linking.md`).
