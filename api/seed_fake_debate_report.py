from __future__ import annotations

import argparse
import hashlib
import json
import random
import string
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

import database
from models.class_model import Class
from models.debate import Debate, DebateParticipation
from models.score import Score
from models.speech import Speech
from models.user import User
from sqlalchemy import func


ROLE_ORDER = ["debater_1", "debater_2", "debater_3", "debater_4"]

TOPIC_POOL = [
    "AI 是否应该深度参与课堂评价",
    "生成式 AI 是否会削弱学生独立思考能力",
    "中学生是否应该系统学习 AI 伦理",
    "课堂讨论中是否应鼓励学生实时使用 AI 助手",
    "学校是否应该将 AI 素养纳入核心课程",
]

HUMAN_SPEECH_TEMPLATES = [
    {
        "role": "debater_1",
        "phase": "opening",
        "content": "我方认为，围绕“{topic}”这一议题，AI 的价值不在于替代教师或学生，而在于提升课堂决策的透明度、反馈速度与个性化支持能力。只要边界清晰、责任仍由人承担，AI 就能成为高质量教学的放大器。",
        "base_score": 86.0,
        "duration": 92,
    },
    {
        "role": "debater_2",
        "phase": "questioning",
        "content": "对方反复强调风险，但没有回答一个核心问题: 如果完全不引入 AI，教师如何在大班教学中兼顾反馈效率与个体差异? 我方的立场从来不是放权给机器，而是用机器降低低效重复劳动，把真正的判断权还给教师。",
        "base_score": 84.0,
        "duration": 78,
    },
    {
        "role": "debater_3",
        "phase": "free_debate",
        "content": "对方把“会出错”直接等同于“不能使用”，这在逻辑上并不成立。课堂中的评分量表、同伴互评、教师主观判断本身也会有偏差。真正成熟的方案应该是多源交叉验证，而不是因为存在误差就拒绝工具进入教育场景。",
        "base_score": 87.0,
        "duration": 66,
    },
    {
        "role": "debater_1",
        "phase": "free_debate",
        "content": "我方再补充一点，AI 的最大优势是形成可追踪的过程证据。它能记录学生修改轨迹、提问路径和反馈接受情况，这种过程性数据恰恰能帮助教师避免单次结果导向的片面评价。",
        "base_score": 85.0,
        "duration": 58,
    },
    {
        "role": "debater_2",
        "phase": "free_debate",
        "content": "如果对方真正担心的是算法偏见，那就更应该让学生在真实场景中学会识别偏见、质疑输出、验证来源，而不是把 AI 神秘化。教育的目标应该是提升判断能力，而不是回避技术环境。",
        "base_score": 83.0,
        "duration": 61,
    },
    {
        "role": "debater_3",
        "phase": "free_debate",
        "content": "对方始终把 AI 描述为终点裁判，但我方明确说的是协作助手。协作助手提供的是建议、分析与辅助视角，最终决策仍由教师完成。把辅助工具说成终局权威，这属于明显的稻草人论证。",
        "base_score": 86.0,
        "duration": 63,
    },
    {
        "role": "debater_4",
        "phase": "closing",
        "content": "总结来看，我方并未否认风险，而是给出了可执行的治理框架: 人类主责、过程留痕、结果复核、伦理约束。正因为教育需要公平和效率并重，我们才更需要在规则之下把 AI 纳入课堂，而不是把它排除在课堂之外。",
        "base_score": 89.0,
        "duration": 95,
    },
]

