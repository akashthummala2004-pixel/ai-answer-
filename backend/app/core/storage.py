"""Persistence: Supabase PostgREST (RLS enforced with the user's JWT) or a local JSON store.

Every table shares one shape: id, user_id, created_at, updated_at, payload (jsonb).
Records are returned flattened as {**payload, "id", "created_at", "updated_at"}.
"""

import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import httpx
from fastapi import Depends

from app.core.auth import CurrentUser, get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import StorageError

_META_KEYS = ("id", "created_at", "updated_at")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def _flatten(row: dict[str, Any]) -> dict[str, Any]:
    record = dict(row.get("payload") or {})
    for key in _META_KEYS:
        record[key] = row.get(key)
    return record


def _strip_meta(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in _META_KEYS}


class Repository(Protocol):
    backend: str

    async def list(self, table: str, limit: int = 500) -> list[dict[str, Any]]: ...
    async def get(self, table: str, record_id: str) -> dict[str, Any] | None: ...
    async def create(self, table: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def update(self, table: str, record_id: str, payload: dict[str, Any]) -> dict[str, Any] | None: ...
    async def delete(self, table: str, record_id: str) -> bool: ...


class LocalRepository:
    """JSON-file store for offline development. Not intended for production use."""

    backend = "local"
    _lock = threading.Lock()

    def __init__(self, data_dir: str, user_id: str):
        self.data_dir = Path(data_dir)
        self.user_id = user_id

    def _path(self, table: str) -> Path:
        return self.data_dir / f"{table}.json"

    def _read(self, table: str) -> list[dict[str, Any]]:
        path = self._path(table)
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise StorageError(f"Local data file {path.name} is unreadable.") from exc

    def _write(self, table: str, rows: list[dict[str, Any]]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self._path(table)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def _list_sync(self, table: str, limit: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = [r for r in self._read(table) if r["user_id"] == self.user_id]
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        return [_flatten(r) for r in rows[:limit]]

    def _get_sync(self, table: str, record_id: str) -> dict[str, Any] | None:
        with self._lock:
            for row in self._read(table):
                if row["id"] == record_id and row["user_id"] == self.user_id:
                    return _flatten(row)
        return None

    def _create_sync(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        row = {"id": str(uuid.uuid4()), "user_id": self.user_id, "created_at": now, "updated_at": now,
               "payload": _strip_meta(payload)}
        with self._lock:
            rows = self._read(table)
            rows.append(row)
            self._write(table, rows)
        return _flatten(row)

    def _update_sync(self, table: str, record_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            rows = self._read(table)
            for row in rows:
                if row["id"] == record_id and row["user_id"] == self.user_id:
                    row["payload"] = _strip_meta(payload)
                    row["updated_at"] = _now()
                    self._write(table, rows)
                    return _flatten(row)
        return None

    def _delete_sync(self, table: str, record_id: str) -> bool:
        with self._lock:
            rows = self._read(table)
            kept = [r for r in rows if not (r["id"] == record_id and r["user_id"] == self.user_id)]
            if len(kept) == len(rows):
                return False
            self._write(table, kept)
        return True

    async def list(self, table: str, limit: int = 500) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_sync, table, limit)

    async def get(self, table: str, record_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_sync, table, record_id)

    async def create(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._create_sync, table, payload)

    async def update(self, table: str, record_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._update_sync, table, record_id, payload)

    async def delete(self, table: str, record_id: str) -> bool:
        return await asyncio.to_thread(self._delete_sync, table, record_id)


class SupabaseRepository:
    """PostgREST access using the signed-in user's JWT so Row Level Security applies."""

    backend = "supabase"

    def __init__(self, settings: Settings, access_token: str):
        self.base = f"{settings.supabase_url.rstrip('/')}/rest/v1"
        self.timeout = settings.supabase_timeout_seconds
        self.headers = {
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def _request(self, method: str, table: str, params: dict[str, str] | None = None,
                       body: Any = None) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, f"{self.base}/{table}", headers=self.headers,
                                                params=params, json=body)
        except httpx.HTTPError as exc:
            raise StorageError(f"Supabase is unreachable ({exc.__class__.__name__}).") from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("message", response.text[:200])
            except ValueError:
                detail = response.text[:200]
            raise StorageError(f"Supabase error ({response.status_code}): {detail}")
        return response.json() if response.content else []

    async def list(self, table: str, limit: int = 500) -> list[dict[str, Any]]:
        rows = await self._request("GET", table, {"select": "*", "order": "created_at.desc", "limit": str(limit)})
        return [_flatten(r) for r in rows]

    async def get(self, table: str, record_id: str) -> dict[str, Any] | None:
        if not _valid_uuid(record_id):
            return None
        rows = await self._request("GET", table, {"select": "*", "id": f"eq.{record_id}"})
        return _flatten(rows[0]) if rows else None

    async def create(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = await self._request("POST", table, body={"payload": _strip_meta(payload)})
        return _flatten(rows[0])

    async def update(self, table: str, record_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not _valid_uuid(record_id):
            return None
        rows = await self._request("PATCH", table, {"id": f"eq.{record_id}"},
                                   body={"payload": _strip_meta(payload), "updated_at": _now()})
        return _flatten(rows[0]) if rows else None

    async def delete(self, table: str, record_id: str) -> bool:
        if not _valid_uuid(record_id):
            return False
        rows = await self._request("DELETE", table, {"id": f"eq.{record_id}"})
        return bool(rows)


def get_repository(
    user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Repository:
    if settings.supabase_enabled and user.access_token:
        return SupabaseRepository(settings, user.access_token)
    return LocalRepository(settings.local_data_dir, user.id)
