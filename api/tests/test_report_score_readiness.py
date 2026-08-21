import uuid
from datetime import datetime

import pytest

from models.debate import Debate, DebateParticipation
from models.score import Score
from models.speech import Speech
from models.user import User
from services.report_orchestration_service import ReportOrchestrationService
from services.report_service import ReportGenerator
from services.scoring_service import ScoringService


@pytest.mark.asyncio
async def test_report_read_does_not_duplicate_running_background_score_job(
    db_session, monkeypatch
):
    student = User(
        id=uuid.uuid4(),
        account="background_report_student",
        name="Background Report Student",
        email="background_report_student@test.com",
        password_hash="hashed_password",
        user_type="student",
        created_at=datetime.utcnow(),
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="Background report ownership",
        description="",
        duration=5,
        invitation_code="RPTBG1",
        status="completed",
        report={
            "__room_meta": {
                "report_job": {"status": "running", "attempts": 1}
            }
        },
    )
    speech = Speech(
        id=uuid.uuid4(),
        debate_id=debate.id,
        speaker_id=student.id,
        speaker_type="human",
        speaker_role="debater_1",
        phase="opening",
        content="This speech is waiting for the background judge task.",
        duration=10,
        is_valid_for_scoring=True,
        timestamp=datetime.utcnow(),
    )
    db_session.add_all([student, debate, speech])
    db_session.commit()

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("report GET must not start a duplicate judge run")

    monkeypatch.setattr(ScoringService, "batch_score_debate", fail_if_called)

    status = await ScoringService.ensure_debate_scored(
        db_session, str(debate.id)
    )

    assert status["generated"] is False
    assert status["ready"] is False
    assert status["report_status"] == "processing"
    assert status["report_job_status"] == "running"


@pytest.mark.asyncio
async def test_report_readiness_scores_missing_valid_speeches(db_session):
    student = User(
        id=uuid.uuid4(),
        account="report_student",
        name="Report Student",
        email="report_student@test.com",
        password_hash="hashed_password",
        user_type="student",
        created_at=datetime.utcnow(),
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="AI in classrooms",
        description="",
        duration=5,
        invitation_code="RPT001",
        status="completed",
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
    )
    participation = DebateParticipation(
        id=uuid.uuid4(),
        debate_id=debate.id,
        user_id=student.id,
        role="debater_1",
        stance="positive",
    )
    speech = Speech(
        id=uuid.uuid4(),
        debate_id=debate.id,
        speaker_id=student.id,
        speaker_type="human",
        speaker_role="debater_1",
        phase="opening",
        content=(
            "First, artificial intelligence can improve classroom efficiency, "
            "and personalized learning helps students understand concepts."
        ),
        duration=18,
        is_valid_for_scoring=True,
        timestamp=datetime.utcnow(),
    )
    db_session.add_all([student, debate, participation, speech])
    db_session.commit()

    assert db_session.query(Score).filter(Score.speech_id == speech.id).count() == 0

    status = await ScoringService.ensure_debate_scored(db_session, str(debate.id))
    db_session.refresh(debate)
    report = ReportGenerator.generate_student_report(
        db_session,
        str(debate.id),
        str(student.id),
    )

    assert status["generated"] is True
    assert status["ready"] is True
    assert debate.report["report_meta"]["provider"] == "llm"
    assert debate.report["report_meta"]["scoring_source"] == "fallback"
    assert debate.report["participant_scores"][0]["rubric_version"] == "a.rubric.v1"
    assert debate.report["evidence_anchors"][0]["turn_id"] == str(speech.id)
    assert debate.report["calibration_summary"]["calibration_version"] == "a.calibration.v1"
    assert db_session.query(Score).filter(Score.speech_id == speech.id).count() == 1
    assert report is not None
    assert report.participants[0]["final_score"]["overall_score"] > 0
    assert report.speeches[0]["score"]["overall_score"] > 0

    report_data = report.to_dict()
    assert report_data["participants"] == report.participants
    assert report_data["speeches"] == report.speeches
    assert report_data["statistics"] == report.statistics
    assert report_data["winner"] == report.winner
    assert report_data["mode"] == "competition"
    assert report_data["domain_pack_id"] == "default"
    assert report_data["report_meta"]["scoring_quality"] == "partial"
    assert report_data["report_meta"]["provider"] == "llm"
    assert report_data["report_meta"]["rubric_version"] == "a.rubric.v1"
    assert report_data["participant_scores"][0]["overall_score"] > 0
    assert report_data["evidence_anchors"][0]["turn_id"] == str(speech.id)
    assert report_data["evidence_anchors"][0]["source_label"] == "Debate speech transcript"
    assert report_data["turning_points"][0]["turn_id"] == str(speech.id)
    assert report_data["team_summary"]["positive"]["participant_count"] == 1
    assert report_data["statistics"]["calibration_summary"]["calibration_version"] == "a.calibration.v1"
    assert "anomaly_samples" in report_data["statistics"]

    meta = ReportOrchestrationService.build_report_meta(db_session, debate)
    assert meta["scoring_source"] == "fallback"
    assert meta["rubric_version"] == "a.rubric.v1"
    assert meta["evidence_anchor_count"] == 1
    assert meta["evidence_sources"][0]["source_type"] == "debate_speech"
    assert meta["evidence_sources"][0]["label"] == "Debate speech transcript"


