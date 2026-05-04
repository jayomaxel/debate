import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import JoinPrivateRoomDialog from '@/components/join-private-room-dialog';
import { useToast } from '@/hooks/use-toast';
import {
  formatDateTime,
  formatRelativeStart,
  roleLabel,
  roomStatusLabelMap,
  stanceLabelMap,
  statusBadgeClass,
} from '@/lib/reservation-display';
import StudentService, {
  type LobbyRoom,
  type LobbyRoomMember,
} from '@/services/student.service';
import {
  ArrowLeft,
  CalendarClock,
  Crown,
  DoorOpen,
  Loader2,
  Lock,
  Play,
  RefreshCw,
  Shield,
  Unlock,
  Users,
} from 'lucide-react';

interface LobbyRoomWaitingProps {
  roomId: string;
  onBack: () => void;
  onEnterDebate: (roomId: string) => void;
}

const memberSort = (a: LobbyRoomMember, b: LobbyRoomMember) =>
  (a.seat_order || 99) - (b.seat_order || 99);

const LobbyRoomWaiting: React.FC<LobbyRoomWaitingProps> = ({
  roomId,
  onBack,
  onEnterDebate,
}) => {
  const { toast } = useToast();
  const [room, setRoom] = useState<LobbyRoom | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [joining, setJoining] = useState(false);
  const [joinPrivateOpen, setJoinPrivateOpen] = useState(false);

  const loadRoom = useCallback(async (mode: 'initial' | 'manual' | 'poll' = 'manual') => {
    try {
      if (mode === 'initial') setLoading(true);
      if (mode === 'manual') setRefreshing(true);
      const data = await StudentService.getLobbyRoomDetail(roomId);
      setRoom(data);
    } catch (err: any) {
      toast({
        variant: 'destructive',
        title: '房间加载失败',
        description: err?.response?.data?.detail || err?.message || '请稍后重试',
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [roomId, toast]);

  useEffect(() => {
    void loadRoom('initial');
  }, [loadRoom]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        void loadRoom('poll');
      }
    }, 8000);
    return () => window.clearInterval(intervalId);
  }, [loadRoom]);

  const members = useMemo(() => [...(room?.members || [])].sort(memberSort), [room?.members]);
  const currentPermissions = room?.current_user_permissions;
  const isJoined = !!currentPermissions?.is_joined || !!room?.is_current_user_joined;
  const canModerate = !!currentPermissions?.can_moderate;
  const memberByRole = useMemo(() => {
    const map = new Map<string, LobbyRoomMember>();
    members.forEach((member) => map.set(member.role, member));
    return map;
  }, [members]);

  const handleJoinPublic = async () => {
    if (!room) return;
    try {
      setJoining(true);
      const next = await StudentService.joinLobbyRoom(room.room_id);
      setRoom(next);
      toast({
        variant: 'success',
        title: '加入成功',
        description: `席位已分配：${roleLabel(next.participant_role || next.current_user_role)}`,
      });
    } catch (err: any) {
      toast({
        variant: 'destructive',
        title: '加入失败',
        description: err?.response?.data?.detail || err?.message || '请稍后重试',
      });
    } finally {
      setJoining(false);
    }
  };

  if (loading) {
    return (
      <div className='flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 via-slate-50 to-emerald-50'>
        <div className='flex items-center gap-3 text-slate-600'>
          <Loader2 className='h-6 w-6 animate-spin text-blue-600' />
          正在进入候场...
        </div>
      </div>
    );
  }

  if (!room) {
    return (
      <div className='flex min-h-screen items-center justify-center bg-slate-50'>
        <Button onClick={onBack}>返回大厅</Button>
      </div>
    );
  }

  return (
    <div className='min-h-screen bg-gradient-to-br from-blue-50 via-slate-50 to-emerald-50'>
      <header className='border-b border-slate-200 bg-white shadow-sm'>
        <div className='mx-auto flex max-w-7xl items-center justify-between px-4 py-4'>
          <div className='flex items-center gap-3'>
            <Button variant='ghost' size='sm' onClick={onBack}>
              <ArrowLeft className='mr-2 h-4 w-4' />
              返回
            </Button>
            <div>
              <div className='flex flex-wrap items-center gap-2'>
                <h1 className='text-2xl font-bold text-slate-900'>{room.room_name}</h1>
                <Badge variant='outline' className={statusBadgeClass(room.status)}>
                  {roomStatusLabelMap[room.status]}
                </Badge>
                {room.mode === 'teacher_reserved' && (
                  <Badge variant='outline' className='bg-amber-50 text-amber-700 border-amber-200'>
                    预约房间
                  </Badge>
                )}
              </div>
              <p className='mt-1 text-sm text-slate-500'>{room.topic}</p>
            </div>
          </div>
          <div className='flex items-center gap-2'>
            <Button variant='outline' disabled={refreshing} onClick={() => loadRoom('manual')}>
              {refreshing ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <RefreshCw className='mr-2 h-4 w-4' />}
              刷新
            </Button>
            {isJoined ? (
              <Button onClick={() => onEnterDebate(room.room_id)}>
                {canModerate ? <Play className='mr-2 h-4 w-4' /> : <DoorOpen className='mr-2 h-4 w-4' />}
                {canModerate ? '进入辩论室开赛' : '进入辩论室'}
              </Button>
            ) : room.visibility === 'private' ? (
              <Button disabled={!room.can_join} onClick={() => setJoinPrivateOpen(true)}>
                <Lock className='mr-2 h-4 w-4' />
                密码加入
              </Button>
            ) : (
              <Button disabled={!room.can_join || joining} onClick={handleJoinPublic}>
                {joining ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <DoorOpen className='mr-2 h-4 w-4' />}
                加入房间
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className='mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[minmax(0,1.2fr)_360px]'>
        <div className='space-y-6'>
          <Card className='border-slate-200 bg-white shadow-sm'>
            <CardHeader>
              <CardTitle>候场成员</CardTitle>
            </CardHeader>
            <CardContent>
              <div className='mb-4 h-3 overflow-hidden rounded-full bg-slate-100'>
                <div
                  className='h-full rounded-full bg-blue-600 transition-all'
                  style={{ width: `${Math.min(100, (room.current_count / Math.max(room.capacity, 1)) * 100)}%` }}
                />
              </div>
              <div className='mb-5 flex items-center justify-between text-sm text-slate-600'>
                <span>人数进度：{room.current_count}/{room.capacity}</span>
                <span>{room.available_roles?.length ? `剩余 ${room.available_roles.length} 个席位` : '席位已满'}</span>
              </div>

              <div className='grid gap-3 md:grid-cols-2'>
                {(['debater_1', 'debater_2', 'debater_3', 'debater_4'] as LobbyRoomMember['role'][]).map((role) => {
                  const member = memberByRole.get(role);
                  const moderator = !!member?.can_moderate;
                  return (
                    <div
                      key={role}
                      className={`rounded-lg border p-4 ${
                        member ? 'border-slate-200 bg-white' : 'border-dashed border-slate-300 bg-slate-50'
                      }`}
                    >
                      <div className='mb-2 flex items-center justify-between gap-2'>
                        <Badge variant='outline' className='bg-blue-50 text-blue-700 border-blue-200'>
                          {roleLabel(role)}
                        </Badge>
                        {moderator && (
                          <Badge className='bg-amber-500 text-white'>
                            <Crown className='mr-1 h-3 w-3' />
                            主持人
                          </Badge>
                        )}
                      </div>
                      {member ? (
                        <div className='flex items-center gap-3'>
                          <div className='flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 font-medium text-slate-700'>
                            {(member.name || '?').charAt(0)}
                          </div>
                          <div className='min-w-0'>
                            <div className='font-medium text-slate-900'>{member.name}</div>
                            <div className='text-xs text-slate-500'>
                              {member.stance ? stanceLabelMap[member.stance] : '正方'} · {member.role_reason || '角色说明待定'}
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className='py-3 text-sm text-slate-500'>等待同学加入</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>

        <aside className='space-y-6'>
          <Card className='border-slate-200 bg-white shadow-sm'>
            <CardHeader>
              <CardTitle>房间信息</CardTitle>
            </CardHeader>
            <CardContent className='space-y-4 text-sm text-slate-600'>
              <div className='flex items-center justify-between'>
                <span className='flex items-center gap-2'>
                  {room.visibility === 'private' ? <Lock className='h-4 w-4 text-amber-600' /> : <Unlock className='h-4 w-4 text-emerald-600' />}
                  房间类型
                </span>
                <span>{room.visibility === 'private' ? '私密' : '公开'} · {room.has_password ? '已设密码' : '无密码'}</span>
              </div>
              <div className='flex items-center justify-between'>
                <span className='flex items-center gap-2'>
                  <Shield className='h-4 w-4 text-purple-600' />
                  当前主持人
                </span>
                <span>{room.host_name || '待定'}</span>
              </div>
              <div className='flex items-center justify-between'>
                <span className='flex items-center gap-2'>
                  <CalendarClock className='h-4 w-4 text-blue-600' />
                  开赛时间
                </span>
                <span>{formatDateTime(room.scheduled_start_time)}</span>
              </div>
              <div className='flex items-center justify-between'>
                <span>倒计时</span>
                <span>{formatRelativeStart(room.scheduled_start_time)}</span>
              </div>
              <div className='flex items-center justify-between'>
                <span>允许旁观</span>
                <span>{room.allow_spectators ? '是' : '否'}</span>
              </div>
              <div className='flex items-center justify-between'>
                <span className='flex items-center gap-2'>
                  <Users className='h-4 w-4 text-slate-500' />
                  我的权限
                </span>
                <span>
                  {isJoined
                    ? `${roleLabel(currentPermissions?.role || room.current_user_role)}${canModerate ? ' · 主持' : ''}`
                    : room.join_block_reason || '尚未加入'}
                </span>
              </div>
            </CardContent>
          </Card>
        </aside>
      </main>

      <JoinPrivateRoomDialog
        open={joinPrivateOpen}
        room={room}
        onOpenChange={setJoinPrivateOpen}
        onJoined={(next) => {
          setRoom(next);
          toast({ variant: 'success', title: '加入成功' });
        }}
      />
    </div>
  );
};

export default LobbyRoomWaiting;