AI_SPEECH_TEMPLATES = [
    {
        "role": "ai_1",
        "phase": "opening",
        "content": "反方认为，讨论“{topic}”时不能只看到效率收益，更要看到教育责任被技术模糊后的长期代价。只要学生开始依赖外部模型给出答案与评价依据，课堂中的主体性就会被悄悄侵蚀。",
        "base_score": 80.0,
        "duration": 88,
    },
    {
        "role": "ai_2",
        "phase": "questioning",
        "content": "正方口头上说保留教师决策权，实际上却不断扩大 AI 介入范围。请正面回答: 当教师时间不足、系统结论又显得专业时，教师真的还能保持独立判断吗? 这恰恰是技术依赖最真实的发生机制。",
        "base_score": 79.0,
        "duration": 73,
    },
    {
        "role": "ai_3",
        "phase": "free_debate",
        "content": "正方把所有问题都交给治理方案解决，却回避了一个事实: 技术一旦进入日常流程，治理往往滞后于使用。教育并不是容错成本极低的实验场，学生被误判、被标签化之后，影响可能是持续性的。",
        "base_score": 81.0,
        "duration": 64,
    },
    {
        "role": "ai_1",
        "phase": "free_debate",
        "content": "正方强调留痕与复核，但现实中越复杂的系统越容易让一线教师被迫信任结论而非理解过程。所谓“可解释”并不等于真正可审计，这一点在教育评价场景中尤其关键。",
        "base_score": 78.0,
        "duration": 57,
    },
    {
        "role": "ai_2",
        "phase": "free_debate",
        "content": "如果学生把与 AI 协作的熟练度误当成自己的真实能力，那么教学反馈就会被污染。反方不是拒绝技术，而是反对在评价权尚未厘清前，把技术深度嵌入教学核心判断环节。",
        "base_score": 80.0,
        "duration": 60,
    },
    {
        "role": "ai_3",
        "phase": "free_debate",
        "content": "正方把风险描述成“可以被管理”，却没有说明谁来承担管理失败的责任。教育制度的设计必须先回答责任链，再讨论效率红利，否则就是拿学生做制度试验。",
        "base_score": 82.0,
        "duration": 62,
    },
    {
        "role": "ai_4",
        "phase": "closing",
        "content": "反方最后强调，教育首先是价值塑造与能力培养，而不是流程优化。任何可能削弱主体判断、放大结构偏差、模糊责任归属的技术介入，都不应被轻率地描述成“进步”。",
        "base_score": 81.0,
        "duration": 90,
    },
]

DIMENSION_OFFSETS = {
    "logic_score": 0.8,
    "argument_score": 0.4,
    "response_score": -0.3,
    "persuasion_score": 0.1,
    "teamwork_score": 0.2,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="写入一场可直接回看报告的假辩论数据，不经过正式自由辩论流程。"
    )
    parser.add_argument(
        "--class-id",
        help="指定班级 ID；不传时会自动从学生数 >= 4 的班级里随机选一个。",
    )
    parser.add_argument(
        "--debate-id",
        help="指定已有辩论 ID；传入后会覆盖该场的参与者/发言/评分，并直接标记为 completed。",
    )
    parser.add_argument(
        "--topic",
        help="辩题；不传时会自动从预设池里随机选一个。",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="随机种子，便于复现抽样结果。",
    )
    parser.add_argument(
        "--student-count",
        type=int,
        default=4,
        help="随机抽取的学生人数，当前建议固定为 4。",
    )
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=18,
        help="辩论时长（分钟）。",
    )
    return parser.parse_args()


def generate_invitation_code(session, rng: random.Random) -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        candidate = "".join(rng.choices(alphabet, k=6))
        existing = session.query(Debate).filter(Debate.invitation_code == candidate).first()
        if existing is None:
            return candidate


def get_eligible_classes(session, minimum_students: int) -> List[Tuple[Class, int]]:
    rows = (
        session.query(Class, func.count(User.id).label("student_count"))
        .join(User, User.class_id == Class.id)
        .filter(User.user_type == "student")
        .group_by(Class.id)
        .having(func.count(User.id) >= minimum_students)
        .order_by(func.count(User.id).desc(), Class.created_at.desc())
        .all()
    )
    return [(row[0], int(row[1])) for row in rows]


