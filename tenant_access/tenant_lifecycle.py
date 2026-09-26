from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4


class Requester(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise AssertionError("protocol method")


class TenantState(StrEnum):
    ACTIVE = "active"
    OFFBOARDING = "offboarding"
    OFFBOARDED = "offboarded"


@dataclass
class TenantAccount:
    tenant_id: str
    user_id: str
    key_id: str
    api_key: str
    state: TenantState
    user_deleted: bool = False
    key_revoked: bool = False


class TenantDirectory:
    def __init__(self, infrai: Requester) -> None:
        self.infrai = infrai
        self.accounts: dict[str, TenantAccount] = {}

    def onboard(
        self,
        *,
        tenant_id: str,
        email: str,
        name: str,
        scopes: list[str],
    ) -> TenantAccount:
        operation_id = str(uuid4())
        key_data = self.infrai.request(
            "POST",
            "/v1/account/keys/create",
            json={
                "name": f"{tenant_id}-creator-key",
                "scopes": scopes,
                "idempotency_key": f"tenant-key-{operation_id}",
            },
        )
        user_data = self.infrai.request(
            "POST",
            "/v1/auth/user/create",
            json={
                "email": email,
                "name": name,
                "metadata": {"tenant_id": tenant_id, "key_id": key_data["key_id"]},
                "mode": "managed",
                "idempotency_key": f"tenant-user-{operation_id}",
            },
        )
        account = TenantAccount(
            tenant_id=tenant_id,
            user_id=user_data["id"],
            key_id=key_data["key_id"],
            api_key=key_data["key_secret"],
            state=TenantState.ACTIVE,
        )
        self.accounts[tenant_id] = account
        return account

    def offboard(self, tenant_id: str) -> TenantAccount:
        account = self.accounts[tenant_id]
        if account.state == TenantState.OFFBOARDED:
            return account

        account.state = TenantState.OFFBOARDING
        if not account.user_deleted:
            self.infrai.request("DELETE", f"/v1/auth/user/delete/{account.user_id}")
            account.user_deleted = True
        if not account.key_revoked:
            self.infrai.request("DELETE", f"/v1/account/keys/revoke/{account.key_id}")
            account.key_revoked = True
        account.state = TenantState.OFFBOARDED
        return account
