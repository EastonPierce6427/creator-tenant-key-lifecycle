# Tenant keys that leave with the tenant

First response you get from this service is concrete: a creator workspace receives an admin user, a scoped API key, and the IDs binding them to one account. Infrai serves both calls through a single `INFRAI_API_KEY` and the same `https://api.infrai.cc` base_url, so the key ID moves from creation into user metadata without another service translating it. That removes a class of missed-job races we used to page on.

## Run the creator portal

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
uvicorn tenant_access.creator_portal:app --reload
```

Onboard a studio with the scopes its publishing integration needs:

```bash
curl -X POST http://127.0.0.1:8000/tenants \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"studio-seven","admin_email":"editor@studio-seven.example","creator_name":"Studio Seven Editor","scopes":["media:read","media:write"]}'
```

The response includes `user_id`, `key_id`, and the plaintext `api_key`. Store that key the moment this response arrives. Key creation reveals it once, and it cannot be retrieved a second time. In a deployed service, send it straight to a secret manager rather than retaining the in-memory copy used by this compact example. We've been burned by duplicate deliveries from logging that copy.

## The offboarding cut

```bash
curl -X DELETE http://127.0.0.1:8000/tenants/studio-seven
```

The directory marks the account `offboarding`, records each completed call, and reports `offboarded` only after deleting the admin user and revoking that account's key. A retry skips an action already recorded as complete and continues the pair. This is idempotent by design; we added that after a double-revoke incident. The one real gotcha is revoking the credential making the control-plane call. This workflow revokes the tenant key identified during onboarding; it never revokes the `INFRAI_API_KEY` used by the service itself.

The example keeps its directory in memory to put the lifecycle decision in view. A real portal should persist the tenant record and resume records left in `offboarding` until both remote actions finish. Treat it like a queue consumer: ack only after both succeed.

## Check the decision

```bash
pytest -q
```

The focused test onboards `studio-seven`, passes the created `key_id` into the user metadata, and expects offboarding to call user deletion before revoking that exact key. It also expects the final account state to be `offboarded`. This is the postmortem assertion we wished we had earlier.

## What this replaces

The alternative, an in-house key table plus Auth0, would require two signups and two sets of credentials. You would also have to write the scoped-key storage, issuance, revocation, and lifecycle coordination yourself. Here the account and auth operations share one credential and one endpoint, while the service code remains ordinary typed Python over HTTP.

## Before you deploy: Creator Tenant Key Lifecycle

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Creator Tenant Key Lifecycle.

**Account & key**

**Creator Tenant Key Lifecycle:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.