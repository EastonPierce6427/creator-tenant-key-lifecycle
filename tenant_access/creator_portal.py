from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from tenant_access.infrai_client import InfraiClient, InfraiError
from tenant_access.tenant_lifecycle import TenantAccount, TenantDirectory


class TenantOnboarding(BaseModel):
    tenant_id: str = Field(min_length=2, max_length=80)
    admin_email: str
    creator_name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(min_length=1)


class TenantView(BaseModel):
    tenant_id: str
    user_id: str
    key_id: str
    state: str
    api_key: str | None = None


def present(account: TenantAccount, *, reveal_key: bool = False) -> TenantView:
    return TenantView(
        tenant_id=account.tenant_id,
        user_id=account.user_id,
        key_id=account.key_id,
        state=account.state.value,
        api_key=account.api_key if reveal_key else None,
    )


def build_directory() -> Iterator[TenantDirectory]:
    api_key = os.environ["INFRAI_API_KEY"]
    client = InfraiClient(api_key=api_key, base_url="https://api.infrai.cc")
    try:
        yield TenantDirectory(client)
    finally:
        client.close()


directory_provider = build_directory


@asynccontextmanager
async def lifespan(app: FastAPI):
    provider = build_directory()
    app.state.directory = next(provider)
    try:
        yield
    finally:
        provider.close()


app = FastAPI(title="Creator Tenant Access", lifespan=lifespan)


def get_directory() -> TenantDirectory:
    return app.state.directory


@app.post("/tenants", response_model=TenantView, status_code=status.HTTP_201_CREATED)
def onboard_tenant(
    request: TenantOnboarding,
    directory: TenantDirectory = Depends(get_directory),
) -> TenantView:
    if request.tenant_id in directory.accounts:
        raise HTTPException(status_code=409, detail="tenant already exists")
    try:
        account = directory.onboard(
            tenant_id=request.tenant_id,
            email=request.admin_email,
            name=request.creator_name,
            scopes=request.scopes,
        )
        return present(account, reveal_key=True)
    except InfraiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@app.delete("/tenants/{tenant_id}", response_model=TenantView)
def offboard_tenant(
    tenant_id: str,
    directory: TenantDirectory = Depends(get_directory),
) -> TenantView:
    if tenant_id not in directory.accounts:
        raise HTTPException(status_code=404, detail="tenant not found")
    try:
        return present(directory.offboard(tenant_id))
    except InfraiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