def pick_class(session, class_id: Optional[str], minimum_students: int, rng: random.Random) -> Class:
    if class_id:
        class_uuid = uuid.UUID(str(class_id))
        class_obj = session.query(Class).filter(Class.id == class_uuid).first()
        if class_obj is None:
            raise ValueError(f"班级不存在: {class_id}")
        student_count = (
            session.query(User)
            .filter(User.class_id == class_obj.id, User.user_type == "student")
            .count()
        )
        if student_count < minimum_students:
            raise ValueError(
                f"班级 {class_obj.name} 仅有 {student_count} 名学生，不满足至少 {minimum_students} 人的要求。"
            )
        return class_obj

    eligible_classes = get_eligible_classes(session, minimum_students=minimum_students)
    if not eligible_classes:
        raise ValueError("数据库中没有学生人数 >= 4 的班级。")
    return rng.choice([item[0] for item in eligible_classes])


def pick_students(
    session,
    class_obj: Class,
    student_count: int,
    rng: random.Random,
) -> List[User]:
    students = (
        session.query(User)
        .filter(User.class_id == class_obj.id, User.user_type == "student")
        .order_by(User.created_at.asc())
        .all()
    )
    if len(students) < student_count:
        raise ValueError(f"班级 {class_obj.name} 学生不足 {student_count} 人。")
    return rng.sample(students, student_count)


def clamp_score(value: float) -> float:
    return round(max(65.0, min(98.0, value)), 2)


def build_score_payload(rng: random.Random, base_score: float, speaker_type: str, phase: str) -> Dict[str, float]:
    phase_bonus = {
        "opening": 0.8,
        "questioning": 0.2,
        "free_debate": 0.5,
        "closing": 1.0,
    }.get(phase, 0.0)
    speaker_bonus = 1.2 if speaker_type == "human" else 0.0

    scores: Dict[str, float] = {}
    for name, offset in DIMENSION_OFFSETS.items():
        jitter = rng.uniform(-2.5, 2.5)
        scores[name] = clamp_score(base_score + speaker_bonus + phase_bonus + offset + jitter)

    scores["overall_score"] = round(
        (
            scores["logic_score"]
            + scores["argument_score"]
            + scores["response_score"]
            + scores["persuasion_score"]
            + scores["teamwork_score"]
        )
        / 5.0,
        2,
    )
    return scores


def build_feedback(speaker_type: str, phase: str, overall_score: float) -> str:
    speaker_label = "学生方" if speaker_type == "human" else "AI 方"
    phase_label = {
        "opening": "立论",
        "questioning": "盘问",
        "free_debate": "自由辩论",
        "closing": "总结陈词",
    }.get(phase, phase)
    if overall_score >= 86:
        level = "论点推进非常稳定，兼顾了逻辑和表达力度。"
    elif overall_score >= 80:
        level = "论证较完整，回应节奏基本到位。"
    else:
        level = "有明确观点，但在证据深度和反击力度上仍有提升空间。"
    return f"{speaker_label}在{phase_label}阶段表现较完整，{level}"


def average_score_payload(score_rows: Sequence[Dict[str, float]]) -> Dict[str, float]:
    if not score_rows:
        return {
            "logic_score": 0.0,
            "argument_score": 0.0,
            "response_score": 0.0,
            "persuasion_score": 0.0,
            "teamwork_score": 0.0,
            "overall_score": 0.0,
        }

    return {
        key: round(sum(float(item[key]) for item in score_rows) / len(score_rows), 2)
        for key in [
            "logic_score",
            "argument_score",
            "response_score",
            "persuasion_score",
            "teamwork_score",
            "overall_score",
        ]
    }


