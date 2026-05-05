import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  CalendarClock,
  DoorOpen,
  Loader2,
  ShieldCheck,
  Sparkles,
  Swords,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import StudentReservationCard from '@/components/student-reservation-card';
import { useToast } from '@/hooks/use-toast';
import { useStudentAssessment } from '@/hooks/use-student-assessment';
import { usePageActivityRefresh } from '@/hooks/use-page-activity-refresh';
import StudentService from '@/services/student.service';
import type { Debate, LobbyRoom, StudentReservation } from '@/services/student.service';
import {
  roomStatusLabelMap,
} from '@/lib/reservation-display';
import competitionAsideImage from '../../../pic/27c72e318f175936bf07d8af3a692d80.jpg';

interface StudentCompetitionHubProps {
  onNavigateToWaiting?: () => void;
  onNavigateToSettings?: (tab?: 'info' | 'password' | 'ability') => void;
  onNavigateToPostMatch?: (debateId: string) => void;
  onNavigateToLobby?: () => void;
  onNavigateToLobbyRoom?: (roomId: string) => void;
}

const roleLabelMap = {
  debater_1: '一辩',
  debater_2: '二辩',
  debater_3: '三辩',
  debater_4: '四辩',
} as const;

const sortJoinedTeacherDebates = (debates: Debate[]) =>
  debates
    .filter(
      (debate) =>
        debate.is_joined &&
        (debate.mode === 'teacher_assigned' || debate.room_source === 'teacher_created')
    )
    .slice()
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));

const sortLobbyRooms = (rooms: LobbyRoom[]) =>
  rooms
    .slice()
    .sort((a, b) => Date.parse(b.created_at || '') - Date.parse(a.created_at || ''));

const isVisibleCompetitionReservation = (reservation: StudentReservation) =>
  reservation.status !== 'cancelled' &&
  reservation.invitation_status !== 'rejected' &&
  reservation.invitation_status !== 'expired' &&
  reservation.checkin_status !== 'absent';

const getStatusLabel = (status?: Debate['status']) => {
  switch (status) {
    case 'published':
      return '等待开赛';
    case 'in_progress':
      return '进行中';
    case 'completed':
      return '已结束';
    case 'draft':
      return '草稿中';
    default:
      return '未加入';
  }
};

