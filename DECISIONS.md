# Decisions

## 2026-07-23 — Temporarily disable BOE and admit only verified safe source access

- **Context:** Radar needs broader Job coverage, while source access must remain public, stable, and compatible with the shared ingestion pipeline.
- **Decision:** BOE is disabled through source configuration and registry state, without deleting its adapter or historical data. Empleo Público is enabled through its official server-rendered public listing with bounded pagination. EURES, Barcelona Activa, and Generalitat/SOC remain inactive because no documented stable public vacancy endpoint was verified.
- **Consequences:** Empleo Público items use the existing raw-item, deduplication, candidate, AI, classification, sponsorship-evidence, Admin Review, promotion, and publication stages. No LinkedIn ingestion, private endpoint, browser automation, or automatic publication is introduced.

## 2026-07-23 — Operational registry contains ingesting sources, not research placeholders

- **Context:** Listing blocked sources beside active sources in Admin overstated operational Job coverage.
- **Decision:** EURES, Barcelona Activa, and Generalitat/SOC remain in research documentation but are removed from `source_registry`. Add three enabled, allowlisted Greenhouse boards with verified current Spain vacancies: 2K Madrid, Keyfactor Spain, and Scopely Spain.
- **Consequences:** Every newly registered source has a working adapter, deterministic ID, canonical URL, normalization tests, and independent failure handling. The API is public and documented; no authentication or browser automation is used.

Decision records capture repository-supported architectural/product choices. Dates reflect the documented decision or the introducing history where available; they do not assert production rollout.

## ADR-001 — Admin Review remains mandatory for ordinary Radar content

- **Date:** 2026-07-20
- **Status:** Accepted
- **Context:** Source and AI processing can create useful but fallible Radar candidates.
- **Decision:** Require an independent admin review decision before promotion of ordinary Radar candidates; approval remains separate from publishing.
- **Consequences:** Scheduler processing can queue work but does not make ordinary content publishable. Admin review and promotion records provide an audit boundary.

## ADR-002 — Sources normalize into one shared Radar pipeline

- **Date:** 2026-07-18
- **Status:** Accepted
- **Context:** BOE and permitted job sources need consistent validation, provenance, deduplication, actionability, AI, classification, and review.
- **Decision:** Store normalized source records as shared raw items and feed them through the existing Radar candidate pipeline.
- **Consequences:** Connector-specific code remains limited to fetch/normalize; downstream safeguards are reused.

## ADR-003 — No parallel job pipeline

- **Date:** 2026-07-18
- **Status:** Accepted
- **Context:** Job sources add structured attributes but should not bypass Radar quality or review controls.
- **Decision:** Add job fields and presentation additively within the shared Radar pipeline rather than create a separate job-processing/publishing path.
- **Consequences:** Job records use the same candidate, AI, classification, review, promotion, and publication lifecycle.

## ADR-004 — No automatic ordinary channel publication

- **Date:** 2026-07-20
- **Status:** Accepted
- **Context:** Channel messages are user-visible and require editorial control.
- **Decision:** Do not automatically publish ordinary Radar content. A separately gated urgent-alert exception exists, is disabled by default, and falls back to review when any safety check fails.
- **Consequences:** Promotion creates a ready item, not a sent message; ordinary publishing remains an explicit human action.

## ADR-005 — Source provenance is retained

- **Date:** 2026-07-18
- **Status:** Accepted
- **Context:** Users and reviewers need traceability to original source material, including cross-source job matches.
- **Decision:** Preserve source identity/canonical URL and append provenance when records are matched rather than deleting records.
- **Consequences:** Storage and presentations can attribute content; deduplication does not erase original-source context.

## ADR-006 — Structured job data is stored additively

- **Date:** 2026-07-18
- **Status:** Accepted
- **Context:** Job details need richer fields without breaking legacy Radar records or review flows.
- **Decision:** Store structured AI extraction in existing additive JSON/data fields and retain fallback behavior for legacy items.
- **Consequences:** Existing Radar fields and callbacks remain usable while job cards/detail pages can consume richer data.

## ADR-007 — Restricted sources must not be bypassed

- **Date:** 2026-07-18
- **Status:** Accepted
- **Context:** Some job sources lack permitted machine-readable retrieval access.
- **Decision:** Use only public/official API, RSS, or Atom access; do not scrape protected sites, automate browsers, bypass CAPTCHAs, or call undocumented endpoints.
- **Consequences:** EURES, Indeed, LinkedIn Jobs, Barcelona Activa, and unverified local sources remain blocked/not integrated until supported access exists.

## ADR-008 — Documentation lives in the repository, not chat memory

- **Date:** 2026-07-20
- **Status:** Accepted
- **Context:** Future Codex and developer work must be understandable without prior Local or Cloud conversation history.
- **Decision:** Maintain project context, architecture, roadmap, known issues, decisions, and contributor instructions in version-controlled repository files.
- **Consequences:** Every PR must assess documentation impact and update the affected source-of-truth files in the same change.

## ADR-009 — Job Review requires source-verified visa sponsorship

- **Date:** 2026-07-23
- **Status:** Accepted
- **Context:** Mobility, English-language, international-employer, and foreigner-suitability signals can be useful but do not prove that an employer will sponsor a visa.
- **Decision:** Treat a candidate as a Job when any reliable classification, structured-AI, source-category, or candidate-metadata signal identifies it as one. Admit that Job to Admin Review only when structured extraction says `visa_sponsorship = YES`, provides a meaningful verbatim evidence excerpt with explicit English/Spanish support wording, and deterministic normalization matches the excerpt against the original title or body independently. `NO`, `UNKNOWN`, probable support, short generic fragments, and indirect signals do not qualify.
- **Consequences:** The rule is an additive eligibility predicate inside the shared Review boundary. Non-Job behavior, callback formats, Admin Review, approval, promotion, and explicit publication remain unchanged. No broad Opportunity Score threshold is part of this decision.
