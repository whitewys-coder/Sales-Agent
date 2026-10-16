# Xeroptix connector implementation status — 2026-10-16

## Two deployment targets, not one interchangeable runtime

The user selected ChatGPT Sites. Sites runs Workers, not this Python server.
The Python adapter is retained as a tested reference/alternative, not installed
inside the workflow Skill and not a workaround for its failed publication scan.

- Python: `sales_agent.connector` is a constrained controller over the original
  ledger; `sales_agent.mcp_server` uses the official MCP Python SDK and an external
  OAuth issuer. Default paid access is off. Six tools, no sending or arbitrary HTTP.
- Sites: a private MCP preflight service uses Workers/D1 and platform identity.
  It implements status, research checkpoints and queue reading. Its three paid
  workflow tools explicitly fail closed. It is NOT a completed port of LeadContact.
- The existing daily Work automation and installed Skill remain the business-rule
  authority. No second scheduler was created and no paid production call was made.

## Python verification

Install `requirements-mcp.txt`, then run `python -m unittest discover -s tests -v`
from this product directory. On 2026-10-16, 45 tests passed, including 12 connector
checks for OAuth boundary, tool annotations, idempotency, unknown requests,
master-sync gating and protected email budget. No Docker or public OAuth deployment
was verified. Paid handlers trust source-reviewed Work submissions; they do not
fetch or independently authenticate website evidence.

## Before Python alternative deployment

Restore the ORIGINAL live.sqlite3 (never initialize an empty budget history),
reconcile against the current Library master, then have the operator record the
Shanghai-day `connector_master_sync` setting with `revision` and
`history_complete=true`. That attestation is not exposed as a model tool.
Record verified API enum values in `connector_supported_search`. Configure an
OAuth issuer with authorization-code/PKCE, discovery and resource-bound RS256
tokens; configure an approved subject and HTTPS reverse proxy. Required scopes:
`sales:read`, `sales:research`, `sales:paid`. The implementation is single-tenant.
Keep the old server/scheduler stopped: the connector must be the only writer to
this ledger. Do not serve the old broad REST API as the connector.

Use `.env.mcp.example` server-side and `compose.mcp.yaml`; protect secret files,
prepare volume permissions for UID10001, and keep MCP_PAID_ENABLED=false until
public authentication, scopes, source history, budget and restart acceptance pass.
A successful Python unit test is not a successful ChatGPT plugin connection.

## Sites next acceptance step

Port original budget reservation, unresolved-request handling, exact request cache,
master/group/history suppression and source-reviewed bilingual email gates to D1.
Import old API calls and sent/frozen history with stable IDs and an explicit import
manifest. Compare counts, day totals, retained unknown reservations and checksums
before enabling API access. Preserve current master Library ID and version checks;
saving local research does not equal canonical master writeback.

Only then configure the LeadContact token through native Sites runtime secrets,
run zero-credit cache/rejection tests and an explicitly authorized capped real
request. Verify a real MCP call from Work, then bind the existing daily task and
Skill to that connection. Do not report a ready daily paid workflow before this.
