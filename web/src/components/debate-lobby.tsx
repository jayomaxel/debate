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
import { ArrowLeft, Loader2, Plus, RefreshCw, Users } from 'lucide-react';

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

  const loadRooms = useCallback(async (mode: 'initial' | 'manual' = 'manual') => {
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
        description: err?.response?.data?.detail || err?.message || '请稍后重试',
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filter.keyword, filter.visibility, filter.status, filter.sort, toast]);

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

  const handleJoin = async (room: LobbyRoom) => {
    try {
      const detail = await StudentService.getLobbyRoomDetail(room.room_id);
      const joined = !!detail.current_user_permissions?.is_joined || !!detail.is_current_user_joined;
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
        description: `你的席位：${next.participant_role || next.current_user_role || '已分配'}`,
      });
      onEnterRoom(next.room_id);
    } catch (err: any) {
      toast({
        variant: 'destructive',
        title: '加入失败',
        description: err?.response?.data?.detail || err?.message || '请稍后重试',
      });
    }
  };

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
              <h1 className='text-2xl font-bold text-slate-900'>匹配大厅</h1>
              <p className='text-sm text-slate-500'>查找同班房间，创建练习赛，进入自发组队候场</p>
            </div>
          </div>
          <div className='flex items-center gap-2'>
            <Badge variant='outline' className='bg-blue-50 text-blue-700 border-blue-200'>
              <Users className='mr-1 h-4 w-4' />
              {total} 个房间
            </Badge>
            <Button variant='outline' disabled={refreshing || loading} onClick={() => loadRooms('manual')}>
              {refreshing || loading ? (
                <Loader2 className='mr-2 h-4 w-4 animate-spin' />
              ) : (
                <RefreshCw className='mr-2 h-4 w-4' />
              )}
              刷新
            </Button>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className='mr-2 h-4 w-4' />
              创建房间
            </Button>
          </div>
        </div>
      </header>

      <main className='mx-auto max-w-7xl px-4 py-6'>
        <DebateLobbyFilter
          value={filter}
          onChange={setFilter}
          onReset={() => setFilter(defaultFilter)}
        />

        {loading ? (
          <div className='flex items-center justify-center gap-2 py-20 text-slate-500'>
            <Loader2 className='h-6 w-6 animate-spin' />
            正在加载大厅房间...
          </div>
        ) : filteredRooms.length === 0 ? (
          <div className='mt-6 rounded-lg border border-dashed border-slate-300 bg-white py-16 text-center'>
            <Users className='mx-auto mb-3 h-10 w-10 text-slate-300' />
            <p className='font-medium text-slate-700'>暂无符合条件的房间</p>
            <p className='mt-1 text-sm text-slate-500'>可以调整筛选条件，或创建一个新的自发组队房间。</p>
          </div>
        ) : (
          <div className='mt-6 grid gap-4 lg:grid-cols-2'>
            {filteredRooms.map((room) => (
              <LobbyRoomCard
                key={room.room_id}
                room={room}
                onJoin={handleJoin}
                onView={(targetRoom) => onEnterRoom(targetRoom.room_id)}
              />
            ))}
          </div>
        )}
      </main>

      <CreateRoomDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(room) => {
          setRooms((prev) => [room, ...prev.filter((item) => item.room_id !== room.room_id)]);
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
