# Controlled LeadContact port — V4.2

The Site remains owner-private. Sites dispatch owns caller authentication; the
worker exposes no send tool, arbitrary HTTP tool, SQL tool, or credential tool.
No LeadContact key is bundled. MCP_PAID_ENABLED defaults to false and the secret
is absent. Changing either is an operator action, not a model-callable tool.

## Implemented

- Original records/api_calls and new paid_requests share the daily Shanghai
  200-credit hard budget. Plan 100 remains a planning target.
- Search reserves 100 (5 per returned person, known maximum 20); email reserves10.
  A query plan protects at least 10 extra credits for email and expires in30min.
- Single conditional SQL reservation checks historical/new unknown requests and
  total committed/reserved credits atomically. Only the insert winner may call API.
- Responses persist before balance settlement. Network or billing ambiguity stops
  new paid work without expiring/releasing unknown reservations automatically.
- Exact successful caches can be read without network/key/enabled flag, with
  source_day disclosed. Same search query is not refreshed automatically.
- Daily source review must match imported master ID/version/hash. A newer master
  blocks until its data is synchronized; API tools do not fetch Library themselves.
- Reviewed Work evidence is trusted input, not an independent website fetch.
  Email gates require official company/task, current personal profile, today's
  current-employment evidence, high responsibility match and complete bilingual copy.
- Corporate personal mail only, no shared/free/invalid addresses; cached mailbox
  validity older than30days is held for operator review without auto repurchase.
- One company/group claim, stable request ID and atomic pack write protect against
  repeat enrichment. Crash after completed API can resume using cache; ambiguous
  API/billing requires operator reconciliation. No automatic SMTP or followup.

## Tool sequence

Read current master via Library, get_connector_status and get_work_queue.
confirm_master_review or plan_people_search.review.master_review records actual
observed version/hash, today's Shanghai date and coverage gaps (never claim a full
mailbox history check if unavailable). Plan requires review.pool, history_reviewed,
business_query_reviewed and reason. execute_people_search uses only plan_id.
prepare_personal_email_pack uses stable request_id, account, person,
employment_evidence, retrieved_urls, bilingual copy and target_match.

Supported search fields are the existing adopted location/currentTitlesOnly,
includeRelatedJobTitles,industry,companySize,jobTitle,nextPageToken. Only adopted
industry enums and previously used size enums are accepted; omit size to avoid an
unjustified hard employee cap. New company/seniority/exclusion/page-size parameters
remain disabled pending official schema verification. Pagination tokens must come
from actual stored responses. China-outbound and channel-market gates remain.

## Verification boundary

Run node scripts/test-paid.mjs and node scripts/test-migration.mjs. The paid test
harness forbids actual fetch and uses an isolated SQLite adapter for D1 semantics;
it is not a real LeadContact response, Cloudflare concurrency load test or daily
end-to-end run. TypeScript check and production build are separate checks.

Real API documentation could not be fetched during this turn. Transport uses the
previously tested Python endpoints and response contract; no new API fields or
billing assumptions were inferred from inaccessible docs. Before enabling live,
configure the server secret with native Sites tools, get explicit capped test
spending authorization, verify current master/history and run that capped test.
Current real daily history already includes10credits; this port must not reset it.