def test_report_includes_participants_without_speeches(db_session):
    student = User(
        id=uuid.uuid4(),
        account="silent_student",
        name="Silent Student",
        email="silent_student@test.com",
        password_hash="hashed_password",
        user_type="student",
        created_at=datetime.utcnow(),
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="Silent participant debate",
        description="",
        duration=5,
        invitation_code="RPT002",
        status="completed",
    )
    participation = DebateParticipation(
        id=uuid.uuid4(),
        debate_id=debate.id,
        user_id=student.id,
        role="debater_1",
        stance="positive",
    )
    db_session.add_all([student, debate, participation])
    db_session.commit()

    report = ReportGenerator.generate_student_report(
        db_session,
        str(debate.id),
        str(student.id),
    )

    assert report is not None
    assert report.participants[0]["user_id"] == str(student.id)
    assert report.participants[0]["has_speech"] is False
    assert report.participants[0]["score_status"] == "no_speech"
    assert report.participants[0]["final_score"]["speech_count"] == 0
    assert report.statistics["calibration_summary"]["sample_count"] >= 1


def test_report_meta_and_teaching_summary_for_empty_report(db_session):
    teacher = User(
        id=uuid.uuid4(),
        account="summary_teacher",
        name="Summary Teacher",
        email="summary_teacher@test.com",
        password_hash="hashed_password",
        user_type="teacher",
        created_at=datetime.utcnow(),
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="Empty report debate",
        description="",
        duration=5,
        invitation_code="RPT003",
        status="completed",
        teacher_id=teacher.id,
    )
    db_session.add_all([teacher, debate])
    db_session.commit()

    meta = ReportOrchestrationService.build_report_meta(db_session, debate)
    summary = ReportOrchestrationService.build_teaching_summary(db_session, str(debate.id))

    assert meta["report_quality"] == "fallback"
    assert meta["report_status"] == "empty"
    assert summary["report_quality"] == "fallback"
    assert summary["common_issues"][0]["type"] == "no_valid_speech"


