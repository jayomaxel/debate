import uuid

import pytest

from models.debate import Debate, DebateParticipation
from models.user import User
from services.file_access_service import FileAccessService, PrivateFileNotFound
from tests.test_file_object_authorization import (
    test_media_ticket_is_bound_to_speech_user_and_object as _media_authorization_proof,
    test_support_document_enforces_teacher_and_participant_object_ownership as _support_authorization_proof,
)


pytestmark = [pytest.mark.e2e, pytest.mark.integration]


def test_real_filesystem_support_and_media_authorization(e2e_db, tmp_path, monkeypatch):
    support_case = tmp_path / "support-case"
    support_case.mkdir()
    _support_authorization_proof(
        e2e_db, support_case, monkeypatch
    )
    media_case = tmp_path / "media-case"
    media_case.mkdir()
    _media_authorization_proof(e2e_db, media_case, monkeypatch)


def test_report_pdf_rejects_non_participant(e2e_db, tmp_path, monkeypatch):
    teacher = User(
        id=uuid.uuid4(), account=f"file-t-{uuid.uuid4().hex[:8]}", password_hash="x",
        user_type="teacher", name="Owner", email=f"{uuid.uuid4().hex}@example.test",
    )
    participant = User(
        id=uuid.uuid4(), account=f"file-p-{uuid.uuid4().hex[:8]}", password_hash="x",
        user_type="student", name="Participant", email=f"{uuid.uuid4().hex}@example.test",
    )
    outsider = User(
        id=uuid.uuid4(), account=f"file-o-{uuid.uuid4().hex[:8]}", password_hash="x",
        user_type="student", name="Outsider", email=f"{uuid.uuid4().hex}@example.test",
    )
    report_root = tmp_path / "reports"
    report_root.mkdir()
    report_path = report_root / f"{uuid.uuid4().hex}.pdf"
    report_path.write_bytes(b"%PDF-1.4\n%%EOF")
    debate = Debate(
        id=uuid.uuid4(), topic="Private report", duration=10,
        invitation_code=uuid.uuid4().hex[:6], teacher_id=teacher.id,
        status="completed", report_pdf=str(report_path),
    )
    e2e_db.add_all([teacher, participant, outsider, debate])
    e2e_db.flush()
    e2e_db.add(
        DebateParticipation(
            debate_id=debate.id, user_id=participant.id,
            role="debater_1", stance="positive",
        )
    )
    e2e_db.commit()
    monkeypatch.setattr(FileAccessService, "_report_roots", staticmethod(lambda: (report_root.resolve(),)))
    service = FileAccessService(e2e_db)
    assert service.report_pdf(teacher, str(debate.id)).path == report_path.resolve()
    assert service.report_pdf(participant, str(debate.id)).path == report_path.resolve()
    with pytest.raises(PrivateFileNotFound):
        service.report_pdf(outsider, str(debate.id))
