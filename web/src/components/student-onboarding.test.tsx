import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StudentOnboarding from './student-onboarding';
import StudentService from '@/services/student.service';

vi.mock('@/services/student.service', () => ({
  default: {
    getAssessment: vi.fn(),
    getAvailableDebates: vi.fn(),
    submitAssessment: vi.fn(),
  },
}));

vi.mock('@/store/auth.context', () => ({
  useAuth: () => ({
    user: {
      id: 'student-001',
      name: '测试学生',
    },
  }),
}));

vi.mock('./waiting-status-bar', () => ({
  default: () => <div>WaitingStatusBar</div>,
}));

vi.mock('./debate-topic-card', () => ({
  default: () => <div>DebateTopicCard</div>,
}));

describe('StudentOnboarding', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (StudentService.getAvailableDebates as any).mockResolvedValue([]);
  });

  it('keeps the assessment editor empty when no saved assessment exists', async () => {
    (StudentService.getAssessment as any).mockResolvedValue(null);

    render(<StudentOnboarding />);

    await screen.findByRole('button', { name: '保存评估结果' });

    expect(screen.getByText('请先完成 5 个维度的填写，系统不会自动补入默认分值。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '保存评估结果' })).toBeDisabled();
    expect(screen.queryByText('已完成')).not.toBeInTheDocument();
  });

  it('shows shared assessment data when a real assessment already exists', async () => {
    (StudentService.getAssessment as any).mockResolvedValue({
      expression_willingness: 80,
      logical_thinking: 86,
      stablecoin_knowledge: 78,
      financial_knowledge: 82,
      critical_thinking: 88,
      recommended_role: 'debater_1',
      role_description: '一辩 - 立论陈词，奠定基调',
      is_default: false,
      created_at: '2026-04-10T00:00:00Z',
    });

    render(<StudentOnboarding />);

    await waitFor(() => {
      expect(screen.getByText('已完成')).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: '保存评估结果' })).not.toBeInTheDocument();
    expect(screen.getByText('推荐辩论角色')).toBeInTheDocument();
    expect(screen.getByText('80%')).toBeInTheDocument();
  });
});
