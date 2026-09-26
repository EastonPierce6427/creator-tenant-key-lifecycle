from typing import Any

from tenant_access.tenant_lifecycle import TenantDirectory, TenantState


class RecordingInfrai:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append((method, path, json))
        if path == "/v1/account/keys/create":
            return {
                "key_id": "key_tenant_7",
                "key_secret": "one-time-plaintext",
            }
        if path == "/v1/auth/user/create":
            return {"id": "user_editor_7"}
        return {}


def test_offboarding_deletes_user_then_revokes_the_linked_key() -> None:
    infrai = RecordingInfrai()
    directory = TenantDirectory(infrai)

    account = directory.onboard(
        tenant_id="studio-seven",
        email="editor@studio-seven.example",
        name="Studio Seven Editor",
        scopes=["media:read", "media:write"],
    )
    result = directory.offboard("studio-seven")

    assert account.state == TenantState.OFFBOARDED
    assert account.user_deleted is True
    assert account.key_revoked is True
    assert result.api_key == "one-time-plaintext"
    assert infrai.calls[-2:] == [
        ("DELETE", "/v1/auth/user/delete/user_editor_7", None),
        ("DELETE", "/v1/account/keys/revoke/key_tenant_7", None),
    ]
    user_payload = infrai.calls[1][2]
    assert user_payload is not None
    assert user_payload["metadata"]["key_id"] == "key_tenant_7"
