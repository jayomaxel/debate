import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { DebateReport } from '../services/student.service';
import DebateReportOverview from './debate-report-overview';

vi.mock('../store/auth.context', () => ({
  useAuth: () => ({
    user: { id: 'teacher-1', user_type: 'teacher', name: '测试教师' },
  }),
}));

describe('DebateReportOverview human-only ability radar', () => {
  it('shows the human empty state when the room only contains AI speeches', () => {
    const report: DebateReport = {
      debate_id: 'debate-ai-only',
      topic: '仅 AI 发言的测试辩题',
      start_time: '2026-07-22T20:00:00',
      end_time: '2026-07-22T20:01:10',
      duration: 1,
      winner: 'negative',
      participants: [
        {
          user_id: 'ai-1',
          name: 'AI辩手1',
          role: 'ai_1',
          stance: 'negative',
          is_ai: true,
          score_status: 'ready',
          final_score: {
            logic_score: 70.33,
            argument_score: 69.33,
            response_score: 68.33,
            persuasion_score: 69.33,
            teamwork_score: 68.33,
            overall_score: 69,
            speech_count: 1,
            total_duration: 70,
          },
        },
      ],
      speeches: [],
      statistics: {
        human_ability: {
          ability_scope: 'human_only',
          evaluated_student_count: 0,
          valid_human_speech_count: 0,
          excluded_ai_speech_count: 1,
          excluded_demo_record_count: 0,
          has_human_ability_data: false,
          ability_scores: null,
          overall_score: null,
        },
      },
    };

    render(<DebateReportOverview report={report} />);

    expect(screen.getByText('人类辩手核心能力评估')).toBeInTheDocument();
    expect(screen.getByText('暂无人类辩手能力数据')).toBeInTheDocument();
    expect(screen.queryByText('70.33')).not.toBeInTheDocument();
    expect(screen.queryByText('69.33')).not.toBeInTheDocument();
  });
});
