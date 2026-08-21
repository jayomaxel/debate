import uuid
from datetime import datetime

import pytest

from models.debate import Debate, DebateParticipation
from models.document import Document
from models.kb_document import KBDocument
from models.speech import Speech
from models.user import User
from services.file_access_service import (
    FileAccessService,
    InvalidMediaTicket,
    PrivateFileNotFound,
)


def _user(db, role: str, name: str) -> User:
    user = User(
        id=uuid.uuid4(),
        account=f"{name}_{uuid.uuid4().hex[:8]}",
        password_hash="hashed",
        user_type=role,
        name=name,
        email=f"{uuid.uuid4().hex}@example.test",
    )
    db.add(user)
    db.flush()
    return user


def _debate(db, teacher: User) -> Debate:
    debate = Debate(
        id=uuid.uuid4(),
        topic="private file authorization",
        duration=30,
        invitation_code=uuid.uuid4().hex[:6],
        teacher_id=teacher.id,
        status="completed",
    )
    db.add(debate)
    db.flush()
    return debate


def _participant(db, debate: Debate, student: User, role: str = "debater_1") -> None:
    db.add(
        DebateParticipation(
            debate_id=debate.id,
            user_id=student.id,
            role=role,
            stance="positive" if role in {"debater_1", "debater_2"} else "negative",
        )
    )
    db.flush()


def test_support_document_enforces_teacher_and_participant_object_ownership(
    db_session,
    tmp_path,
    monkeypatch,
):
    owner = _user(db_session, "teacher", "owner")
    other_teacher = _user(db_session, "teacher", "other_teacher")
    participant = _user(db_session, "student", "participant")
    outsider = _user(db_session, "student", "outsider")
    debate = _debate(db_session, owner)
    _participant(db_session, debate, participant)
    support_root = tmp_path / "support"
    support_root.mkdir()
    stored = support_root / f"{uuid.uuid4().hex}.pdf"
    stored.write_bytes(b"private support")
    document = Document(
        debate_id=debate.id,
        filename="lesson.pdf",
        file_path=str(stored),
        file_type="application/pdf",
    )
    db_session.add(document)
    db_session.commit()
    monkeypatch.setattr(
        FileAccessService,
        "_support_roots",
        staticmethod(lambda: (support_root.resolve(),)),
    )

    service = FileAccessService(db_session)
    assert service.support_document(owner, str(debate.id), str(document.id)).path == stored.resolve()
    assert service.support_document(participant, str(debate.id), str(document.id)).path == stored.resolve()
    for forbidden_user in (other_teacher, outsider):
        with pytest.raises(PrivateFileNotFound):
            service.support_document(forbidden_user, str(debate.id), str(document.id))
    with pytest.raises(PrivateFileNotFound):
        service.support_document(owner, str(uuid.uuid4()), str(document.id))


def test_knowledge_document_requires_explicit_publication(db_session, tmp_path, monkeypatch):
    student = _user(db_session, "student", "student")
    admin = db_session.query(User).filter(User.user_type == "administrator").first()
    kb_root = tmp_path / "kb"
    kb_root.mkdir()
    stored = kb_root / f"{uuid.uuid4().hex}.pdf"
    stored.write_bytes(b"global knowledge")
    document = KBDocument(
        filename="global.pdf",
        file_path=str(stored),
        file_type="application/pdf",
        file_size=stored.stat().st_size,
        upload_status="completed",
        is_published=False,
        uploaded_by=admin.id,
    )
    db_session.add(document)
    db_session.commit()
    monkeypatch.setattr(
        FileAccessService,
        "_kb_roots",
        staticmethod(lambda: (kb_root.resolve(),)),
    )
    service = FileAccessService(db_session)

    with pytest.raises(PrivateFileNotFound):
        service.knowledge_document(student, str(document.id))
    assert service.knowledge_document(admin, str(document.id)).path == stored.resolve()
    document.is_published = True
    db_session.commit()
    assert service.knowledge_document(student, str(document.id)).path == stored.resolve()


