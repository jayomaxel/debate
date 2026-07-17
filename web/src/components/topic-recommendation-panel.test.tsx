import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TopicRecommendationPanel from './topic-recommendation-panel';
import TeacherService from '@/services/teacher.service';

vi.mock('@/services/teacher.service', () => ({
  default: {
    getCurrentTeachingDesign: vi.fn(),
    generateTopicRecommendations: vi.fn(),
  },
}));

describe('TopicRecommendationPanel', () => {
  beforeEach(() => {
    vi.mocked(TeacherService.getCurrentTeachingDesign).mockResolvedValue(null);
  });

  it('keeps manual topic entry available when no design exists', async () => {
    render(<TopicRecommendationPanel classId='class-1' onSelect={vi.fn()} />);
    expect(screen.getByText('教学设计与辩题推荐')).toBeInTheDocument();
    expect(await screen.findByText(/仍可手动填写辩题/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '生成候选辩题' })).toBeDisabled();
  });
});