def test_report_inherits_existing_a_contract_fields(db_session):
    student = User(
        id=uuid.uuid4(),
        account="contract_student",
        name="Contract Student",
        email="contract_student@test.com",
        password_hash="hashed_password",
        user_type="student",
        created_at=datetime.utcnow(),
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="Existing report contract",
        description="",
        duration=5,
        invitation_code="RPT007",
        status="completed",
        report={
            "mode": "teaching",
            "domain_pack_id": "pack-a",
            "report_meta": {
                "scoring_source": "fallback",
                "scoring_quality": "fallback",
                "provider": "llm",
            },
            "turning_points": [{"turn_id": "kept-turn", "summary": "kept", "impact": "kept"}],
            "teaching_summary": {"learning_objectives": ["kept"]},
        },
    )
    participation = DebateParticipation(
        id=uuid.uuid4(),
        debate_id=debate.id,
        user_id=student.id,
        role="debater_1",
        stance="positive",
    )
    db_session.add_all([student, debate, participation])
    db_session.commit()

    report = ReportGenerator.generate_student_report(
        db_session,
        str(debate.id),
        str(student.id),
    )

    assert report is not None
    report_data = report.to_dict()
    assert report_data["mode"] == "teaching"
    assert report_data["domain_pack_id"] == "pack-a"
    assert report_data["report_meta"]["scoring_quality"] == "fallback"
    assert report_data["report_meta"]["mode"] == "teaching"
    assert report_data["report_meta"]["prompt_pack_version"] == "a.prompt_pack.v1"
    assert report_data["turning_points"][0]["turn_id"] == "kept-turn"
    assert report_data["teaching_summary"]["learning_objectives"] == ["kept"]
    assert report_data["statistics"]["calibration_summary"]["fairness_check"]["status"] == "needs_review"


def test_report_meta_normalizes_repaired_and_flags_generation_failures(db_session):
    student = User(
        id=uuid.uuid4(),
        account="quality_student",
        name="Quality Student",
        email="quality_student@test.com",
        password_hash="hashed_password",
        user_type="student",
        created_at=datetime.utcnow(),
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="Quality signal debate",
        description="",
        duration=5,
        invitation_code="RPT005",
        status="completed",
        report={
            "report_quality": "repaired",
            "report_markdown_status": "failed",
            "report_markdown_error": "llm unavailable",
            "report_pdf_status": "failed",
            "report_pdf_error": "renderer unavailable",
            "score_fallback_generated": True,
            "score_generation_mode": "fallback",
        },
    )
    participation = DebateParticipation(
        id=uuid.uuid4(),
        debate_id=debate.id,
        user_id=student.id,
        role="debater_1",
        stance="positive",
    )
    speech = Speech(
        id=uuid.uuid4(),
        debate_id=debate.id,
        speaker_id=student.id,
        speaker_type="human",
        speaker_role="debater_1",
        phase="opening",
        content="This speech has enough content to be scored.",
        duration=18,
        is_valid_for_scoring=True,
        timestamp=datetime.utcnow(),
    )
    score = Score(
        id=uuid.uuid4(),
        participation_id=participation.id,
        speech_id=speech.id,
        logic_score=70,
        argument_score=70,
        response_score=70,
        persuasion_score=70,
        teamwork_score=70,
        overall_score=70,
        feedback=ReportOrchestrationService.SCORE_FALLBACK_MARKER,
        status="fallback",
        scoring_source="fallback",
        scoring_quality="fallback",
        failure_code="SCORING_PROVIDER_ERROR",
        eligible_for_analytics=False,
    )
    db_session.add_all([student, debate, participation, speech, score])
    db_session.commit()

    meta = ReportOrchestrationService.build_report_meta(db_session, debate)

    assert meta["report_quality"] == "partial"
    assert meta["rubric_version"] == "a.rubric.v1"
    assert meta["legacy_report_quality"] == "repaired"
    assert "repaired" not in meta["report_quality_supported_values"]
    assert meta["score_fallback_detected"] is True
    assert meta["score_fallback_count"] == 1
    assert "legacy_repaired_quality" in meta["quality_flags"]
    assert "markdown_generation_failed" in meta["quality_flags"]
    assert "pdf_generation_failed" in meta["quality_flags"]
    assert "score_fallback_detected" in meta["quality_flags"]