def build_speech_specs(topic: str) -> List[Dict[str, object]]:
    specs: List[Dict[str, object]] = []
    for human_item, ai_item in zip(HUMAN_SPEECH_TEMPLATES, AI_SPEECH_TEMPLATES):
        specs.append(
            {
                "speaker_type": "human",
                "speaker_role": human_item["role"],
                "phase": human_item["phase"],
                "content": str(human_item["content"]).format(topic=topic),
                "base_score": float(human_item["base_score"]),
                "duration": int(human_item["duration"]),
            }
        )
        specs.append(
            {
                "speaker_type": "ai",
                "speaker_role": ai_item["role"],
                "phase": ai_item["phase"],
                "content": str(ai_item["content"]).format(topic=topic),
                "base_score": float(ai_item["base_score"]),
                "duration": int(ai_item["duration"]),
            }
        )
    return specs


def clear_existing_debate_data(session, debate: Debate) -> None:
    speech_ids = [
        row[0]
        for row in session.query(Speech.id).filter(Speech.debate_id == debate.id).all()
    ]
    participation_ids = [
        row[0]
        for row in session.query(DebateParticipation.id)
        .filter(DebateParticipation.debate_id == debate.id)
        .all()
    ]

    if speech_ids:
        session.query(Score).filter(Score.speech_id.in_(speech_ids)).delete(
            synchronize_session=False
        )
    if participation_ids:
        session.query(Score).filter(Score.participation_id.in_(participation_ids)).delete(
            synchronize_session=False
        )

    session.query(Speech).filter(Speech.debate_id == debate.id).delete(
        synchronize_session=False
    )
    session.query(DebateParticipation).filter(
        DebateParticipation.debate_id == debate.id
    ).delete(synchronize_session=False)

    debate.report = None
    debate.report_pdf = None
    session.flush()


def build_markdown_report(
    debate: Debate,
    class_obj: Class,
    teacher: User,
    role_assignments: Sequence[Tuple[User, str]],
    human_final_scores: Dict[str, Dict[str, float]],
    team_stats: Dict[str, Dict[str, float]],
    speech_rows: Sequence[Speech],
) -> str:
    winner = "正方" if team_stats["human"]["avg_score"] >= team_stats["ai"]["avg_score"] else "反方"
    participant_lines = []
    for student, role in role_assignments:
        final_score = human_final_scores.get(role, {})
        participant_lines.append(
            f"| {role} | {student.name} | {student.account} | {final_score.get('overall_score', 0)} | {int(final_score.get('speech_count', 0))} |"
        )

    highlight_rows = []
    for speech in speech_rows[:4]:
        speaker_label = speech.speaker_role
        highlight_rows.append(
            f"- `{speaker_label}` [{speech.phase}] {speech.content[:80]}..."
        )

    return "\n".join(
        [
            "# 辩论报告",
            "",
            "## 基本信息",
            "",
            f"- 辩题: {debate.topic}",
            f"- 班级: {class_obj.name}",
            f"- 教师: {teacher.name}",
            f"- 开始时间: {debate.start_time.isoformat() if debate.start_time else ''}",
            f"- 结束时间: {debate.end_time.isoformat() if debate.end_time else ''}",
            f"- 结论: {winner}获胜",
            "",
            "## 参赛学生",
            "",
            "| 角色 | 姓名 | 账号 | 综合得分 | 发言次数 |",
            "| :--- | :--- | :--- | ---: | ---: |",
            *participant_lines,
            "",
            "## 双方概览",
            "",
            "| 阵营 | 平均分 | 发言次数 | 总时长(秒) |",
            "| :--- | ---: | ---: | ---: |",
            f"| 正方(学生) | {team_stats['human']['avg_score']} | {int(team_stats['human']['speech_count'])} | {int(team_stats['human']['total_duration'])} |",
            f"| 反方(AI) | {team_stats['ai']['avg_score']} | {int(team_stats['ai']['speech_count'])} | {int(team_stats['ai']['total_duration'])} |",
            "",
            "## 裁判结论",
            "",
            "- 正方整体结构更稳定，回应更聚焦教学场景与治理边界。",
            "- 反方风险意识充分，但个别回合存在论点重复、压制力不足的问题。",
            "- 这份报告为演示假数据，目的是直接验证历史、回放与报告页面链路。",
            "",
            "## 代表性发言",
            "",
            *highlight_rows,
            "",
            "## 教学建议",
            "",
            "- 建议继续保留分阶段发言、单条评分和汇总评分三类数据，以便后续前端回放与报告复用。",
            "- 如果后续需要补到指定卡死场次，可复用本脚本的 `--debate-id` 模式直接覆盖写入。",
        ]
    )


