# Codex and Contributor Instructions

## Required reading and source of truth

Before changing this repository, read `AGENTS.md`, `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`, `ROADMAP.md`, and `KNOWN_ISSUES.md`. Read `DECISIONS.md` and the relevant parts of `README.md` when planning implementation. These repository files are the project source of truth; do not rely on previous Local or Cloud chat history.

Confirm facts from the current code, Git history, tests, and documented operational evidence. Label anything not proven by those sources as requiring production verification. Never claim production verification without evidence.

## Change rules

- Preserve backward compatibility unless explicitly instructed otherwise.
- Reuse the existing architecture and shared Radar pipeline; do not introduce a parallel job pipeline.
- Do not create fake, placeholder, or non-functional integrations.
- Do not bypass Admin Review or publishing safeguards. Ordinary Radar content must not be automatically published.
- Do not alter Telegram callback formats without migration compatibility.
- Preserve source provenance and Persian-first UX, including the distinction between full bot detail pages and concise channel content.
- Keep pull requests focused and small. Do not mix unrelated refactors with a feature or fix.
- Never commit secrets, credentials, tokens, connection strings, or production data.
- Do not change database behavior, production behavior, or deployment configuration unless the task explicitly requires it.

## Validation and reporting

- Run relevant tests and `git diff --check` before requesting review.
- Check Markdown links and referenced repository paths when documentation changes.
- Clearly report every test or check that could not run and why.
- Report repository evidence separately from production-reported evidence.

## Documentation maintenance workflow

Update the documentation in the same PR whenever architecture, behavior, environment variables, known bugs, feature status, or roadmap status changes:

- Architecture change → `ARCHITECTURE.md` and `DECISIONS.md`
- New or removed environment variable → `PROJECT_CONTEXT.md` and `README.md`
- Bug discovered or fixed → `KNOWN_ISSUES.md`
- Feature completed, blocked, or reprioritized → `ROADMAP.md`
- Product behavior or UX rule changed → `PROJECT_CONTEXT.md`
- Development rule changed → `AGENTS.md`

For every PR, determine whether each file below needs an update. If none does, the PR summary must explicitly state **`Documentation impact: none`**.

```text
Documentation impact:

- [ ] AGENTS.md
- [ ] PROJECT_CONTEXT.md
- [ ] ARCHITECTURE.md
- [ ] ROADMAP.md
- [ ] KNOWN_ISSUES.md
- [ ] DECISIONS.md
- [ ] README.md
- [ ] None

Reason:
```
