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
  Sparkles,
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

const roomInfoCardClassName =
  'student-card overflow-hidden border-0 shadow-none';

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

  const loadRoom = useCallback(
    async (mode: 'initial' | 'manual' | 'poll' = 'manual') => {
      try {
        if (mode === 'initial') setLoading(true);
        if (mode === 'manual') setRefreshing(true);

        const data = await StudentService.getLobbyRoomDetail(roomId);
        setRoom(data);
      } catch (err: any) {
        toast({
          variant: 'destructive',
          title: '房间加载失败',
          description:
            err?.response?.data?.detail || err?.message || '请稍后重试',
        });
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [roomId, toast]
  );

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

  const members = useMemo(
    () => [...(room?.members || [])].sort(memberSort),
    [room?.members]
  );
  const currentPermissions = room?.current_user_permissions;
  const isJoined =
    !!currentPermissions?.is_joined || !!room?.is_current_user_joined;
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
        description: `你的席位已分配为 ${roleLabel(
          next.participant_role || next.current_user_role
        )}`,
      });
    } catch (err: any) {
      toast({
        variant: 'destructive',
        title: '加入失败',
        description:
          err?.response?.data?.detail || err?.message || '请稍后重试',
      });
    } finally {
      setJoining(false);
    }
  };

  if (loading) {
    return (
      <div className="student-container flex min-h-[70vh] items-center justify-center py-10">
        <div className="student-card min-w-[280px] px-8 py-10 text-center">
          <Loader2 className="mx-auto mb-4 h-10 w-10 animate-spin text-slate-700" />
          <p className="text-slate-600">正在进入候场...</p>
        </div>
      </div>
    );
  }

  if (!room) {
    return (
      <div className="student-container flex min-h-[70vh] items-center justify-center py-10">
        <div className="student-card px-8 py-10 text-center">
          <Button onClick={onBack} className="student-dark-button h-auto">
            返回大厅
          </Button>
        </div>
      </div>
    );
  }

  const occupancy = Math.min(
    100,
    (room.current_count / Math.max(room.capacity, 1)) * 100
  );

  return (
    <div className="student-container py-6 pb-14">
      <div className="space-y-5">
        <section className="student-card px-5 py-6 md:px-6">
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onBack}
                  className="student-light-button h-auto px-4 py-2"
                >
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  返回大厅
                </Button>
              </div>

              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="student-section-title text-[1.95rem] md:text-[2.25rem]">
                    {room.room_name}
                  </h1>
                  <Badge variant="outline" className={statusBadgeClass(room.status)}>
                    {roomStatusLabelMap[room.status]}
                  </Badge>
                  {room.mode === 'teacher_reserved' ? (
                    <Badge className="student-pill">预约房间</Badge>
                  ) : null}
                </div>
                <p className="student-section-copy mt-3 max-w-2xl">
                  {room.topic}
                </p>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row">
                <Button
                  variant="outline"
                  disabled={refreshing}
                  onClick={() => loadRoom('manual')}
                  className="student-light-button h-auto px-5 py-3"
                >
                  {refreshing ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="mr-2 h-4 w-4" />
                  )}
                  刷新状态
                </Button>

                {isJoined ? (
                  <Button
                    onClick={() => onEnterDebate(room.room_id)}
                    className="student-dark-button h-auto px-5 py-3"
                  >
                    {canModerate ? (
                      <Play className="mr-2 h-4 w-4" />
                    ) : (
                      <DoorOpen className="mr-2 h-4 w-4" />
                    )}
                    {canModerate ? '进入辩论并开始' : '进入辩论'}
                  </Button>
                ) : room.visibility === 'private' ? (
                  <Button
                    disabled={!room.can_join}
                    onClick={() => setJoinPrivateOpen(true)}
                    className="student-dark-button h-auto px-5 py-3"
                  >
                    <Lock className="mr-2 h-4 w-4" />
                    密码加入
                  </Button>
                ) : (
                  <Button
                    disabled={!room.can_join || joining}
                    onClick={handleJoinPublic}
                    className="student-dark-button h-auto px-5 py-3"
                  >
                    {joining ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <DoorOpen className="mr-2 h-4 w-4" />
                    )}
                    加入房间
                  </Button>
                )}
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
              <div className="student-card-soft-blue p-5">
                <div className="text-sm text-slate-500">已入座人数</div>
                <div className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-slate-900">
                  {room.current_count}
                  <span className="ml-1 text-sm font-medium text-slate-500">
                    / {room.capacity}
                  </span>
                </div>
              </div>
              <div className="student-card-soft-peach p-5">
                <div className="text-sm text-slate-500">剩余席位</div>
                <div className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-slate-900">
                  {room.available_roles?.length || 0}
                </div>
              </div>
              <div className="student-card-soft-lavender p-5">
                <div className="text-sm text-slate-500">开赛倒计时</div>
                <div className="mt-2 text-lg font-semibold text-slate-900">
                  {formatRelativeStart(room.scheduled_start_time)}
                </div>
              </div>
            </div>
          </div>
        </section>

        <main className="student-page-split grid gap-5">
          <div className="space-y-5">
            <Card className={roomInfoCardClassName}>
              <CardHeader className="px-5 pb-0 pt-5 md:px-6">
                <CardTitle className="text-lg text-slate-900">候场成员</CardTitle>
              </CardHeader>
              <CardContent className="px-5 pb-5 pt-5 md:px-6">
                <div className="h-2 overflow-hidden rounded-full bg-[#ece3d8]">
                  <div
                    className="h-full rounded-full bg-[#1b2436] transition-all"
                    style={{ width: `${occupancy}%` }}
                  />
                </div>
                <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600">
                  <span>
                    当前进度：{room.current_count}/{room.capacity}
                  </span>
                  <span>
                    {room.available_roles?.length
                      ? `剩余 ${room.available_roles.length} 个席位`
                      : '席位已满'}
                  </span>
                </div>

                <div className="mt-5 grid gap-3 md:grid-cols-2">
                  {(
                    ['debater_1', 'debater_2', 'debater_3', 'debater_4'] as LobbyRoomMember['role'][]
                  ).map((role) => {
                    const member = memberByRole.get(role);
                    const moderator = !!member?.can_moderate;

                    return (
                      <div
                        key={role}
                        className={
                          member
                            ? 'student-card-muted p-4'
                            : 'student-dashed-card p-4'
                        }
                      >
                        <div className="mb-3 flex items-center justify-between gap-2">
                          <Badge className="student-pill">{roleLabel(role)}</Badge>
                          {moderator ? (
                            <Badge className="bg-amber-500 text-white">
                              <Crown className="mr-1 h-3 w-3" />
                              主持人
                            </Badge>
                          ) : null}
                        </div>

                        {member ? (
                          <div className="flex items-center gap-3">
                            <div className="student-icon-bubble h-11 w-11 bg-white text-slate-900">
                              {(member.name || '?').charAt(0)}
                            </div>
                            <div className="min-w-0">
                              <div className="font-medium text-slate-900">
                                {member.name}
                              </div>
                              <div className="text-xs leading-5 text-slate-500">
                                {member.stance
                                  ? stanceLabelMap[member.stance]
                                  : '待定'}{' '}
                                · {member.role_reason || '角色说明待补充'}
                              </div>
                            </div>
                          </div>
                        ) : (
                          <div className="py-3 text-sm text-slate-500">
                            等待同学加入
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            {room.description ? (
              <section className="student-card-soft-lavender px-5 py-5 md:px-6">
                <div className="mb-2 flex items-center gap-2 font-medium text-slate-900">
                  <Sparkles className="h-4 w-4" />
                  房间说明
                </div>
                <p className="text-sm leading-7 text-slate-700">
                  {room.description}
                </p>
              </section>
            ) : null}
          </div>

          <aside className="student-page-aside space-y-5">
            <Card className={roomInfoCardClassName}>
              <CardHeader className="px-5 pb-0 pt-5 md:px-6">
                <CardTitle className="text-lg text-slate-900">房间信息</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 px-5 pb-5 pt-5 text-sm text-slate-600 md:px-6">
                <div className="student-card-muted flex items-center justify-between gap-4 px-4 py-3">
                  <span className="flex items-center gap-2">
                    {room.visibility === 'private' ? (
                      <Lock className="h-4 w-4 text-amber-600" />
                    ) : (
                      <Unlock className="h-4 w-4 text-emerald-600" />
                    )}
                    房间类型
                  </span>
                  <span className="text-right font-medium text-slate-900">
                    {room.visibility === 'private' ? '私密' : '公开'}
                    {room.has_password ? ' · 已设密码' : ' · 无密码'}
                  </span>
                </div>

                <div className="student-card-muted flex items-center justify-between gap-4 px-4 py-3">
                  <span className="flex items-center gap-2">
                    <Shield className="h-4 w-4 text-purple-600" />
                    当前主持人
                  </span>
                  <span className="font-medium text-slate-900">
                    {room.host_name || '待定'}
                  </span>
                </div>

                <div className="student-card-muted flex items-center justify-between gap-4 px-4 py-3">
                  <span className="flex items-center gap-2">
                    <CalendarClock className="h-4 w-4 text-blue-600" />
                    开赛时间
                  </span>
                  <span className="font-medium text-slate-900">
                    {formatDateTime(room.scheduled_start_time)}
                  </span>
                </div>

                <div className="student-card-muted flex items-center justify-between gap-4 px-4 py-3">
                  <span>倒计时</span>
                  <span className="font-medium text-slate-900">
                    {formatRelativeStart(room.scheduled_start_time)}
                  </span>
                </div>

                <div className="student-card-muted flex items-center justify-between gap-4 px-4 py-3">
                  <span>允许旁观</span>
                  <span className="font-medium text-slate-900">
                    {room.allow_spectators ? '是' : '否'}
                  </span>
                </div>

                <div className="student-card-muted flex items-center justify-between gap-4 px-4 py-3">
                  <span className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-slate-500" />
                    我的状态
                  </span>
                  <span className="text-right font-medium text-slate-900">
                    {isJoined
                      ? `${roleLabel(
                          currentPermissions?.role || room.current_user_role
                        )}${canModerate ? ' · 主持' : ''}`
                      : room.join_block_reason || '尚未加入'}
                  </span>
                </div>
              </CardContent>
            </Card>
          </aside>
        </main>
      </div>

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
