# PR Review SOP

This is the standard procedure for reviewing pull requests on Editor Intelligence. It is written for both AI agents and human reviewers. Follow it for every PR review — drift here is how bugs, scope creep, and convention violations slip into the codebase.

The SOP is opinionated on purpose. It is the result of catching real bugs that pure code-reading missed (wrong-scope PRs, false claims in PR descriptions, server defaults missing despite documented presence, datetimes that look correct but break at the column boundary). Skip steps only when you can articulate why the skip is safe.

## When this applies

- Every PR opened against `master`, regardless of size.
- Re-reviews after the author pushes fixes.
- Self-PRs included — reviewing your own diff is still a review, and GitHub blocks `--request-changes` on it (use `--comment` instead).

## Before you start

Confirm setup:

```bash
gh auth status                 # must show: Logged in to github.com
gh pr view <N> --json mergeable,mergeStateStatus,baseRefName,headRefName
```

Fetch the PR branch locally:

```bash
git fetch origin pull/<N>/head:pr<N> -f
```

Re-read these docs at least once per session if you have not already:

- `docs/prd.md` §6 — the deferred-features list. Many "improvements" proposed in PRs are deferred features in disguise.
- `docs/constraints.md` — the architectural don'ts and schema invariants.
- `docs/decisions.md` — every non-obvious choice has a number (D1, D2, ...). Cite them when relevant.
- `docs/conventions.md` — code layout, cross-module imports, datetime convention, alembic workflow.
- `docs/schema.dbml` — schema source of truth (mirrored by `core/models.py`; ORM wins on drift, but flag it).

## The five phases

Run these in order. Skipping a phase means you do not have grounds to approve.

### Phase 1 — Verify scope

Compare three things before reading any code:

1. PR **title**
2. PR **body** (what it claims to close, what it claims to implement)
3. Actual **diff** (`git diff master..pr<N> --stat`)

If they disagree, stop. Do not review the code. Examples of real scope failures:

