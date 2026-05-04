import React, { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import StudentReservationCard from '@/components/student-reservation-card';
import StudentService, {
  type LobbyRoom,
  type StudentReservation,
} from '@/services/student.service';
import { CalendarClock, DoorOpen, Loader2, RefreshCw, Users } from 'lucide-react';
import { formatDateTime, roomStatusLabelMap, statusBadgeClass } from '@/lib/reservation-display';

interface StudentReservationListProps {
  onEnterRoom?: (roomId: string) => void;
}

const StudentReservationList: React.FC<StudentReservationListProps> = ({ onEnterRoom }) => {
  const [reservations, setReservations] = useState<StudentReservation[]>([]);
  const [joinedRooms, setJoinedRooms] = useState<LobbyRoom[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async (mode: 'initial' | 'manual' = 'manual') => {
    try {
      if (mode === 'initial') setLoading(true);
      if (mode === 'manual') setRefreshing(true);
      const [reservationData, roomData] = await Promise.allSettled([
        StudentService.getMyReservations({ include_cancelled: true, page: 1, page_size: 10 }),
        StudentService.getMyLobbyRooms(),
      ]);

      if (reservationData.status === 'fulfilled') {
        setReservations(reservationData.value.items);
      }
      if (roomData.status === 'fulfilled') {
        setJoinedRooms(roomData.value.filter((room) => room.mode === 'student_lobby'));
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadData('initial');
  }, [loadData]);

  const handleReservationChanged = (next: StudentReservation) => {
    setReservations((prev) =>
      prev.map((item) => (item.reservation_id === next.reservation_id ? next : item))
    );
  };

  return (
    <div className='mb-8 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.8fr)]'>
      <Card className='border-slate-200 bg-white shadow-sm'>
        <CardHeader>
          <CardTitle className='flex flex-col gap-3 md:flex-row md:items-center md:justify-between'>
            <div className='flex items-center gap-2'>
              <CalendarClock className='h-5 w-5 text-blue-600' />
              预约辩论赛
              <Badge variant='outline'>{reservations.length} 场</Badge>
            </div>
            <Button
              variant='outline'
              size='sm'
              disabled={refreshing || loading}
              onClick={() => loadData('manual')}
            >
              {refreshing || loading ? (
                <Loader2 className='mr-2 h-4 w-4 animate-spin' />
              ) : (
                <RefreshCw className='mr-2 h-4 w-4' />
              )}
              刷新
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className='flex items-center justify-center gap-2 py-10 text-slate-500'>
              <Loader2 className='h-5 w-5 animate-spin' />
              正在加载预约...
            </div>
          ) : reservations.length === 0 ? (
            <div className='rounded-lg border border-dashed border-slate-300 bg-slate-50 py-10 text-center text-slate-500'>
              暂无预约辩论赛
            </div>
          ) : (
            <div className='space-y-3'>
              {reservations.map((reservation) => (
                <StudentReservationCard
                  key={reservation.reservation_id}
                  reservation={reservation}
                  onChanged={handleReservationChanged}
                  onEnterRoom={onEnterRoom}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className='border-slate-200 bg-white shadow-sm'>
        <CardHeader>
          <CardTitle className='flex items-center gap-2'>
            <Users className='h-5 w-5 text-emerald-600' />
            待加入房间
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className='flex items-center gap-2 py-8 text-sm text-slate-500'>
              <Loader2 className='h-4 w-4 animate-spin' />
              正在加载房间...
            </div>
          ) : joinedRooms.length === 0 ? (
            <div className='rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500'>
              暂无已加入且未开始的自发组队房间
            </div>
          ) : (
            <div className='space-y-3'>
              {joinedRooms.map((room) => (
                <div key={room.room_id} className='rounded-lg border border-slate-200 p-4'>
                  <div className='mb-2 flex items-center justify-between gap-2'>
                    <h4 className='line-clamp-1 font-medium text-slate-900'>{room.room_name}</h4>
                    <Badge variant='outline' className={statusBadgeClass(room.status)}>
                      {roomStatusLabelMap[room.status]}
                    </Badge>
                  </div>
                  <p className='line-clamp-2 text-sm text-slate-600'>{room.topic}</p>
                  <div className='mt-3 flex items-center justify-between gap-3 text-xs text-slate-500'>
                    <span>{room.current_count}/{room.capacity} 人</span>
                    <span>{formatDateTime(room.scheduled_start_time || room.created_at)}</span>
                  </div>
                  <Button className='mt-3 w-full' size='sm' onClick={() => onEnterRoom?.(room.room_id)}>
                    <DoorOpen className='mr-2 h-4 w-4' />
                    继续候场
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default StudentReservationList;