export default function StudentCompetitionHub({
  onNavigateToWaiting,
  onNavigateToSettings,
  onNavigateToPostMatch,
  onNavigateToLobby,
  onNavigateToLobbyRoom,
}: StudentCompetitionHubProps) {
  const { toast } = useToast();
  const { needsAssessment, loading: assessmentLoading } =
    useStudentAssessment(true);
  const [invitationCode, setInvitationCode] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [joining, setJoining] = useState(false);
  const [teacherDebates, setTeacherDebates] = useState<Debate[]>([]);
  const [studentLobbyRooms, setStudentLobbyRooms] = useState<LobbyRoom[]>([]);
  const [teacherReservations, setTeacherReservations] = useState<StudentReservation[]>([]);

  const loadCompetitionContext = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent === true;

      try {
        if (silent) {
          setRefreshing(true);
        } else {
          setLoading(true);
        }

        const [debates, myLobbyRooms, reservationResponse] = await Promise.all([
          StudentService.getAvailableDebates({
            force: silent,
          }).catch(() => []),
          StudentService.getMyLobbyRooms().catch(() => []),
          StudentService.getMyReservations({
            include_cancelled: false,
            page: 1,
            page_size: 20,
          }).catch(() => ({ items: [] as StudentReservation[] })),
        ]);

        setTeacherDebates(sortJoinedTeacherDebates(debates));
        setStudentLobbyRooms(sortLobbyRooms(myLobbyRooms));
        setTeacherReservations(
          (reservationResponse.items || []).filter(isVisibleCompetitionReservation)
        );
      } catch (error: any) {
        console.error('[StudentCompetitionHub] Failed to load data:', error);
        if (!silent) {
          toast({
            variant: 'destructive',
            title: '加载失败',
            description: error?.message || '比赛区数据加载失败',
          });
        }
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [toast]
  );

  useEffect(() => {
    void loadCompetitionContext();
  }, [loadCompetitionContext]);

  usePageActivityRefresh(() => loadCompetitionContext({ silent: true }), {
    enabled: !loading,
    intervalMs: 12000,
  });

  const activeTeacherDebate = teacherDebates[0] || null;
  const activeStudentRoom = studentLobbyRooms[0] || null;

  const canJoin = !needsAssessment;
  const actionTitle = useMemo(() => {
    if (needsAssessment) {
      return '先完成能力评估';
    }

    if (activeTeacherDebate?.status === 'completed') {
      return '查看赛后分析';
    }

    if (activeTeacherDebate || activeStudentRoom) {
      return '继续比赛';
    }

    return '加入本场辩论';
  }, [activeStudentRoom, activeTeacherDebate, needsAssessment]);

  const handleReservationChanged = useCallback((next: StudentReservation) => {
    setTeacherReservations((current) => {
      const remaining = current.filter(
        (item) => item.reservation_id !== next.reservation_id
      );

      if (!isVisibleCompetitionReservation(next)) {
        return remaining;
      }

      return [next, ...remaining];
    });
  }, []);

  const handleJoinDebate = async () => {
    if (!canJoin) {
      toast({
        variant: 'destructive',
        title: '请先完成能力评估',
        description: '完成评估后，比赛区入口才会解锁。',
      });
      onNavigateToSettings?.('ability');
      return;
    }

    if (invitationCode.trim().length !== 6) {
      toast({
        variant: 'destructive',
        title: '邀请码格式不正确',
        description: '请输入 6 位邀请码。',
      });
      return;
    }

    try {
      setJoining(true);
      const debate = await StudentService.joinDebate({
        invitation_code: invitationCode.trim(),
      });
      setTeacherDebates((current) => sortJoinedTeacherDebates([debate, ...current]));
      setInvitationCode('');
      onNavigateToWaiting?.();
    } catch (error: any) {
      toast({
        variant: 'destructive',
        title: '加入失败',
        description: error?.message || '加入本场辩论失败',
      });
    } finally {
      setJoining(false);
    }
  };

  if (loading || assessmentLoading) {
    return (
      <div className="student-container flex min-h-[70vh] items-center justify-center py-10">
        <div className="student-card min-w-[280px] px-8 py-10 text-center">
          <Loader2 className="mx-auto mb-4 h-10 w-10 animate-spin text-slate-700" />
          <p className="text-slate-600">正在加载比赛区...</p>
        </div>
      </div>
    );
  }

  return (
      <div className="student-container py-6 pb-14">
      <div className="student-page-split grid gap-5 lg:grid-cols-[minmax(0,1.32fr)_minmax(320px,0.88fr)]">
        <div className="space-y-5">
        <section className="student-card px-5 py-6 md:px-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-2xl">
              <div className="student-kicker">
                <Swords className="h-4 w-4" />
                比赛区
              </div>
              <h1 className="mt-4 text-[2rem] font-semibold leading-[1.06] tracking-[-0.05em] text-slate-900 md:text-[2.35rem]">
                {actionTitle}
              </h1>
            </div>
          </div>

          <div className="mt-6">
            {!canJoin ? (
              <div className="student-card-soft-peach p-5">
                <div className="flex items-start gap-4">
                  <div className="student-icon-bubble h-12 w-12 bg-white text-slate-900">
                    <ShieldCheck className="h-5 w-5 text-amber-700" />
                  </div>
                  <div className="space-y-3">
                    <div className="text-lg font-semibold tracking-[-0.03em] text-slate-900">
                      能力评估尚未完成
                    </div>
                    <Button
                      onClick={() => onNavigateToSettings?.('ability')}
                      className="student-dark-button h-auto"
                    >
                      现在去评估
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ) : activeTeacherDebate || activeStudentRoom ? (
              <div className="space-y-4">
                {activeTeacherDebate ? (
                  <div className="student-card-soft-blue p-5">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
                          老师安排的比赛
                        </div>
                        <div className="mt-2.5 text-[1.6rem] font-semibold tracking-[-0.04em] text-slate-900">
                          {activeTeacherDebate.topic}
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <Badge className="student-pill">
                            邀请码 {activeTeacherDebate.invitation_code}
                          </Badge>
                          <Badge className="student-pill">
                            {getStatusLabel(activeTeacherDebate.status)}
                          </Badge>
                          {activeTeacherDebate.role ? (
                            <Badge className="student-pill">
                              {roleLabelMap[activeTeacherDebate.role]}
                            </Badge>
                          ) : null}
                        </div>
                      </div>
                    </div>

                    <div className="mt-5">
                      {activeTeacherDebate.status === 'completed' ? (
                        <Button
                          onClick={() => onNavigateToPostMatch?.(activeTeacherDebate.id)}
                          className="student-dark-button h-auto"
                        >
                          进入赛后分析页
                          <ArrowRight className="ml-2 h-4 w-4" />
                        </Button>
                      ) : (
                        <Button
                          onClick={onNavigateToWaiting}
                          className="student-dark-button h-auto"
                        >
                          进入等待与准备页
                          <ArrowRight className="ml-2 h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                ) : null}

                {activeStudentRoom ? (
                  <div className="student-card-soft-lavender p-5">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
                          我的自主房间
                        </div>
                        <div className="mt-2.5 text-[1.6rem] font-semibold tracking-[-0.04em] text-slate-900">
                          {activeStudentRoom.topic}
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <Badge className="student-pill">
                            {activeStudentRoom.room_name}
                          </Badge>
                          <Badge className="student-pill">
                            {roomStatusLabelMap[activeStudentRoom.status] || activeStudentRoom.status}
                          </Badge>
                          {activeStudentRoom.current_user_role ? (
                            <Badge className="student-pill">
                              {roleLabelMap[
                                activeStudentRoom.current_user_role as keyof typeof roleLabelMap
                              ] || activeStudentRoom.current_user_role}
                            </Badge>
                          ) : null}
                        </div>
                      </div>
                    </div>

                    <div className="mt-5">
                      <Button
                        onClick={() => onNavigateToLobbyRoom?.(activeStudentRoom.room_id)}
                        className="student-dark-button h-auto"
                      >
                        进入我的自主房间
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="student-card-soft-lavender p-5">
                <div className="max-w-lg">
                  <div className="mt-2.5 text-lg font-semibold tracking-[-0.03em] text-slate-900">
                    用 6 位邀请码加入本场辩论
                  </div>
                </div>

                <div className="mt-5 space-y-3">
                  <Input
                    value={invitationCode}
                    onChange={(event) =>
                      setInvitationCode(event.target.value.trim().toUpperCase())
                    }
                    placeholder="例如 ABC123"
                    maxLength={6}
                    className="h-14 rounded-[16px] border-black/10 bg-white/85 text-center font-mono text-lg tracking-[0.25em] text-slate-900"
                  />
                  <Button
                    onClick={handleJoinDebate}
                    disabled={joining}
                    className="student-dark-button h-auto w-full justify-center"
                  >
                    {joining ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        正在加入...
                      </>
                    ) : (
                      <>
                        加入本场辩论
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </>
                    )}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="student-card px-5 py-6 md:px-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="student-kicker">
                <CalendarClock className="h-4 w-4" />
                我的预约辩论
              </div>
              <h2 className="mt-3 text-[1.55rem] font-semibold tracking-[-0.04em] text-slate-900">
                已预约辩论
              </h2>
            </div>
            <Badge className="student-pill">{teacherReservations.length} 场</Badge>
          </div>

          <div className="mt-5 space-y-3">
            {teacherReservations.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-5 py-8 text-sm text-slate-500">
                当前没有待处理的预约辩论场次。
              </div>
            ) : (
              teacherReservations.map((reservation) => (
                <StudentReservationCard
                  key={reservation.reservation_id}
                  reservation={reservation}
                  onChanged={handleReservationChanged}
                  onEnterRoom={(roomId) => onNavigateToLobbyRoom?.(roomId)}
                />
              ))
            )}
          </div>
        </section>
        </div>

        <div className="student-page-aside space-y-5">
          <section className="student-card overflow-hidden px-5 py-6 md:px-6">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex min-w-0 items-center gap-4">
                <div className="student-icon-bubble h-12 w-12 shrink-0">
                  <DoorOpen className="h-5 w-5 text-slate-800" />
                </div>
                <div className="min-w-0">
                  <h2 className="text-[1.45rem] font-semibold tracking-[-0.03em] text-slate-950">
                    匹配大厅
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    加入同学发起的房间。
                  </p>
                </div>
              </div>
              <Button
                variant="outline"
                onClick={onNavigateToLobby}
                className="student-light-button h-auto"
              >
                进入匹配大厅
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </section>

          <section className="space-y-3">
            <div className="grid gap-3">
              <StatusItem
                icon={<Sparkles className="h-4 w-4 text-slate-700" />}
                label="能力评估"
                value={canJoin ? '已完成' : '待完成'}
                tone={canJoin ? 'student-card-soft-blue' : 'student-card-soft-peach'}
              />
              <Button
                variant="outline"
                onClick={() => void loadCompetitionContext({ silent: true })}
                disabled={refreshing}
                className="student-light-button h-auto justify-start"
              >
                {refreshing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="mr-2 h-4 w-4" />
                )}
                刷新比赛状态
              </Button>
            </div>
          </section>

          <section className="student-card overflow-hidden p-0">
            <img
              src={competitionAsideImage}
              alt=""
              className="aspect-square w-full object-contain"
            />
          </section>
        </div>
      </div>
    </div>
  );
}

function StatusItem({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone: string;
}) {
  return (
    <div className={`${tone} p-5`}>
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-slate-500">
        {icon}
        <span>{label}</span>
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-[-0.05em] text-slate-900">
        {value}
      </div>
    </div>
  );
}