def test_report_meta_flags_stale_markdown_and_pdf_caches(db_session):
    student = User(
        id=uuid.uuid4(),
        account="stale_cache_student",
        name="Stale Cache Student",
        email="stale_cache_student@test.com",
        password_hash="hashed_password",
        user_type="student",
        created_at=datetime.utcnow(),
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="Stale cache debate",
        description="",
        duration=5,
        invitation_code="RPT006",
        status="completed",
        report={
            "score_revision": 2,
            "report_markdown": "# cached report",
            "report_markdown_hash": "old-markdown-hash",
            "report_pdf_markdown_hash": "old-pdf-hash",
        },
    )
    participation = DebateParticipation(
        id=uuid.uuid4(),
        debate_id=debate.id,
        user_id=student.id,
        role="debater_1",
        stance="positive",
    )
    speech = Speech(
        id=uuid.uuid4(),
        debate_id=debate.id,
        speaker_id=student.id,
        speaker_type="human",
        speaker_role="debater_1",
        phase="opening",
        content="This speech has enough content to be scored.",
        duration=18,
        is_valid_for_scoring=True,
        timestamp=datetime.utcnow(),
    )
    score = Score(
        id=uuid.uuid4(),
        participation_id=participation.id,
        speech_id=speech.id,
        logic_score=82,
        argument_score=81,
        response_score=80,
        persuasion_score=79,
        teamwork_score=78,
        overall_score=80,
        feedback="ready",
        status="validated",
        scoring_source="test_fixture",
        scoring_quality="validated",
        eligible_for_analytics=True,
    )
    db_session.add_all([student, debate, participation, speech, score])
    db_session.commit()

    meta = ReportOrchestrationService.build_report_meta(db_session, debate)

    assert meta["report_quality"] == "validated"
    assert meta["report_markdown_cache_status"] == "stale"
    assert meta["report_pdf_cache_status"] == "stale"
    assert "markdown_cache_stale" in meta["quality_flags"]
    assert "pdf_cache_stale" in meta["quality_flags"]


@pytest.mark.asyncio
async def test_lightweight_recalculation_clears_report_cache_without_replacing_scores(db_session):
    teacher = User(
        id=uuid.uuid4(),
        account="recalc_teacher",
        name="Recalc Teacher",
        email="recalc_teacher@test.com",
        password_hash="hashed_password",
        user_type="teacher",
        created_at=datetime.utcnow(),
    )
    student = User(
        id=uuid.uuid4(),
        account="recalc_student",
        name="Recalc Student",
        email="recalc_student@test.com",
        password_hash="hashed_password",
        user_type="student",
        created_at=datetime.utcnow(),
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="Recalculate report debate",
        description="",
        duration=5,
        invitation_code="RPT004",
        status="completed",
        teacher_id=teacher.id,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        report={
            "report_markdown": "# old",
            "report_markdown_hash": "old-hash",
            "report_pdf_markdown_hash": "old-pdf-hash",
            "report_pdf_storage": {
                "backend": "local",
                "storage_key": "ab/private-report.pdf",
            },
            "report_quality": "fallback",
        },
        report_pdf="old.pdf",
    )
    participation = DebateParticipation(
        id=uuid.uuid4(),
        debate_id=debate.id,
        user_id=student.id,
        role="debater_1",
        stance="positive",
    )
    speech = Speech(
        id=uuid.uuid4(),
        debate_id=debate.id,
        speaker_id=student.id,
        speaker_type="human",
        speaker_role="debater_1",
        phase="opening",
        content="First, the argument has evidence and a clear conclusion.",
        duration=18,
        is_valid_for_scoring=True,
        timestamp=datetime.utcnow(),
    )
    score = Score(
        id=uuid.uuid4(),
        participation_id=participation.id,
        speech_id=speech.id,
        logic_score=82,
        argument_score=81,
        response_score=80,
        persuasion_score=79,
        teamwork_score=78,
        overall_score=80,
        feedback="ready",
        status="validated",
        scoring_source="test_fixture",
        scoring_quality="validated",
        eligible_for_analytics=True,
    )
    db_session.add_all([teacher, student, debate, participation, speech, score])
    db_session.commit()

    score_id = score.id
    meta = ReportOrchestrationService.clear_report_cache_for_recalculation(db_session, str(debate.id))
    refreshed = db_session.query(Debate).filter(Debate.id == debate.id).one()

    assert db_session.query(Score).filter(Score.id == score_id).count() == 1
    assert refreshed.report_pdf is None
    assert "report_markdown" not in refreshed.report
    assert "report_markdown_hash" not in refreshed.report
    assert "report_pdf_storage" not in refreshed.report
    assert refreshed.report["report_recalculation_count"] == 1
    assert meta["report_quality"] == "validated"
