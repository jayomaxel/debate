import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import LobbyRoomWaiting from './lobby-room-waiting';
import StudentService from '@/services/student.service';

const toastMock = vi.fn();
const websocketState = {
  send: vi.fn(),
  on: vi.fn(),
  off: vi.fn(),
};

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: toastMock,
  }),
}));

vi.mock('@/hooks/use-websocket', () => ({
  useWebSocket: () => websocketState,
}));

vi.mock('@/store/auth.context', () => ({
  useAuth: () => ({
    user: {
      id: 'student-001',
      name: '测试学生',
    },
  }),
}));

vi.mock('@/services/student.service', () => ({
  default: {
    getLobbyRoomDetail: vi.fn(),
    leaveLobbyRoom: vi.fn(),
    joinLobbyRoom: vi.fn(),
  },
}));

const roomDetail = {
  room_id: 'room-001',
  debate_id: 'room-001',
  topic: '测试房间辩题',
  room_name: '测试房间',
  description: '房间说明',
  current_count: 2,
  capacity: 4,
  visibility: 'public',
  has_password: false,
  host_user_id: 'student-001',
  host_name: '测试学生',
  mode: 'student_lobby',
  room_source: 'student_created',
  config_source: 'room_owner_preset',
  preparation_page_type: 'student_lobby_preparation',
  status: 'waiting',
  scheduled_start_time: null,
  allow_spectators: false,
  members: [
    {
      user_id: 'student-001',
      name: '测试学生',
      role: 'debater_1',
      stance: 'positive',
      role_reason: '一辩',
      seat_order: 1,
      can_moderate: true,
      can_speak: true,
      membership_status: 'joined',
      presence_status: 'online_in_room',
      ready_status: 'not_ready',
    },
  ],
  current_user_permissions: {
    role: 'debater_1',
    can_speak: true,
    can_moderate: true,
    is_joined: true,
    membership_status: 'joined',
    presence_status: 'online_in_room',
    ready_status: 'not_ready',
  },
  available_roles: ['debater_2', 'debater_3', 'debater_4'],
  can_join: true,
  join_block_reason: null,
  is_current_user_joined: true,
  current_user_role: 'debater_1',
};

describe('LobbyRoomWaiting', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    websocketState.send.mockReset();
    websocketState.on.mockReset();
    websocketState.off.mockReset();
    vi.mocked(StudentService.getLobbyRoomDetail).mockResolvedValue(roomDetail as any);
    vi.mocked(StudentService.leaveLobbyRoom).mockResolvedValue({
      room_id: 'room-001',
      debate_id: 'room-001',
      membership_status: 'joined',
      presence_status: 'online_out_of_room_page',
      room_source: 'student_created',
    } as any);
  });

  it('sends permanent false when temporary leave is clicked', async () => {
    const onBack = vi.fn();

    render(
      <LobbyRoomWaiting roomId="room-001" onBack={onBack} onEnterDebate={vi.fn()} />
    );

    fireEvent.click(await screen.findByRole('button', { name: '临时退出' }));

    await waitFor(() => {
      expect(StudentService.leaveLobbyRoom).toHaveBeenCalledWith('room-001', {
        permanent: false,
      });
    });
    expect(onBack).toHaveBeenCalled();
  });

  it('sends permanent true when permanent leave is clicked', async () => {
    const onBack = vi.fn();

    render(
      <LobbyRoomWaiting roomId="room-001" onBack={onBack} onEnterDebate={vi.fn()} />
    );

    fireEvent.click(await screen.findByRole('button', { name: '退出房间' }));

    await waitFor(() => {
      expect(StudentService.leaveLobbyRoom).toHaveBeenCalledWith('room-001', {
        permanent: true,
      });
    });
    expect(onBack).toHaveBeenCalled();
  });
});
