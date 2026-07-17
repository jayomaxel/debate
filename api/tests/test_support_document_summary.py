from services.document_service import DocumentService


def test_support_document_summary_contains_frozen_fields():
    content = (
        'A 2025 survey covered 1,200 students and reported an 82% response rate. '
        'The study compares two teaching methods. '
        'For example, one class used structured questioning before free debate.'
    )
    result = DocumentService.build_support_document_summary(content, 'evidence')

    assert result['label'] == 'evidence'
    assert result['summary_quality'] == 'validated'
    assert result['key_points']
    assert result['evidence_candidates']
    assert 'questioning' in result['usable_phases']


def test_support_document_summary_has_safe_fallback():
    result = DocumentService.build_support_document_summary('', 'optional')

    assert result['summary_quality'] == 'fallback'
    assert result['summary']
    assert result['key_points'] == []