def test_private_path_rejects_traversal_and_outside_absolute_path(tmp_path):
    root = tmp_path / "private"
    root.mkdir()
    outside = tmp_path / "secret.pdf"
    outside.write_bytes(b"secret")

    with pytest.raises(PrivateFileNotFound):
        FileAccessService.resolve_private_path(root / ".." / "secret.pdf", (root,))
    with pytest.raises(PrivateFileNotFound):
        FileAccessService.resolve_private_path(outside, (root,))


def test_media_ticket_is_bound_to_speech_user_and_object(db_session, tmp_path, monkeypatch):
    teacher = _user(db_session, "teacher", "teacher")
    participant = _user(db_session, "student", "participant")
    outsider = _user(db_session, "student", "outsider")
    debate = _debate(db_session, teacher)
    _participant(db_session, debate, participant)
    upload_root = tmp_path / "uploads"
    audio_root = upload_root / "audio"
    audio_root.mkdir(parents=True)
    object_name = f"{uuid.uuid4().hex}.wav"
    stored = audio_root / object_name
    stored.write_bytes(b"RIFF-private-audio")
    speech = Speech(
        debate_id=debate.id,
        speaker_id=participant.id,
        speaker_type="human",
        speaker_role="debater_1",
        phase="opening",
        content="hello",
        audio_url=f"/uploads/audio/{object_name}",
        duration=1,
        timestamp=datetime.utcnow(),
    )
    db_session.add(speech)
    db_session.commit()
    monkeypatch.setattr(
        FileAccessService,
        "_configured_upload_root",
        staticmethod(lambda: upload_root.resolve()),
    )
    service = FileAccessService(db_session)

    object_key, authorized_speech = service.authorize_media_reference(participant, speech.audio_url)
    assert str(authorized_speech.id) == str(speech.id)
    with pytest.raises(PrivateFileNotFound):
        service.authorize_media_reference(outsider, speech.audio_url)

    ticket = FileAccessService.issue_media_ticket(
        user_id=str(participant.id),
        object_key=object_key,
        speech_id=str(speech.id),
    )
    resolved = service.resolve_ticketed_media(ticket, object_key)
    assert resolved.path == stored.resolve()
    with pytest.raises((InvalidMediaTicket, PrivateFileNotFound)):
        service.resolve_ticketed_media(ticket, f"audio/{uuid.uuid4().hex}.wav")

    participation = (
        db_session.query(DebateParticipation)
        .filter(DebateParticipation.debate_id == debate.id)
        .filter(DebateParticipation.user_id == participant.id)
        .first()
    )
    participation.left_at = datetime.utcnow()
    db_session.commit()
    with pytest.raises(InvalidMediaTicket):
        service.resolve_ticketed_media(ticket, object_key)


def test_random_object_names_do_not_include_original_basename():
    generated = FileAccessService.random_object_name("student-name-debate-42.wav")

    assert generated.endswith(".wav")
    assert "student-name" not in generated
    assert len(generated.removesuffix(".wav")) == 32


def test_provider_ticket_only_reads_bound_asr_object(db_session, tmp_path, monkeypatch):
    upload_root = tmp_path / "uploads"
    asr_root = upload_root / "asr"
    asr_root.mkdir(parents=True)
    object_name = f"{uuid.uuid4().hex}.wav"
    stored = asr_root / object_name
    stored.write_bytes(b"provider input")
    monkeypatch.setattr(
        FileAccessService,
        "_configured_upload_root",
        staticmethod(lambda: upload_root.resolve()),
    )
    object_key = f"asr/{object_name}"
    ticket = FileAccessService.issue_media_ticket(
        user_id="asr-provider",
        object_key=object_key,
        provider_only=True,
    )

    assert FileAccessService(db_session).resolve_ticketed_media(ticket, object_key).path == stored.resolve()
    with pytest.raises((InvalidMediaTicket, PrivateFileNotFound)):
        FileAccessService(db_session).resolve_ticketed_media(
            ticket,
            f"asr/{uuid.uuid4().hex}.wav",
        )
