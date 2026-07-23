# Project Context

## Project Identity

**Vitrin Spain** is a Persian-language Telegram bot for Persian speakers in Spain. It provides Vitrin community listings, the **Hayat Khalvat** community channel flow, a profile area, language-lesson interactions, and **Radar Spain**—a structured feed of useful Spain-related information.

The current product purpose is to help its audience discover and share local information and listings through Telegram. Radar aggregates source-backed opportunities and updates, then routes them through a human review workflow. The repository’s long-term direction is evidenced by reusable Radar content records and documented future uses such as a dashboard, city/category pages, personalized feeds, and notifications; production delivery of those future surfaces requires verification.

## Current Product Areas

- **Vitrin and Hayat Khalvat submissions:** user content creation, admin review, and Telegram-channel publishing flows.
- **Radar Spain:** browsing categories, deep-linked full item pages, channel cards, reactions, and admin-created Radar items.
- **Radar ingestion:** configured source connectors normalize into shared raw-item and candidate processing. BOE is temporarily disabled (its adapter and history are retained); Empleo Público plus the allowlisted 2K Madrid, Keyfactor Spain, and Scopely Spain public Greenhouse boards are active by default.
- **Radar review and promotion:** AI-assisted candidate review, explicit approval, promotion to a ready Radar item, then explicit publication.
- **Language lessons:** generated lesson content with reactions, comments, reports, and discussion mapping.
- **Profiles and dashboard:** user-facing navigation and content/profile views. The primary Telegram navigation is a persistent two-column Reply Keyboard with Home, Radar, ad creation, anonymous messaging, Profile, VIP, Settings, and Help entries; page-specific actions remain inline.

## Current Production Stack

| Component | Repository evidence | State |
| --- | --- | --- |
| Telegram bot | `python-telegram-bot` application uses long polling in `bot.py`. | Implemented but production deployment requires verification. |
| Railway worker | `Procfile` starts `python bot.py`; README documents Railway deployment. | Implemented but production deployment requires verification. |
| PostgreSQL | `DATABASE_URL` is used by the database layer; startup runs additive schema setup. | Implemented but production connectivity requires verification. |
| AI provider integration | Configurable Gemini (default) or OpenAI providers support structured Radar summary and classification. | Implemented but provider credentials/quota behavior requires verification. |
| Scheduler | Bot lifecycle starts an in-process Radar scheduler unless disabled; it also uses a PostgreSQL advisory lock. | Implemented but production scheduling requires verification. |
| Source ingestion | BOE is disabled by configuration; enabled Job connectors use official/public API, RSS, Atom, or a bounded stable official listing. | Implemented; each external source requires operational verification. |
| Review workflow | Radar candidates can be reviewed by admins and promoted only after approval. | Implemented but production workflow evidence is incomplete. |
| Channel publishing | Explicit Radar publication sends to the configured Vitrin channel with duplicate/attempt safeguards. | Implemented; a production-reported send failure is tracked in `KNOWN_ISSUES.md`. |

## Current State

Status labels in this file distinguish repository evidence from production evidence:

- **Production:** only use when direct production evidence is recorded.
- **Implemented but unverified in production:** code and tests/documentation establish the capability, but this repository does not prove it is operating in production.
- **In progress:** active unresolved implementation or diagnostic work.
- **Blocked:** work cannot proceed with the currently supported access or source.
- **Planned:** documented direction not yet delivered as a verified capability.

At the last review (2026-07-20), this repository supports the implemented-but-unverified capabilities listed above. `KNOWN_ISSUES.md` records three production-reported observations that are not confirmed by repository code.

## Non-negotiable Product Rules

- **Admin Review:** ordinary Radar content must pass human Admin Review before promotion/publication.
- **No automatic ordinary publication:** scheduler work may ingest, process, and queue content, but ordinary content is not auto-published. The narrowly gated urgent-alert path is disabled by default and falls back to review when checks fail.
- **Source provenance:** retain source identity and canonical URL through source ingestion and candidate processing.
- **Backward compatibility:** preserve existing schemas, flows, and Telegram callback formats unless a compatible migration is explicitly included.
- **Persian UX:** user-facing navigation and Radar rendering are Persian-first.
- **BOE full details:** BOE AI enrichment persistently stores the complete Persian translation in structured data. Admin/user detail views select that Persian field, split long text safely, and show a clear Persian pending message instead of presenting Spanish as Persian when translation is unavailable.
- **Full detail vs. Job list card:** public Job overviews are mobile-first and limited to the Persian title, city, and—only when deterministically verified—the sponsorship badge. Job detail pages show the richer company, location, optional sponsorship/salary/work-mode, description, skills, deadline, source, and functional navigation actions. Admin Review retains its fuller evidence-bearing presentation.
- **Confirmed sponsorship Jobs:** a Job can enter Admin Review only when AI extraction returns `visa_sponsorship = YES`, includes a verbatim evidence excerpt, and deterministic normalization matches that excerpt against the original candidate title/body. `NO`, `UNKNOWN`, probable support, relocation, English-friendly work, international-company status, foreigner suitability, or applying from abroad are insufficient.
- **Review and publication remain separate:** confirmed sponsorship changes Job eligibility and presentation only. Admin approval, promotion to a ready item, and explicit publication remain independent actions.
- **Restricted sources:** do not bypass access controls, scrape protected sites, automate browsers, solve CAPTCHAs, or use undocumented endpoints.

## Current Environment

The repository documents a Railway **worker** deployment using `python bot.py`, long polling, Telegram credentials, a PostgreSQL `DATABASE_URL`, configured Telegram channel/admin identifiers, and optional AI/source/scheduler settings. `init_db()` runs during bot startup and creates/extends tables additively. Secrets are supplied through environment variables and must not be committed. Actual Railway topology, active variable values, worker count, channel permissions, and production health require production verification.