def build_report_payload(
    debate: Debate,
    class_obj: Class,
    teacher: User,
    role_assignments: Sequence[Tuple[User, str]],
    human_final_scores: Dict[str, Dict[str, float]],
    team_stats: Dict[str, Dict[str, float]],
    speech_rows: Sequence[Speech],
) -> Dict[str, object]:
    winner = "positive" if team_stats["human"]["avg_score"] >= team_stats["ai"]["avg_score"] else "negative"
    markdown_text = build_markdown_report(
        debate=debate,
        class_obj=class_obj,
        teacher=teacher,
        role_assignments=role_assignments,
        human_final_scores=human_final_scores,
        team_stats=team_stats,
        speech_rows=speech_rows,
    )
    return {
        "summary": "已跳过正式自由辩论流程，直接注入可回看的假数据报告。",
        "winner": winner,
        "winning_reason": "正方在逻辑完整性和场景落地性上略占优势。",
        "scores": {
            "positive": {
                "avg_score": team_stats["human"]["avg_score"],
                "speech_count": int(team_stats["human"]["speech_count"]),
                "total_duration": int(team_stats["human"]["total_duration"]),
            },
            "negative": {
                "avg_score": team_stats["ai"]["avg_score"],
                "speech_count": int(team_stats["ai"]["speech_count"]),
                "total_duration": int(team_stats["ai"]["total_duration"]),
            },
        },
        "overall_comment": "本场数据为演示链路用假数据，但结构已满足历史页、回放页、报告页与 PDF 导出前置条件。",
        "suggestions": [
            "若只想保演示链路，优先保 debates/report、speeches、scores 三类数据完整。",
            "如需映射到卡死那场，传入 --debate-id 即可覆盖到指定辩论。",
        ],
        "report_markdown": markdown_text,
        "report_markdown_hash": hashlib.sha256(markdown_text.encode("utf-8")).hexdigest(),
    }


def create_or_update_debate(
    session,
    class_obj: Class,
    teacher: User,
    topic: str,
    duration_minutes: int,
    debate_id: Optional[str],
    rng: random.Random,
) -> Debate:
    now = datetime.utcnow()
    start_time = now - timedelta(minutes=duration_minutes)
    end_time = now

    if debate_id:
        debate_uuid = uuid.UUID(str(debate_id))
        debate = session.query(Debate).filter(Debate.id == debate_uuid).first()
        if debate is None:
            raise ValueError(f"辩论不存在: {debate_id}")
        clear_existing_debate_data(session, debate)
        debate.class_id = class_obj.id
        debate.teacher_id = teacher.id
        debate.topic = topic
        debate.description = "演示链路用假数据，已直接跳过自由辩论正式流程。"
        debate.duration = duration_minutes
        debate.status = "completed"
        debate.start_time = start_time
        debate.end_time = end_time
        debate.report = None
        debate.report_pdf = None
        return debate

    debate = Debate(
        id=uuid.uuid4(),
        topic=topic,
        description="演示链路用假数据，已直接跳过自由辩论正式流程。",
        duration=duration_minutes,
        invitation_code=generate_invitation_code(session, rng),
        class_id=class_obj.id,
        teacher_id=teacher.id,
        status="completed",
        start_time=start_time,
        end_time=end_time,
        report=None,
        report_pdf=None,
    )
    session.add(debate)
    session.flush()
    return debate


