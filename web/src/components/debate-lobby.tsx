import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import CreateRoomDialog from '@/components/create-room-dialog';
import DebateLobbyFilter, {
  type LobbyFilterValue,
} from '@/components/debate-lobby-filter';
import JoinPrivateRoomDialog from '@/components/join-private-room-dialog';
import LobbyRoomCard from '@/components/lobby-room-card';
import { useToast } from '@/hooks/use-toast';
import StudentService, { type LobbyRoom } from '@/services/student.service';
import {
  ArrowLeft,
  Loader2,
  Plus,
  RefreshCw,
  Sparkles,
  Users,
} from 'lucide-react';

interface DebateLobbyProps {
  onBack: () => void;
  onEnterRoom: (roomId: string) => void;
}

const defaultFilter: LobbyFilterValue = {
  keyword: '',
  visibility: 'all',
  status: 'all',
  occupancy: 'all',
  sort: 'latest',
};

const DebateLobby: React.FC<DebateLobbyProps> = ({ onBack, onEnterRoom }) => {
  const { toast } = useToast();
  const [filter, setFilter] = useState<LobbyFilterValue>(defaultFilter);
  const [rooms, setRooms] = useState<LobbyRoom[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [privateRoom, setPrivateRoom] = useState<LobbyRoom | null>(null);

  const loadRooms = useCallback(
    async (mode: 'initial' | 'manual' = 'manual') => {
      try {
        if (mode === 'initial') setLoading(true);
        if (mode === 'manual') setRefreshing(true);

        const data = await StudentService.getLobbyRooms({
          keyword: filter.keyword || undefined,
          visibility: filter.visibility,
          status: filter.status,
          sort: filter.sort,
          page: 1,
          page_size: 60,
        });

        setRooms(data.items);
        setTotal(data.total);
      } catch (err: any) {
        toast({
          variant: 'destructive',
          title: '大厅加载失败',
          description:
            err?.response?.data?.detail || err?.message || '请稍后重试',
        });
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [filter.keyword, filter.sort, filter.status, filter.visibility, toast]
  );

  useEffect(() => {
    void loadRooms('initial');
  }, [loadRooms]);

  const filteredRooms = useMemo(() => {
    if (filter.occupancy === 'available') {
      return rooms.filter((room) => room.current_count < room.capacity);
    }
    if (filter.occupancy === 'almost_full') {
      return rooms.filter((room) => room.current_count >= room.capacity - 1);
    }
    return rooms;
  }, [filter.occupancy, rooms]);

  const waitingRooms = filteredRooms.filter((room) => room.status === 'waiting')
    .length;

  const availableSeats = filteredRooms.reduce((sum, room) => {
    return sum + Math.max(0, room.capacity - room.current_count);
  }, 0);

  const handleJoin = async (room: LobbyRoom) => {
    try {
      const detail = await StudentService.getLobbyRoomDetail(room.room_id);
      const joined =
        !!detail.current_user_permissions?.is_joined ||
        !!detail.is_current_user_joined;

      if (joined) {
        onEnterRoom(detail.room_id);
        return;
      }

      if (detail.visibility === 'private') {
        setPrivateRoom(detail);
        return;
      }

      const next = await StudentService.joinLobbyRoom(detail.room_id);
      toast({
        variant: 'success',
        title: '加入成功',
        description: `你已进入 ${next.room_name}`,
      });
      onEnterRoom(next.room_id);
    } catch (err: any) {
      toast({
        variant: 'destructive',
        title: '加入失败',
        description:
          err?.response?.data?.detail || err?.message || '请稍后重试',
      });
    }
  };

  return (
    <div className="student-container py-6 pb-14">
      <div className="space-y-5">
        <section className="student-card px-5 py-6 md:px-6">
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  variant="outline"
                  onClick={onBack}
                  className="student-light-button h-auto px-4 py-2"
                >
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  返回
                </Button>
              </div>

              <div>
                <h1 className="student-section-title text-[1.95rem] md:text-[2.25rem]">
                  匹配大厅
                </h1>
                <p className="student-section-copy mt-3 max-w-2xl">
                  先筛选可加入的房间，再决定直接加入还是自己创建房间。创建后会自动进入候场。
                </p>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row">
                <Button
                  onClick={() => setCreateOpen(true)}
                  className="student-dark-button h-auto px-5 py-3"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  创建房间
                </Button>
                <Button
                  variant="outline"
                  disabled={refreshing || loading}
                  onClick={() => loadRooms('manual')}
                  className="student-light-button h-auto px-5 py-3"
                >
                  {refreshing || loading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="mr-2 h-4 w-4" />
                  )}
                  刷新大厅
                </Button>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
              <div className="student-card-soft-blue p-5">
                <div className="text-sm text-slate-500">房间总数</div>
                <div className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-slate-900">
                  {total}
                </div>
              </div>
              <div className="student-card-soft-peach p-5">
                <div className="text-sm text-slate-500">候场中房间</div>
                <div className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-slate-900">
                  {waitingRooms}
                </div>
              </div>
              <div className="student-card-soft-lavender p-5">
                <div className="text-sm text-slate-500">可用席位</div>
                <div className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-slate-900">
                  {availableSeats}
                </div>
              </div>
            </div>
          </div>
        </section>

        <DebateLobbyFilter
          value={filter}
          onChange={setFilter}
          onReset={() => setFilter(defaultFilter)}
        />

        {loading ? (
          <div className="student-card flex items-center justify-center gap-3 px-5 py-16 text-slate-500">
            <Loader2 className="h-6 w-6 animate-spin" />
            正在加载大厅房间...
          </div>
        ) : filteredRooms.length === 0 ? (
          <section className="student-card px-5 py-14 text-center md:px-6">
            <div className="student-icon-bubble mx-auto mb-4 h-12 w-12 bg-white text-slate-900">
              <Users className="h-5 w-5" />
            </div>
            <div className="text-lg font-semibold text-slate-900">
              暂无符合条件的房间
            </div>
          </section>
        ) : (
          <section className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Sparkles className="h-4 w-4" />
                当前共找到 {filteredRooms.length} 个房间
              </div>
              <Badge className="student-pill">
                <Users className="mr-1 h-3.5 w-3.5" />
                {total} 个大厅房间
              </Badge>
            </div>
            <div className="grid gap-4 xl:grid-cols-2">
              {filteredRooms.map((room) => (
                <LobbyRoomCard
                  key={room.room_id}
                  room={room}
                  onJoin={handleJoin}
                  onView={(targetRoom) => onEnterRoom(targetRoom.room_id)}
                />
              ))}
            </div>
          </section>
        )}
      </div>

      <CreateRoomDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(room) => {
          setRooms((prev) => [
            room,
            ...prev.filter((item) => item.room_id !== room.room_id),
          ]);
          onEnterRoom(room.room_id);
        }}
      />
      <JoinPrivateRoomDialog
        open={!!privateRoom}
        room={privateRoom}
        onOpenChange={(open) => {
          if (!open) setPrivateRoom(null);
        }}
        onJoined={(room) => {
          toast({
            variant: 'success',
            title: '加入成功',
          });
          onEnterRoom(room.room_id);
        }}
      />
    </div>
  );
};

export default DebateLobby;
