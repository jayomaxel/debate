"""Database authority for realtime room state and cross-worker CAS updates."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.debate_runtime_state import DebateRuntimeState


class RuntimeStateConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeSnapshot:
    room_id: str
    debate_id: str
    state: dict[str, Any]
    version: int
    lease_owner: Optional[str] = None
    lease_expires_at: Optional[datetime] = None


class RuntimeStateStore:
    CORE_DEADLINE_FIELDS = {
        "phase_start_time",
        "segment_start_time",
        "mic_expires_at",
        "playback_gate_deadline_at",
        "timer_paused_at",
        "sub_timer_started_at",
    }

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _snapshot(row: DebateRuntimeState) -> RuntimeSnapshot:
        return RuntimeSnapshot(
            room_id=str(row.room_id),
            debate_id=str(row.debate_id),
            state=dict(row.state or {}),
            version=int(row.version or 0),
            lease_owner=row.lease_owner,
            lease_expires_at=row.lease_expires_at,
        )

    def load(self, room_id: str, *, for_update: bool = False) -> Optional[RuntimeSnapshot]:
        statement = select(DebateRuntimeState).where(DebateRuntimeState.room_id == str(room_id))
        if for_update:
            statement = statement.with_for_update()
        row = self.db.execute(statement).scalar_one_or_none()
        return self._snapshot(row) if row else None

    def ensure(self, room_id: str, debate_id: str, state: dict[str, Any]) -> RuntimeSnapshot:
        existing = self.load(room_id)
        if existing:
            if existing.debate_id != str(debate_id):
                raise RuntimeStateConflict("room id belongs to another debate")
            return existing
        try:
            row = DebateRuntimeState(
                room_id=str(room_id),
                debate_id=uuid.UUID(str(debate_id)),
                state=dict(state),
                version=0,
            )
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
            return self._snapshot(row)
        except IntegrityError:
            self.db.rollback()
            existing = self.load(room_id)
            if not existing or existing.debate_id != str(debate_id):
                raise RuntimeStateConflict("runtime state creation raced with another debate")
            return existing

    def compare_and_set(
        self,
        room_id: str,
        expected_version: int,
        state: dict[str, Any],
    ) -> Optional[RuntimeSnapshot]:
        result = self.db.execute(
            update(DebateRuntimeState)
            .where(DebateRuntimeState.room_id == str(room_id))
            .where(DebateRuntimeState.version == int(expected_version))
            .values(
                state=dict(state),
                version=int(expected_version) + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )
        if result.rowcount != 1:
            self.db.rollback()
            return None
        self.db.commit()
        return self.load(room_id)

    def mutate(
        self,
        room_id: str,
        mutation: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> RuntimeSnapshot:
        snapshot = self.load(room_id, for_update=True)
        if not snapshot:
            self.db.rollback()
            raise RuntimeStateConflict("runtime state does not exist")
        row = self.db.execute(
            select(DebateRuntimeState)
            .where(DebateRuntimeState.room_id == str(room_id))
            .with_for_update()
        ).scalar_one()
        row.state = dict(mutation(dict(snapshot.state)))
        row.version = snapshot.version + 1
        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return self._snapshot(row)

    def patch(self, room_id: str, changes: dict[str, Any]) -> RuntimeSnapshot:
        return self.mutate(room_id, lambda current: {**current, **changes})

    def claim_mic(
        self,
        room_id: str,
        *,
        user_id: str,
        user_role: str,
        now: datetime,
        ttl_seconds: int,
    ) -> tuple[bool, RuntimeSnapshot, str]:
        row = self.db.execute(
            select(DebateRuntimeState)
            .where(DebateRuntimeState.room_id == str(room_id))
            .with_for_update()
        ).scalar_one_or_none()
        if not row:
            self.db.rollback()
            raise RuntimeStateConflict("runtime state does not exist")
        state = dict(row.state or {})
        expires_at = self._parse_datetime(state.get("mic_expires_at"))
        comparable_now = now
        if expires_at and expires_at.tzinfo and comparable_now.tzinfo is None:
            comparable_now = comparable_now.replace(tzinfo=expires_at.tzinfo)
        if expires_at and comparable_now < expires_at and (
            state.get("mic_owner_user_id") or state.get("mic_owner_role")
        ):
            self.db.rollback()
            return False, self._snapshot(row), "occupied"
        new_expires_at = now + timedelta(seconds=max(1, int(ttl_seconds)))
        state.update(
            {
                "mic_owner_user_id": str(user_id),
                "mic_owner_role": str(user_role),
                "mic_expires_at": new_expires_at.isoformat(),
                "current_speaker": str(user_role),
                "free_debate_last_side": "human",
                "free_debate_next_side": "human",
            }
        )
        row.state = state
        row.version = int(row.version or 0) + 1
        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return True, self._snapshot(row), "claimed"

    def acquire_lease(
        self,
        room_id: str,
        *,
        owner: str,
        now: datetime,
        ttl_seconds: int = 30,
    ) -> bool:
        row = self.db.execute(
            select(DebateRuntimeState)
            .where(DebateRuntimeState.room_id == str(room_id))
            .with_for_update()
        ).scalar_one_or_none()
        if not row:
            self.db.rollback()
            return False
        expires_at = row.lease_expires_at
        comparable_now = now
        if expires_at and expires_at.tzinfo and comparable_now.tzinfo is None:
            comparable_now = comparable_now.replace(tzinfo=expires_at.tzinfo)
        if expires_at and comparable_now < expires_at and row.lease_owner != owner:
            self.db.rollback()
            return False
        row.lease_owner = owner
        row.lease_expires_at = now + timedelta(seconds=max(1, int(ttl_seconds)))
        self.db.commit()
        return True

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None
