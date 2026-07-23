# Known Issues

## KIB-005 — Some requested official Job sources have no supported ingestion endpoint

- **Status:** Open / blocked by upstream access.
- **Affected subsystem:** Radar Job source expansion.
- **Observed behavior:** EURES requires partner/public-employment-service access; Barcelona Activa and the Generalitat/SOC public vacancy experiences do not expose a documented stable public vacancy API or feed verified for this release.
- **Current safeguard:** The sources are visible as inactive in Admin source status and have no adapter. No private API, browser automation, CAPTCHA bypass, or restricted scraping is attempted.
- **Next step:** Reassess only when the source publishes a documented supported endpoint.

This register contains only issues supported by repository evidence or explicitly labeled production-reported observations. A report is not proof of root cause or current production state. Last reviewed: **2026-07-20**.

## KIB-004 — BOE full-detail view displayed the Spanish source body

- **Status:** Resolved in `feature/fix-boe-full-description-persian`; production deployment verification pending.
- **Severity:** Medium (Persian-first UX regression).
- **Affected subsystem:** BOE AI enrichment → Admin Review / Radar detail rendering.
- **Observed behavior:** BOE items reached Admin Review, but full-detail actions rendered the Spanish candidate/radar body under the full-description section.
- **Root cause:** The AI schema generated only a Persian headline, short summary, and importance reason. Promotion correctly preserved the Spanish body, while detail renderers had no persistent full Persian field and therefore selected `body`/`original_text`.
- **Fix:** The existing AI stage now stores `structured_data.full_text_fa` for BOE candidates; review and detail views select it, show a Persian pending fallback when absent, and split long output safely without changing callback formats.
- **Preserved data:** Spanish candidate body, promoted `body`, `original_text`, source URL, metadata, review lifecycle, and publication lifecycle remain unchanged.
- **Verification:** Regression tests cover translated-field selection, missing translation, long splitting, promotion preservation, and existing detail callback routing.
- **Last verified date:** 2026-07-21 (repository tests; production deployment not yet verified).

## KIB-001 — Job raw items may not progress into candidate creation

- **Status:** Open — production verification and diagnosis required.
- **Severity:** High (if reproduced).
- **Affected subsystem:** Job-source ingestion → raw storage → candidate pipeline.
- **Observed behavior:** A previously reported production run logged `madrid_empleo fetched=10 normalized=10 inserted=10`; later scheduler metrics reported `Candidate created=0`, `Actionability evaluated=0`, `AI processed=0`, and `Queued for review=0`.
- **Evidence:** Production-reported metrics supplied with this documentation task. Repository code shows raw storage and candidate processing as separate stages (`radar_engine/source_manager.py`, `radar_engine/pipeline/engine.py`, `radar_engine/scheduler.py`), but contains no captured production row/log evidence for that run.
- **Suspected cause:** Unconfirmed. Possibilities must be tested against the reported raw rows, their `ingestion_status`, source-registry availability, candidate pipeline errors, scheduler lock/cycle context, and actionability results; none is established by the repository alone.
- **Production impact:** Newly stored job records may remain unavailable for AI, review, and publication until they progress or are handled manually.
- **Workaround:** Use the non-publishing `scripts/run_radar_pipeline.py` only after inspecting the target database and confirming it is safe; do not claim it fixes the underlying cause.
- **Next diagnostic or fix action:** Correlate source metrics with `radar_raw_items`, `radar_candidates`, source registry, and scheduler logs for the same deployment/cycle.
- **Related branch or PR:** None known in local Git history.
- **Last verified date:** 2026-07-20 (documentation review; production observation itself was not re-verified).

## KIB-002 — Generic Telegram error after approved item entered ready-for-publication queue

- **Status:** Open — production verification and diagnosis required.
- **Severity:** High (publication-blocking for the affected item).
- **Affected subsystem:** Radar approval/promotion/publication and Telegram API.
- **Observed behavior:** A previously reported approved review item produced a generic Telegram error in the ready-for-publication flow.
- **Evidence:** Production-reported observation supplied with this documentation task. The repository has explicit publication validation and durable attempt handling (`radar_engine/publication/engine.py`, `publisher.py`, `storage.py`), but no retained exception payload or production attempt record proving the root cause.
- **Suspected cause:** Unconfirmed. It could arise before or during Telegram send, item validation, channel configuration/permissions, or attempt persistence; repository evidence does not identify one.
- **Production impact:** The affected ready item may not reach the Vitrin channel and may need reconciliation before any retry.
- **Workaround:** Inspect the item’s publication attempt and Telegram/channel state; use reconciliation/release commands only after manual verification described by `scripts/run_radar_publication.py --help`.
- **Next diagnostic or fix action:** Capture the exact Telegram exception, radar item ID, publication-attempt status, channel configuration, and whether a channel message was actually sent.
- **Related branch or PR:** None known in local Git history.
- **Last verified date:** 2026-07-20 (documentation review; production observation itself was not re-verified).

## KIB-003 — Telegram `getUpdates` conflict observed during deployment

- **Status:** Needs production verification; not confirmed as an active defect.
- **Severity:** Medium while present (polling can be interrupted).
- **Affected subsystem:** Telegram long polling and Railway deployment lifecycle.
- **Observed behavior:** A `getUpdates` conflict was previously observed during deployment.
- **Evidence:** Production-reported observation supplied with this documentation task. `bot.py` uses `app.run_polling()`; local Git history includes a Railway production-crash fix (merge PR #46), but neither proves whether the conflict was transient during redeployment or persists.
- **Suspected cause:** Unconfirmed. Concurrent polling processes during deployment are a plausible operational hypothesis, not a repository-confirmed cause.
- **Production impact:** If concurrent pollers exist, Telegram polling updates may fail until only one poller remains.
- **Workaround:** Verify that one Railway worker owns polling after deployment stabilizes; avoid intentionally running a second bot instance with the same token.
- **Next diagnostic or fix action:** Review Railway deployment timing, worker count, and Telegram error logs after a stable deployment. Mark resolved only with evidence that conflicts cease.
- **Related branch or PR:** Merge PR #46 (`35bd41d`) is related to a Railway crash fix, not confirmed to fix this conflict.
- **Last verified date:** 2026-07-20 (documentation review; production observation itself was not re-verified).
