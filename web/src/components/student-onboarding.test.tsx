import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StudentOnboarding from './student-onboarding';
import StudentService, { type Debate } from '@/services/student.service';

const websocketState = {
  on: vi.fn(),
  off: vi.fn(),
  send: vi.fn(),
  isConnected: true,
  connect: vi.fn(),
  disconnect: vi.fn(),
  __handler: undefined as undefined | ((data: Record<string, unknown>) => void),
};

vi.mock('@/hooks/use-page-activity-refresh', () => ({
  usePageActivityRefresh: vi.fn(),
}));

vi.mock('@/hooks/use-websocket', () => ({
  useWebSocket: vi.fn(() => websocketState),
}));

vi.mock('@/services/student.service', () => ({
  default: {
    getAvailableDebates: vi.fn(),
    getDebateParticipants: vi.fn(),
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
  default: ({
    hasAssignedRole,
    participantCount,
    isReady,
  }: {
    hasAssignedRole: boolean;
    participantCount: number;
    isReady: boolean;
  }) => (
    <div>
      WaitingStatusBar {String(hasAssignedRole)} {participantCount} {String(isReady)}
    </div>
  ),
}));

vi.mock('./debate-topic-card', () => ({
  default: ({ debate }: { debate: Debate }) => <div>DebateTopicCard {debate.topic}</div>,
}));

const baseDebate: Debate = {
  id: 'debate-001',
  topic: 'AI 是否应该替代部分教师工作',
  description: '测试辩题',
  duration: 30,
  status: 'published',
  invitation_code: 'ABC123',
  created_at: '2026-05-03T00:00:00Z',
  participant_count: 3,
  is_joined: true,
  role: 'debater_2',
  role_reason: '负责推进攻辩并追问对方论证。',
  participants: [
    {
      user_id: 'student-001',
      name: '测试学生',
      role: 'debater_2',
      role_reason: '负责推进攻辩并追问对方论证。',
    },
    {
      user_id: 'student-002',
      name: '队友甲',
      role: 'debater_1',
    },
    {
      user_id: 'student-003',
      name: '队友乙',
      role: 'debater_3',
    },
  ],
};

describe('StudentOnboarding', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    websocketState.__handler = undefined;
    websocketState.on.mockImplementation((type, handler) => {
      if (type === 'state_update') {
        websocketState.__handler = handler;
      }
    });
    websocketState.off.mockImplementation(() => undefined);
    websocketState.send.mockImplementation(() => undefined);
    vi.mocked(StudentService.getAvailableDebates).mockResolvedValue([]);
    vi.mocked(StudentService.getDebateParticipants).mockResolvedValue([]);
  });

  it('shows an empty-state prompt when the student has not joined a debate yet', async () => {
    render(<StudentOnboarding />);

    expect(await screen.findByText('还没有加入本场辩论')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '返回学生首页' })).toBeInTheDocument();
  });

  it('renders the waiting and preparation view for a joined debate', async () => {
    vi.mocked(StudentService.getAvailableDebates).mockResolvedValue([baseDebate]);

    render(<StudentOnboarding />);

    expect(
      await screen.findByText('先确认你的辩位和参赛名单，四位辩手全部完成准备后会自动进入正式辩论。')
    ).toBeInTheDocument();
    expect(screen.getByText('DebateTopicCard AI 是否应该替代部分教师工作')).toBeInTheDocument();
    expect(screen.getByText('WaitingStatusBar true 3 false')).toBeInTheDocument();
    expect(screen.getByText('邀请码 ABC123')).toBeInTheDocument();
    expect(screen.getByText('我的辩位')).toBeInTheDocument();
    expect(screen.getByText('二辩')).toBeInTheDocument();
    expect(screen.getByText('测试学生')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '等待四人全部准备完成' })).toBeDisabled();
  });

  it('loads participants on demand when the joined debate is missing roster data', async () => {
    vi.mocked(StudentService.getAvailableDebates).mockResolvedValue([
      {
        ...baseDebate,
        participants: [],
        participant_count: 1,
      },
    ]);
    vi.mocked(StudentService.getDebateParticipants).mockResolvedValue([
      {
        user_id: 'student-001',
        name: '测试学生',
        role: 'debater_2',
        role_reason: '负责推进攻辩并追问对方论证。',
      },
    ]);

    render(<StudentOnboarding />);

    expect(await screen.findByText('测试学生')).toBeInTheDocument();
    await waitFor(() => {
      expect(StudentService.getDebateParticipants).toHaveBeenCalledWith('debate-001');
    });
  });

  it('sends waiting checklist updates when a student toggles a task', async () => {
    vi.mocked(StudentService.getAvailableDebates).mockResolvedValue([baseDebate]);

    render(<StudentOnboarding />);

    const checkbox = (await screen.findAllByRole('checkbox'))[0];
    fireEvent.click(checkbox);

    expect(websocketState.send).toHaveBeenCalledWith('waiting_checklist_update', {
      items: [true, false, false, false],
    });
  });

  it('auto-navigates when realtime room state shows the debate has started', async () => {
    vi.mocked(StudentService.getAvailableDebates).mockResolvedValue([baseDebate]);
    const onDebateStart = vi.fn();

    render(<StudentOnboarding onDebateStart={onDebateStart} />);

    await screen.findByText('准备清单');
    websocketState.__handler?.({
      room_id: 'debate-001',
      debate_id: 'debate-001',
      current_phase: 'opening',
      waiting_status: {
        required_roles: ['debater_1', 'debater_2', 'debater_3', 'debater_4'],
        required_count: 4,
        online_count: 4,
        ready_count: 4,
        online_roles: ['debater_1', 'debater_2', 'debater_3', 'debater_4'],
        ready_roles: ['debater_1', 'debater_2', 'debater_3', 'debater_4'],
        online_user_ids: ['student-001', 'student-002', 'student-003', 'student-004'],
        ready_user_ids: ['student-001', 'student-002', 'student-003', 'student-004'],
        missing_roles: [],
        all_online: true,
        all_ready: true,
        ready_to_start: true,
      },
      waiting_checklists: {
        'student-001': {
          items: [true, true, true, true],
          ready: true,
          completed_count: 4,
        },
      },
    });

    await waitFor(() => {
      expect(onDebateStart).toHaveBeenCalledWith('debate-001');
    });
  });
});
