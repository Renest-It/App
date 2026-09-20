# Contributing to ReNest

This doc covers how we work day to day: branches, commits, PRs, and how we
review each other's code. It's not a rulebook — it's here so we don't have to
re-decide the same small stuff every week.

## Branches

Name branches `{epic}/{short-description}`, e.g. `e1/verification-email`.

The epic prefix is whatever epic/ticket the work belongs to (matches the
numbering we use in planning). Keep the description short and dash-separated
— it's there so a `git branch` listing is actually readable, not a changelog.

## Commits

- Present tense, imperative mood: `Add email verification`, not `Added email
  verification` or `Adds email verification`. Read it as completing the
  sentence "This commit will ___".
- One logical change per commit. If your commit message needs "and" to
  describe it, it's probably two commits.
- Doesn't need to be fancy — a clear one-liner is fine. Add a body if the
  "why" isn't obvious from the diff.

## Pull requests

**Size.** Keep PRs focused on one logical change. Split large ones when
practical. ~400 lines is a rule of thumb, not a hard limit — generated
migrations, lockfiles, and scaffolds are expected to exceed it, and that's
fine. Use judgment: a 600-line PR that's mostly a generated lockfile is
easier to review than a 200-line PR mixing three unrelated changes.

**Description.** Say what the PR does and why, and link the ticket. If it's
not obvious how to test it, say that too.

## Reviews

**Turnaround.** PRs should normally get an initial review within one
business day when possible. If you're swamped, say so on the PR rather than
letting it sit silently.

**What counts as a review.** Leave at least one substantive comment, or an
explicit approval that shows you actually read the diff. "LGTM" on a PR you
skimmed for five seconds isn't a review — if you approve without comments,
it should be because the change is genuinely small and clean, not because
you didn't look.

## Weekly team meeting

Standing agenda, same three things every week:

1. **What shipped** — merged since last time.
2. **What's next** — what each of us is picking up this week.
3. **What's blocked** — anything stuck on a decision, a review, or someone
   else's work, said out loud so it doesn't rot in a PR thread.

Keep it short. This is a status sync, not a design meeting — if something
needs real discussion, take it offline with the people involved.
