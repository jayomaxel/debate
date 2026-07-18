from types import SimpleNamespace
from unittest.mock import MagicMock
import uuid

from services.comparison_service import ComparisonService


def _chain_query(result):
    query = MagicMock()
    query.filter.return_value = query
    query.join.return_value = query
    query.group_by.return_value = query
    query.first.return_value = result
    query.all.return_value = result
    return query


def test_class_average_weights_each_student_equally():
    student_id = uuid.uuid4()
    class_id = uuid.uuid4()
    student = SimpleNamespace(id=student_id, class_id=class_id)
    class_obj = SimpleNamespace(name="Test Class")
    scores = [
        SimpleNamespace(
            student_id=student_id,
            student_name="Student A",
            avg_overall=100,
            avg_logic=100,
            avg_argument=100,
            avg_response=100,
            avg_persuasion=100,
            avg_teamwork=100,
        ),
        SimpleNamespace(
            student_id=uuid.uuid4(),
            student_name="Student B",
            avg_overall=0,
            avg_logic=0,
            avg_argument=0,
            avg_response=0,
            avg_persuasion=0,
            avg_teamwork=0,
        ),
    ]

    db = MagicMock()
    db.query.side_effect = [
        _chain_query(student),
        _chain_query(class_obj),
        _chain_query(scores),
    ]

    result = ComparisonService(db).get_class_comparison(
        str(student_id),
        metric="overall",
    )

    assert result["sample_size"] == 2
    assert result["class_avg"]["score"] == 50.0
    assert result["class_avg"]["overall_score"] == 50.0
    assert result["class_avg"]["ability_scores"] == {
        "logic": 50.0,
        "argument": 50.0,
        "response": 50.0,
        "persuasion": 50.0,
        "teamwork": 50.0,
    }
    assert db.query.call_count == 3


def test_leading_percentile_counts_only_peers_ranked_below_student():
    student_id = uuid.uuid4()
    class_id = uuid.uuid4()
    student = SimpleNamespace(id=student_id, class_id=class_id)
    class_obj = SimpleNamespace(name="Test Class")
    scores = [
        SimpleNamespace(
            student_id=uuid.uuid4(),
            student_name="Student A",
            avg_overall=90,
            avg_logic=90,
            avg_argument=90,
            avg_response=90,
            avg_persuasion=90,
            avg_teamwork=90,
        ),
        SimpleNamespace(
            student_id=student_id,
            student_name="Student B",
            avg_overall=80,
            avg_logic=80,
            avg_argument=80,
            avg_response=80,
            avg_persuasion=80,
            avg_teamwork=80,
        ),
        SimpleNamespace(
            student_id=uuid.uuid4(),
            student_name="Student C",
            avg_overall=70,
            avg_logic=70,
            avg_argument=70,
            avg_response=70,
            avg_persuasion=70,
            avg_teamwork=70,
        ),
    ]

    db = MagicMock()
    db.query.side_effect = [
        _chain_query(student),
        _chain_query(class_obj),
        _chain_query(scores),
    ]

    result = ComparisonService(db).get_class_comparison(
        str(student_id),
        metric="overall",
    )

    my_stats = result["my"]
    assert my_stats["rank"] == 2
    assert my_stats["percentile"] == 50.0
    assert my_stats["leading_percentile"] == 50.0
    assert my_stats["rank_position_percentile"] == 66.67
    assert my_stats["percentile_label"] == "超过同班比例"
    assert my_stats["percentile_basis"]["leading_peer_count"] == 1
    assert my_stats["percentile_basis"]["comparable_peer_count"] == 2
