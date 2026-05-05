import React, { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import StudentReservationCard from '@/components/student-reservation-card';
import StudentService, { type StudentReservation } from '@/services/student.service';
import { CalendarClock, Loader2, RefreshCw } from 'lucide-react';

interface StudentReservationListProps {
  onEnterRoom?: (roomId: string) => void;
}

const StudentReservationList: React.FC<StudentReservationListProps> = ({ onEnterRoom }) => {
  const [reservations, setReservations] = useState<StudentReservation[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async (mode: 'initial' | 'manual' = 'manual') => {
    try {
      if (mode === 'initial') setLoading(true);
      if (mode === 'manual') setRefreshing(true);
      const reservationData = await StudentService.getMyReservations({
        include_cancelled: true,
        page: 1,
        page_size: 10,
      });
      setReservations(reservationData.items);
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
    <div className='mb-8'>
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
    </div>
  );
};

export default StudentReservationList;