- Title `feat(scoring)`, body `Closes #7`, branch `feat/b5-scoring`, diff touches only `ingest/*` (PR #15 in this repo).
- Title `feat(clustering)`, body `Closes #5` only, diff also implements `ingest/*` (PR #13 first version — body must list both `Closes #3` and `Closes #5`).

Either ask the author to fix scope (split the PR, retitle, or update the body), or close it. Reviewing the wrong code wastes everyone's time.

### Phase 2 — Code review by category

Read the diff with `gh pr diff <N>` and the relevant files via `Read`. Group findings into four categories. Do not mix them — treating a Discussion item as Required confuses authors; treating a Required as a Nit gets bugs merged.

| Category              | Definition                                                                        | Example                                                                                                              |
| --------------------- | --------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| **Required**          | Must be fixed before merge. Bug, convention violation, doc drift, security issue. | Missing `server_default` on PK; `_resolve_source` fallback misattributing articles; `datetime.utcnow()` in new code. |
| **Discussion**        | Design decision the author should confirm with the team. Not strictly wrong.      | Clustering window using `created_at` vs `published_at`; sequential vs parallel RSS fetch.                            |
| **Known limitations** | Not fixable in this PR without scope expansion. Document and move on.             | Sitemap titles derived from URL slugs; Trends RSS lacks article pubdates.                                            |
| **Nits**              | Cosmetic or low-value. Author may defer.                                          | Type hints `Mapped[list \| None]` vs `Mapped[list[float] \| None]`; one-line docstrings.                             |

Every Required and Discussion item must:

- **Cite the file path and line number.** "`pipeline.py:89` — `run = ClusterRun(...)` shadows the module-level function".
- **Cite the doc that justifies the rule.** "Per `docs/constraints.md` §"Schema invariants", `vector(768)` is fixed."
- **Provide the concrete fix.** Show the replacement code, not just the problem.

What to look for, by area:

- **Schema / migrations.** Compare against `schema.dbml`. Confirm `server_default` for documented `[default: ...]` values. Confirm `nullable` matches dbml. Check enum names. Verify `CREATE EXTENSION IF NOT EXISTS vector` in baseline migrations. Verify downgrade drops enum types (Postgres does not auto-drop them).
- **Cross-module imports.** Per `docs/conventions.md`, a module may only import from packages declared in its `pyproject.toml`. New imports without matching dep declarations are bugs even if they work locally.
- **Constraints checklist.** Walk `docs/constraints.md` mentally:
  - `api` package must not import torch, transformers, or any ML module.
  - Batch modules must not import each other (only via `core`).
  - `article_gsc_metric` is reference-only — never returned via API.
  - `source_type` enum is exactly `{rss, internal}`.
  - Datetimes are naive UTC (`docs/conventions.md` §Datetimes).
  - No write-side API endpoints in MVP.
- **Decisions check.** When the PR makes a non-obvious choice, look for a corresponding entry in `docs/decisions.md`. If none exists, ask whether one should be added.

### Phase 3 — Verify PR body claims

PR descriptions claim things the code may not actually do. Check every concrete claim against the code. Real failures from this repo:

- Body claimed "parallel RSS fetch (asyncio.gather)" but `rss.py` had a plain `for source in sources: await ...` loop.
- Body claimed "HTML-to-text sanitization" but `_parse_entry` did `summary.split("\n")[0][:2000]` with no parsing.

False claims in a PR description are worse than the underlying bug. They cause the next reviewer (or merge-bot) to trust the description and skip verification. Always either:

- Ask the author to remove the claim from the body, or
- Ask the author to actually implement what was claimed.

Do not approve a PR whose description does not match the code.

### Phase 4 — Smoke test

`import` tests are not smoke tests. A smoke test runs the actual code path being changed against real or seeded data. Skip this phase only when:

- The change is documentation-only.
- The change is purely a rename with no behavior change, AND tests cover it.

Otherwise, run a minimal end-to-end exercise. Examples:

- **Schema PR** (PR #12 pattern):
  ```bash
  uv run alembic upgrade head      # creates tables on a fresh DB
  uv run alembic downgrade base    # tears down cleanly, drops enum types
  uv run alembic upgrade head      # succeeds again — proves enum drop works
  ```
- **Ingest PR** (PR #13 pattern):
  ```bash
  # seed one source, then:
  uv run python -m ingest.cli run
  # verify in psql: HTML tags absent in first_paragraph, idempotent re-run
  ```
- **Clustering / labeling / scoring PRs:** seed prerequisites or use fixture data; run the CLI; inspect the rows produced.

The smoke test does not need to cover edge cases — that is the test suite's job. It needs to prove the happy path actually works on real Postgres + real dependencies, not just in the reader's mental model.

Record a brief smoke summary in the review. The author and the next reviewer should be able to see what was actually run.

### Phase 5 — Write the review

Use this structure. It maps directly to how authors action the feedback.

```markdown
## Verdict

[1-2 sentences. Approve, request changes, or note progress for follow-up review.]

## Resolved (re-review only)

[Items confirmed fixed since the previous review. Acknowledge progress.]

## Required (must fix)

### 1. <short title> — `path/to/file.py:<line>`

[Why it is wrong, citing docs.]
[Concrete fix as code.]

## Discussion (decide in this thread)

[Open questions where the author should confirm intent.]

## Known limitations (note and move on)

[What cannot be fixed here without scope expansion.]

## Nits (defer if you want)

## Re-review checklist

- [ ] <verifiable item 1>
- [ ] <verifiable item 2>
- [ ] Smoke test command(s) the author should run before re-requesting

## Smoke test (only when approving)

[What you ran and what it produced. Brief.]
```

Post via:

```bash
# initial review or follow-up:
gh pr review <N> --comment --body-file /tmp/pr<N>_review.md

# request changes (only on PRs not authored by you):
gh pr review <N> --request-changes --body-file /tmp/pr<N>_review.md

# approval:
gh pr review <N> --approve --body-file /tmp/pr<N>_review.md
```

GitHub blocks `--request-changes` and `--approve` on your own PRs. Use `--comment` for self-PRs and the body itself signals the verdict.

Do **not** add `Co-Authored-By: Claude` or `🤖 Generated with [Claude Code]` footers to review bodies, commits, or PR descriptions. Project convention: no AI attribution in artifacts that ship.

## Re-review (follow-up)

When the author pushes fixes, do a focused re-review:

1. **Refresh the branch:** `git fetch origin pull/<N>/head:pr<N> -f`.
2. **Verify each previous Required item one by one** with explicit grep / read commands. Mark each ✅ or ❌ in the new review body. Do not assume "they probably fixed it."
3. **Re-check PR body claims.** New body changes can introduce new false claims.
4. **Re-run smoke tests** if the diff touches runtime behavior.
5. **Categorize remaining issues** the same way as the first review.

A re-review that says "looks good now" without per-item verification is not a review.

## Categorization rules of thumb

When in doubt about which category a finding belongs to, ask:

- **Will the next batch / next deploy fail because of this?** → Required.
- **Is the code working but possibly wrong by intent?** → Discussion.
- **Is this fixable only by changing scope or upstream data?** → Known limitation.
- **Will a reader's eye twitch but no behavior change matters?** → Nit.

The categories are also a budget. A PR with 12 Required items is not a PR — it is a rewrite request. If you find that many Required issues, recommend the author close and re-open with a tighter scope.

## Specific rules for AI reviewers

- **Never approve a PR you have not smoke-tested.** Code-reading missed bugs in this repo's first reviews; smoke tests caught them. Time spent on a smoke test is cheaper than a production rollback.
- **Never edit code as part of "reviewing."** A review produces feedback, not commits. The author or a separate implementation pass handles the fix.
- **Always re-read this SOP at the start of a review session.** The phases are easy to elide under pressure.
- **Cite docs by path, not from memory.** Memory of doc contents drifts as docs change. `docs/constraints.md §"Schema invariants"` is verifiable; "I remember the docs say..." is not.
- **Do not use force-push or rebase to "resolve conflicts as part of the review."** That is the author's job. Reviewers do not rewrite history on PR branches without explicit user approval.
- **Do not post auto-attributions** ("Generated with Claude Code", "Co-Authored-By: Claude"). Project convention.

## Specific rules for human reviewers

- **Use this SOP even when you wrote the code.** Self-review catches more than peer review for trivial PRs.
- **Apply the categorization honestly.** Marking a Nit as Required to "be safe" creates noise; marking a Required as a Nit lets bugs through.
- **Smoke test on the same machine that runs Postgres.** Local Docker compose is the supported dev environment per `docs/architecture.md`.
- **When you disagree with the SOP**, raise it in `docs/decisions.md` as a new entry rather than skipping a phase silently. The SOP exists to be evolved deliberately.

## What this SOP does not cover

- **Frontend PR review.** Same phases apply, but smoke tests are different (Vite dev server, MSW fixtures). See `docs/frontend.md` for FE-specific concerns.
- **Security review.** Out of scope for this SOP. Use the `/security-review` skill or escalate to the deploy team for auth or infra changes.
- **Performance benchmarking.** Smoke tests verify correctness, not speed. Performance work belongs in a dedicated investigation.