def seed_fake_bundle(
    session,
    class_obj: Class,
    teacher: User,
    selected_students: Sequence[User],
    topic: str,
    duration_minutes: int,
    rng: random.Random,
    debate_id: Optional[str],
) -> Dict[str, object]:
    debate = create_or_update_debate(
        session=session,
        class_obj=class_obj,
        teacher=teacher,
        topic=topic,
        duration_minutes=duration_minutes,
        debate_id=debate_id,
        rng=rng,
    )

    shuffled_students = list(selected_students)
    rng.shuffle(shuffled_students)
    role_assignments: List[Tuple[User, str]] = list(zip(shuffled_students, ROLE_ORDER))

    participation_by_role: Dict[str, DebateParticipation] = {}
    student_by_role: Dict[str, User] = {}
    for student, role in role_assignments:
        participation = DebateParticipation(
            id=uuid.uuid4(),
            debate_id=debate.id,
            user_id=student.id,
            role=role,
            stance="positive",
            role_reason="fake_report_seed",
        )
        session.add(participation)
        participation_by_role[role] = participation
        student_by_role[role] = student
    session.flush()

    speech_specs = build_speech_specs(topic)
    total_seconds = max(duration_minutes * 60, len(speech_specs) * 40)
    step_seconds = max(35, total_seconds // max(len(speech_specs), 1))
    speech_rows: List[Speech] = []
    human_score_rows_by_role: Dict[str, List[Dict[str, float]]] = {role: [] for role in ROLE_ORDER}
    team_score_rows: Dict[str, List[Dict[str, float]]] = {"human": [], "ai": []}
    team_duration: Dict[str, int] = {"human": 0, "ai": 0}
    team_speech_count: Dict[str, int] = {"human": 0, "ai": 0}

    for index, spec in enumerate(speech_specs):
        speaker_type = str(spec["speaker_type"])
        speaker_role = str(spec["speaker_role"])
        phase = str(spec["phase"])
        content = str(spec["content"])
        duration = int(spec["duration"])
        timestamp = debate.start_time + timedelta(seconds=index * step_seconds)

        speaker_id = None
        if speaker_type == "human":
            speaker_id = student_by_role[speaker_role].id

        speech = Speech(
            id=uuid.uuid4(),
            debate_id=debate.id,
            speaker_id=speaker_id,
            speaker_type=speaker_type,
            speaker_role=speaker_role,
            phase=phase,
            content=content,
            duration=duration,
            timestamp=timestamp,
        )
        session.add(speech)
        session.flush()

        score_payload = build_score_payload(
            rng=rng,
            base_score=float(spec["base_score"]),
            speaker_type=speaker_type,
            phase=phase,
        )
        score = Score(
            id=uuid.uuid4(),
            participation_id=(
                participation_by_role[speaker_role].id
                if speaker_type == "human"
                else participation_by_role[f"debater_{speaker_role.split('_')[1]}"].id
            ),
            speech_id=speech.id,
            feedback=build_feedback(
                speaker_type=speaker_type,
                phase=phase,
                overall_score=score_payload["overall_score"],
            ),
            **score_payload,
        )
        session.add(score)

        speech_rows.append(speech)
        team_key = "human" if speaker_type == "human" else "ai"
        team_score_rows[team_key].append(score_payload)
        team_duration[team_key] += duration
        team_speech_count[team_key] += 1

        if speaker_type == "human":
            human_score_rows_by_role[speaker_role].append(score_payload)

    human_final_scores: Dict[str, Dict[str, float]] = {}
    for role, participation in participation_by_role.items():
        averaged = average_score_payload(human_score_rows_by_role[role])
        averaged["speech_count"] = len(human_score_rows_by_role[role])
        averaged["total_duration"] = sum(
            speech.duration
            for speech in speech_rows
            if str(speech.speaker_role) == role and str(speech.speaker_type) == "human"
        )
        summary_score = Score(
            id=uuid.uuid4(),
            participation_id=participation.id,
            speech_id=None,
            feedback="汇总得分，供历史详情与报告页直接读取。",
            logic_score=averaged["logic_score"],
            argument_score=averaged["argument_score"],
            response_score=averaged["response_score"],
            persuasion_score=averaged["persuasion_score"],
            teamwork_score=averaged["teamwork_score"],
            overall_score=averaged["overall_score"],
        )
        session.add(summary_score)
        human_final_scores[role] = averaged

    team_stats = {
        "human": {
            "avg_score": average_score_payload(team_score_rows["human"])["overall_score"],
            "speech_count": team_speech_count["human"],
            "total_duration": team_duration["human"],
        },
        "ai": {
            "avg_score": average_score_payload(team_score_rows["ai"])["overall_score"],
            "speech_count": team_speech_count["ai"],
            "total_duration": team_duration["ai"],
        },
    }

    debate.report = build_report_payload(
        debate=debate,
        class_obj=class_obj,
        teacher=teacher,
        role_assignments=role_assignments,
        human_final_scores=human_final_scores,
        team_stats=team_stats,
        speech_rows=speech_rows,
    )
    debate.report_pdf = None

    session.commit()
    session.refresh(debate)

    return {
        "debate": debate,
        "role_assignments": role_assignments,
        "team_stats": team_stats,
        "human_final_scores": human_final_scores,
        "speech_rows": speech_rows,
    }


def print_summary(
    class_obj: Class,
    teacher: User,
    result: Dict[str, object],
) -> None:
    debate: Debate = result["debate"]  # type: ignore[assignment]
    role_assignments: Sequence[Tuple[User, str]] = result["role_assignments"]  # type: ignore[assignment]
    team_stats: Dict[str, Dict[str, float]] = result["team_stats"]  # type: ignore[assignment]
    human_final_scores: Dict[str, Dict[str, float]] = result["human_final_scores"]  # type: ignore[assignment]

    print("Seed completed.")
    print(f"debate_id={debate.id}")
    print(f"class_id={class_obj.id}")
    print(f"class_name={class_obj.name}")
    print(f"teacher_account={teacher.account}")
    print(f"teacher_name={teacher.name}")
    print(f"topic={debate.topic}")
    print(f"status={debate.status}")
    print(f"report_api=/api/student/reports/{debate.id}")
    print(f"history_api=/api/student/history/{debate.id}")
    print(f"human_avg_score={team_stats['human']['avg_score']}")
    print(f"ai_avg_score={team_stats['ai']['avg_score']}")
    print("selected_students=")
    print(
        json.dumps(
            [
                {
                    "role": role,
                    "user_id": str(student.id),
                    "account": student.account,
                    "name": student.name,
                    "overall_score": human_final_scores.get(role, {}).get("overall_score", 0),
                }
                for student, role in role_assignments
            ],
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    args = parse_args()
    student_count = min(max(args.student_count, 4), 4)
    rng = random.Random(args.seed)

    database.init_engine()
    database.init_db()
    session = database.SessionLocal()

    try:
        class_obj = pick_class(
            session=session,
            class_id=args.class_id,
            minimum_students=student_count,
            rng=rng,
        )
        teacher = (
            session.query(User)
            .filter(User.id == class_obj.teacher_id, User.user_type == "teacher")
            .first()
        )
        if teacher is None:
            raise ValueError(f"班级 {class_obj.name} 未找到有效教师。")

        selected_students = pick_students(
            session=session,
            class_obj=class_obj,
            student_count=student_count,
            rng=rng,
        )
        topic = args.topic or rng.choice(TOPIC_POOL)

        result = seed_fake_bundle(
            session=session,
            class_obj=class_obj,
            teacher=teacher,
            selected_students=selected_students,
            topic=topic,
            duration_minutes=args.duration_minutes,
            rng=rng,
            debate_id=args.debate_id,
        )
        print_summary(class_obj=class_obj, teacher=teacher, result=result)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
