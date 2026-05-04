import React, { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useToast } from '@/hooks/use-toast';
import {
  checkinStatusLabelMap,
  formatDateTime,
  formatRelativeStart,
  invitationStatusLabelMap,
  reservationStatusLabelMap,
  roleLabel,
  statusBadgeClass,
} from '@/lib/reservation-display';
import StudentService, { type StudentReservation } from '@/services/student.service';
import { CalendarClock, CheckCircle, Clock, DoorOpen, Loader2, X } from 'lucide-react';

interface StudentReservationCardProps {
  reservation: StudentReservation;
  onChanged?: (reservation: StudentReservation) => void;
  onEnterRoom?: (roomId: string) => void;
}

const StudentReservationCard: React.FC<StudentReservationCardProps> = ({
  reservation,
  onChanged,
  onEnterRoom,
}) => {
  const { toast } = useToast();
  const [submittingAction, setSubmittingAction] = useState<'accept' | 'reject' | 'check-in' | null>(null);

  const handleRespond = async (action: 'accept' | 'reject') => {
    try {
      setSubmittingAction(action);
      const next = await StudentService.respondReservationInvitation(reservation.reservation_id, action);
      onChanged?.(next);
      toast({
        variant: 'success',
        title: action === 'accept' ? '已接受预约' : '已拒绝预约',
        description: action === 'accept' ? '开赛前可在签到窗口进入候场。' : undefined,
      });
    } catch (err: any) {
      toast({
        variant: 'destructive',
        title: '操作失败',
        description: err?.response?.data?.detail || err?.message || '请稍后重试',
      });
    } finally {
      setSubmittingAction(null);
    }
  };

  const handleCheckIn = async () => {
    try {
      setSubmittingAction('check-in');
      const next = await StudentService.checkInReservation(reservation.reservation_id);
      onChanged?.(next);
      toast({
        variant: 'success',
        title: '签到成功',
        description: '已进入候场资格，可以前往房间等待开赛。',
      });
    } catch (err: any) {
      toast({
        variant: 'destructive',
        title: '签到失败',
        description: err?.response?.data?.detail || err?.message || '当前不可签到',
      });
    } finally {
      setSubmittingAction(null);
    }
  };

  const canRespond = reservation.invitation_status === 'pending' && reservation.status !== 'cancelled';
  const canEnter = reservation.room_entry_enabled || reservation.checkin_status === 'checked_in';

  return (
    <Card className='border-slate-200 bg-white shadow-sm'>
      <CardContent className='p-4'>
        <div className='flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between'>
          <div className='min-w-0 flex-1'>
            <div className='mb-2 flex flex-wrap items-center gap-2'>
              <Badge variant='outline' className={statusBadgeClass(reservation.status)}>
                {reservationStatusLabelMap[reservation.status] || reservation.status}
              </Badge>
              <Badge variant='outline' className='bg-slate-50 text-slate-700 border-slate-200'>
                {invitationStatusLabelMap[reservation.invitation_status]}
              </Badge>
              <Badge variant='outline' className='bg-white text-slate-700 border-slate-200'>
                {checkinStatusLabelMap[reservation.checkin_status]}
              </Badge>
            </div>

            <h4 className='line-clamp-2 text-base font-semibold text-slate-900'>
              {reservation.topic}
            </h4>
            <div className='mt-3 grid gap-2 text-sm text-slate-600 md:grid-cols-2'>
              <div className='flex items-center gap-2'>
                <CalendarClock className='h-4 w-4 text-blue-600' />
                {formatDateTime(reservation.scheduled_start_time)}
              </div>
              <div className='flex items-center gap-2'>
                <Clock className='h-4 w-4 text-amber-600' />
                {formatRelativeStart(reservation.scheduled_start_time)}
              </div>
              <div>预计时长：{reservation.duration} 分钟</div>
              <div>我的角色：{roleLabel(reservation.role)}</div>
              {reservation.teacher_name && <div>发起教师：{reservation.teacher_name}</div>}
            </div>
          </div>

          <div className='flex shrink-0 flex-wrap gap-2 lg:justify-end'>
            {canRespond && (
              <>
                <Button
                  size='sm'
                  variant='outline'
                  disabled={!!submittingAction}
                  onClick={() => handleRespond('reject')}
                  className='text-red-600 hover:bg-red-50 hover:text-red-700'
                >
                  {submittingAction === 'reject' ? (
                    <Loader2 className='mr-2 h-4 w-4 animate-spin' />
                  ) : (
                    <X className='mr-2 h-4 w-4' />
                  )}
                  拒绝
                </Button>
                <Button size='sm' disabled={!!submittingAction} onClick={() => handleRespond('accept')}>
                  {submittingAction === 'accept' ? (
                    <Loader2 className='mr-2 h-4 w-4 animate-spin' />
                  ) : (
                    <CheckCircle className='mr-2 h-4 w-4' />
                  )}
                  接受
                </Button>
              </>
            )}
            {reservation.can_check_in && (
              <Button size='sm' disabled={!!submittingAction} onClick={handleCheckIn}>
                {submittingAction === 'check-in' ? (
                  <Loader2 className='mr-2 h-4 w-4 animate-spin' />
                ) : (
                  <CheckCircle className='mr-2 h-4 w-4' />
                )}
                签到
              </Button>
            )}
            <Button
              size='sm'
              variant={canEnter ? 'default' : 'outline'}
              disabled={!canEnter}
              onClick={() => onEnterRoom?.(reservation.room_id)}
            >
              <DoorOpen className='mr-2 h-4 w-4' />
              进入候场
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default StudentReservationCard;
