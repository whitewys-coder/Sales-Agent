"""OAuth-protected Streamable HTTP entrypoint; no local scheduler or mail tools."""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlsplit

import jwt
from jwt import PyJWKClient
from mcp.server.fastmcp import FastMCP
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from .config import Config
from .connector import Connector
from .engine import Engine


def https_setting(name):
    value = os.environ.get(name, '').rstrip('/')
    p = urlsplit(value)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise ValueError(name + ' must be an operator-configured HTTPS URL')
    return value


class JWTVerifier:
    def __init__(self, issuer, resource, jwks_url, subject):
        if not subject:
            raise ValueError('MCP_ALLOWED_SUBJECT required for this single-tenant service')
        self.issuer, self.resource, self.subject = issuer, resource, subject
        self.keys = PyJWKClient(jwks_url, timeout=5)

    async def verify_token(self, token):
        try:
            key = await asyncio.to_thread(self.keys.get_signing_key_from_jwt, token)
            claims = jwt.decode(token, key.key, algorithms=['RS256'],
                                issuer=self.issuer, audience=self.resource,
                                options={'require': ['exp', 'iss', 'aud', 'sub']})
            if claims['sub'] != self.subject:
                return None
            scopes = claims.get('scope', '').split()
            return AccessToken(token=token, client_id=claims.get('client_id', claims['sub']),
                               subject=claims['sub'], scopes=scopes,
                               expires_at=claims['exp'], resource=self.resource)
        except Exception:
            return None  # No token contents or upstream errors in logs or responses.


def require_scope(scope):
    token = get_access_token()
    if token is None or scope not in token.scopes:
        raise PermissionError('Required scope: ' + scope)


def build_server(service, issuer, resource, verifier):
    host = urlsplit(resource).netloc
    mcp = FastMCP('Xeroptix LeadContact', host='0.0.0.0', port=8081,
                  stateless_http=True, json_response=True, max_request_body_size=128000,
                  instructions='Manual sending only. Read connector status first. '
                  'Search requires a reviewed plan; email requires verified company, current '
                  'responsibility match and full English/Chinese copy. Never retry uncertain paid work.',
                  token_verifier=verifier,
                  auth=AuthSettings(issuer_url=issuer, resource_server_url=resource,
                                    required_scopes=['sales:read'], validate_token_resource=True),
                  transport_security=TransportSecuritySettings(
                      enable_dns_rebinding_protection=True,
                      allowed_hosts=[host], allowed_origins=['https://' + host]))
    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    write = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
    paid = ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                           idempotentHint=False, openWorldHint=True)

    @mcp.tool(annotations=read)
    def get_connector_status() -> dict:
        """Read local readiness and ledger summary; does not call LeadContact."""
        require_scope('sales:read')
        return service.status()

    @mcp.tool(annotations=write)
    def save_company_research(record: dict) -> dict:
        """Save researched facts and next action locally. Does not sync the Library master."""
        require_scope('sales:research')
        return service.save_research(record)

    @mcp.tool(annotations=write)
    def plan_people_search(payload: dict, review: dict, email_reserve: int) -> dict:
        """Review and save an expiring query plan without contacting LeadContact."""
        require_scope('sales:research')
        return service.plan_search(payload, review, email_reserve)

    @mcp.tool(annotations=paid)
    def execute_people_search(plan_id: str) -> dict:
        """Spend up to 100 credits on an approved plan, or return cached results. No retry on ambiguity."""
        require_scope('sales:paid')
        return service.search(plan_id)

    @mcp.tool(annotations=paid)
    def prepare_personal_email_pack(request_id: str, account: dict, person: dict,
                                    employment_evidence: list[dict], retrieved_urls: list[str],
                                    copy: dict, target_match: dict) -> dict:
        """Query one matched person's work email (10 credits) and save bilingual pack; never send."""
        require_scope('sales:paid')
        return service.prepare_email(request_id, account, person, employment_evidence,
                                     retrieved_urls, copy, target_match)

    @mcp.tool(annotations=read)
    def get_work_queue() -> dict:
        """Read saved company research and unsent packs for continuation and Library writeback."""
        require_scope('sales:read')
        return {'research': [r for r in service.e.db.all('settings')
                             if r['id'].startswith('connector_research:')],
                'drafts': [d for d in service.e.db.all('drafts') if d.get('status') == 'pending'],
                'canonical_master_synced': False}

    return mcp


def main():
    issuer = https_setting('MCP_ISSUER_URL')
    resource = https_setting('MCP_RESOURCE_URL')
    jwks = https_setting('MCP_JWKS_URL')
    if urlsplit(resource).path != '/mcp':
        raise ValueError('MCP_RESOURCE_URL must use /mcp')
    config = Config.env()
    if config.schedule_enabled or config.mail_sync_enabled:
        raise ValueError('Disable local scheduler and mailbox sync for Work connector')
    if config.mode != 'live' or config.research_backend != 'native':
        raise ValueError('APP_MODE=live and RESEARCH_BACKEND=native required')
    if not Path(config.data_dir, 'live.sqlite3').is_file():
        raise ValueError('Restore original ledger; never create an empty live budget database')
    config.check_live()
    service = Connector(Engine(config), paid_enabled=os.getenv('MCP_PAID_ENABLED', 'false') == 'true')
    verifier = JWTVerifier(issuer, resource, jwks, os.getenv('MCP_ALLOWED_SUBJECT', ''))
    build_server(service, issuer, resource, verifier).run(transport='streamable-http')


if __name__ == '__main__':
    main()
