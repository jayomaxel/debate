import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StudentCompetitionHub from './student-competition-hub';
import StudentService from '@/services/student.service';

vi.mock('@/hooks/use-page-activity-refresh', () => ({
  usePageActivityRefresh: vi.fn(),
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

vi.mock('@/hooks/use-student-assessment', () => ({
  useStudentAssessment: vi.fn(() => ({
    needsAssessment: false,
    loading: false,
  })),
}));

vi.mock('@/services/student.service', () => ({
  default: {
    getAvailableDebates: vi.fn(),
    getMyLobbyRooms: vi.fn(),
    getMyReservations: vi.fn(),
    joinDebate: vi.fn(),
  },
}));

describe('StudentCompetitionHub', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(StudentService.getAvailableDebates).mockResolvedValue([]);
    vi.mocked(StudentService.getMyLobbyRooms).mockResolvedValue([]);
    vi.mocked(StudentService.getMyReservations).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    } as any);
  });

  it('routes completed joined debates to the post-match page instead of waiting', async () => {
    vi.mocked(StudentService.getAvailableDebates).mockResolvedValue([
      {
        id: 'debate-001',
        topic: '测试已结束辩论',
        duration: 30,
        status: 'completed',
        invitation_code: 'ABC123',
        created_at: '2026-05-03T00:00:00Z',
        is_joined: true,
      },
    ] as any);

    const onNavigateToPostMatch = vi.fn();
    const onNavigateToWaiting = vi.fn();

    render(
      <StudentCompetitionHub
        onNavigateToPostMatch={onNavigateToPostMatch}
        onNavigateToWaiting={onNavigateToWaiting}
      />
    );

    expect(await screen.findByText('查看赛后分析')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '进入赛后分析页' }));

    expect(onNavigateToPostMatch).toHaveBeenCalledWith('debate-001');
    expect(onNavigateToWaiting).not.toHaveBeenCalled();
  });

  it('routes active lobby rooms to the lobby room page', async () => {
    vi.mocked(StudentService.getMyLobbyRooms).mockResolvedValue([
      {
        room_id: 'room-001',
        debate_id: 'room-001',
        topic: '我的自主房间辩题',
        room_name: '我的房间',
        mode: 'student_lobby',
        status: 'waiting',
        created_at: '2026-05-05T00:00:00Z',
        current_user_role: 'debater_2',
        current_user_permissions: {
          is_joined: true,
          role: 'debater_2',
          can_speak: true,
          can_moderate: false,
        },
      },
    ] as any);

    const onNavigateToLobbyRoom = vi.fn();

    render(<StudentCompetitionHub onNavigateToLobbyRoom={onNavigateToLobbyRoom} />);

    fireEvent.click(await screen.findByRole('button', { name: '进入我的自主房间' }));

    expect(onNavigateToLobbyRoom).toHaveBeenCalledWith('room-001');
  });

  it('does not treat student-created lobby debates as teacher-assigned debates', async () => {
    vi.mocked(StudentService.getAvailableDebates).mockResolvedValue([
      {
        id: 'debate-student-001',
        topic: '学生自建房不应进入老师卡片',
        duration: 30,
        status: 'published',
        invitation_code: 'ROOM01',
        created_at: '2026-05-05T00:00:00Z',
        is_joined: true,
        mode: 'student_lobby',
        room_source: 'student_created',
      },
    ] as any);

    vi.mocked(StudentService.getMyLobbyRooms).mockResolvedValue([
      {
        room_id: 'room-student-001',
        debate_id: 'debate-student-001',
        topic: '学生自建房不应进入老师卡片',
        room_name: '学生房间',
        mode: 'student_lobby',
        room_source: 'student_created',
        status: 'waiting',
        created_at: '2026-05-05T00:00:00Z',
        current_user_permissions: {
          is_joined: true,
          can_speak: true,
          can_moderate: false,
        },
      },
    ] as any);

    render(<StudentCompetitionHub />);

    expect(await screen.findByText('我的自主房间')).toBeInTheDocument();
    expect(screen.getByText('学生自建房不应进入老师卡片')).toBeInTheDocument();
    expect(screen.queryByText('邀请码 ROOM01')).not.toBeInTheDocument();
  });
});
