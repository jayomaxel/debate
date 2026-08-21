import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TopicRecommendationPanel from './topic-recommendation-panel';
import TeacherService from '@/services/teacher.service';

vi.mock('@/services/teacher.service', () => ({
  default: {
    getCurrentTeachingDesign: vi.fn(),
    generateTopicRecommendations: vi.fn(),
    getTopicRecommendationDashboard: vi.fn(),
    listTopicRecommendationRuns: vi.fn(),
    getTopicRecommendationRun: vi.fn(),
  },
}));

describe('TopicRecommendationPanel', () => {
  beforeEach(() => {
    vi.mocked(TeacherService.getCurrentTeachingDesign).mockResolvedValue(null);
    vi.mocked(TeacherService.getTopicRecommendationDashboard).mockResolvedValue({
      class_id: 'class-1',
      summary: {
        total_runs: 0,
        total_candidates: 0,
        adopted_run_count: 0,
        adopted_candidate_count: 0,
        total_adoptions: 0,
        run_adoption_rate: 0,
        candidate_adoption_rate: 0,
        average_candidates_per_run: 0,
        direct_adoptions: 0,
        edited_adoptions: 0,
        debate_adoptions: 0,
        reservation_adoptions: 0,
      },
      quality: {
        quality_counts: {},
        quality_rates: {},
        provider_counts: {},
        status_counts: {},
        version_breakdown: [],
      },
      timeline: {},
      leaderboards: {
        top_adopted_candidates: [],
        top_edited_candidates: [],
      },
      observations: {
        high_quality_low_adoption_candidates: [],
        high_quality_edited_only_candidates: [],
      },
      recent_runs: [],
    });
    vi.mocked(TeacherService.listTopicRecommendationRuns).mockResolvedValue([]);
  });

  it('keeps manual topic entry available when no design exists', async () => {
    render(<TopicRecommendationPanel classId='class-1' onSelect={vi.fn()} />);
    expect(screen.getByText('教学设计与辩题推荐')).toBeInTheDocument();
    expect(await screen.findByText(/仍可手动填写辩题/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '生成候选辩题' })).toBeDisabled();
  });
});
