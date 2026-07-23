# Roadmap

> **This file must be updated whenever a PR changes feature status, priorities, blockers or known defects.** It is a living status document, not permanent truth without maintenance.

All items were last reviewed on **2026-07-20**. “Implemented” is repository evidence; it does not assert production operation.

## Completed

| Item | Status | Evidence | Last reviewed | Next action |
| --- | --- | --- | --- | --- |
| Shared Radar raw-to-candidate pipeline and deterministic Actionability Gate | Implemented | `radar_engine/pipeline/engine.py`; merge PR #32 (`61655a2`) | 2026-07-20 | Diagnose KIB-001 against production data before changing pipeline behavior. |
| AI summary, structured job extraction, and controlled classification | Implemented | `radar_engine/ai/`, `radar_engine/classification/`; merges #23–#25 and #40 | 2026-07-20 | Verify provider configuration and queue progress in production. |
| Admin review, approval, promotion, and guarded publication lifecycle | Implemented | `radar_engine/review/`, `promotion/`, `publication/`; merges #37–#39 | 2026-07-20 | Diagnose KIB-002 with Telegram/API error details. |
| BOE adapter plus permitted Job-source adapters | Implemented | BOE retained but temporarily disabled; Empleo Público uses the official bounded public listing. | 2026-07-23 | Smoke-test enabled sources from the target network; re-enable BOE only by explicit configuration. |
| Job freshness/expiration safeguards and concise job channel cards | Implemented | `radar_engine/job_expiration.py`, `job_presentation.py`; merges #39 and #41 | 2026-07-20 | Monitor expiry/review outcomes after production verification. |
| Language-lesson interactive feedback | Implemented | `handlers/language_lessons.py`; merges #43–#46 | 2026-07-20 | Validate live Telegram behavior separately from repository evidence. |
| Source-verified visa sponsorship Job Review | Implemented | `radar_engine/job_sponsorship.py`, AI extraction, Review eligibility, and Job presentation tests | 2026-07-23 | Verify AI evidence quality and Review queue outcomes in production before enabling additional Job categories. |

## In Progress

| Item | Status | Evidence | Last reviewed | Next action |
| --- | --- | --- | --- | --- |
| Diagnose job raw-item to candidate progression | In progress | Production report captured as KIB-001; no root-cause commit/branch is present in local history. | 2026-07-20 | Collect raw-item statuses, source-registry rows, candidate rows, and scheduler logs for the same cycle. |
| Diagnose generic ready-publication Telegram error | In progress | Production report captured as KIB-002; publication safeguards exist but do not prove the reported error’s source. | 2026-07-20 | Preserve the exact Telegram exception, attempt state, and item/channel configuration. |

## Next Priority

| Priority item | Status | Evidence | Last reviewed | Next action |
| --- | --- | --- | --- | --- |
| 1. Establish production evidence for KIB-001 | In progress | `KNOWN_ISSUES.md` KIB-001 | 2026-07-20 | Run non-destructive database/log diagnostics and document results. |
| 2. Establish production evidence for KIB-002 | In progress | `KNOWN_ISSUES.md` KIB-002 | 2026-07-20 | Reproduce only with a safe test item and inspect durable publication attempts. |
| 3. Verify deployment polling ownership | Needs production verification | KIB-003; `bot.py` uses long polling. | 2026-07-20 | Confirm Railway worker count and deployment overlap behavior. |
| 4. Smoke-test opted-in job connectors before activation | Planned | Connector limitations in `radar_engine/source_config.py`. | 2026-07-20 | Use `scripts/run_radar_jobs.py --smoke` from the intended network. |

## Planned

| Item | Status | Evidence | Last reviewed | Next action |
| --- | --- | --- | --- | --- |
| Reusable Radar content beyond the bot (dashboard/city/category/personalized feeds/notifications) | Planned | README describes these as future uses of reusable `radar_items`. | 2026-07-20 | Define a scoped product proposal before implementation. |
| Save and reminder actions in public Radar views | Planned | README identifies these buttons as placeholders. | 2026-07-20 | Specify persistence and notification behavior before replacing placeholders. |
| Broader Job opportunity scoring and additional Job categories | Planned | Explicitly outside the confirmed-sponsorship phase. | 2026-07-23 | Define separate requirements; do not use 60/80 score thresholds in the current phase. |

## Blocked

| Item | Status | Evidence | Last reviewed | Next action |
| --- | --- | --- | --- | --- |
| EURES vacancy ingestion | Blocked | `BLOCKED_SOURCES`: public retrieval API not documented; partner/PES access required. | 2026-07-20 | Obtain supported partner/PES access or keep disabled. |
| Indeed vacancy ingestion | Blocked | `BLOCKED_SOURCES`: Job Sync is an ATS posting API, not public search retrieval. | 2026-07-20 | Do not scrape; use a supported source if one becomes available. |
| LinkedIn Jobs ingestion | Blocked | `BLOCKED_SOURCES`: approved partner access required; no public search ingestion. | 2026-07-20 | Do not scrape; pursue approved access only. |
| Barcelona Activa ingestion | Blocked | `BLOCKED_SOURCES`: no verified public feed/API; search is dynamic/authenticated. | 2026-07-20 | Do not bypass protections; reassess only if an official feed/API appears. |
| Generalitat/SOC vacancy ingestion | Blocked | Official vacancy page identified, but no documented stable machine-readable API/feed was verified. | 2026-07-23 | Reassess only when Generalitat/SOC publishes a supported endpoint. |
| Empleo Público ingestion | Implemented | Bounded parsing of the official server-rendered Administracion.gob.es listing; stable reference IDs, deadlines, organizations, locations, and canonical detail URLs are retained. | 2026-07-23 | Monitor official markup and target-network availability. |

## Technical Debt

| Item | Status | Evidence | Last reviewed | Next action |
| --- | --- | --- | --- | --- |
| Production observability for source-to-candidate and publication failures | In progress | KIB-001/KIB-002 are reports without retained diagnostic evidence in this repository. | 2026-07-20 | Add scoped diagnostics only after confirming requirements and preserving privacy/secrets. |
| Production verification coverage | Needs production verification | Tests cover components, but repository tests cannot prove Telegram, Railway, PostgreSQL, or external source operation. | 2026-07-20 | Maintain a safe operational verification checklist with evidence. |
| Documentation freshness | Ongoing | This knowledge base is introduced by this change. | 2026-07-20 | Apply the `AGENTS.md` PR checklist on every future PR. |
