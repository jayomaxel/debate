import React, { useMemo, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  checkinStatusLabelMap,
  formatDateTime,
  formatRelativeStart,
  invitationStatusLabelMap,
  reservationStatusLabelMap,
  roleLabel,
  statusBadgeClass,
} from '@/lib/reservation-display';
import TeacherService, {
  type Student,
  type TeacherReservation,
} from '@/services/teacher.service';
import { CalendarClock, Eye, Loader2, Trash2, Users } from 'lucide-react';

interface TeacherReservationCardProps {
  reservation: TeacherReservation;
  students: Student[];
  onChanged: (reservation: TeacherReservation) => void;
  onViewDetail: (reservation: TeacherReservation) => void;
}

const TeacherReservationCard: React.FC<TeacherReservationCardProps> = ({
  reservation,
  students,
  onChanged,
  onViewDetail,
}) => {
  const [cancelling, setCancelling] = useState(false);
  const studentById = useMemo(
    () => new Map(students.map((student) => [student.id, student])),
    [students]
  );
  const invitations = Object.values(reservation.invitations || {});

  const handleCancel = async () => {
    const reason = window.prompt('请输入取消原因（可留空）') || undefined;
    try {
      setCancelling(true);
      const next = await TeacherService.cancelReservationDebate(reservation.reservation_id, reason);
      onChanged(next);
    } finally {
      setCancelling(false);
    }
  };

  return (
    <Card className='border-slate-200 bg-white shadow-sm'>
      <CardContent className='p-5'>
        <div className='flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between'>
          <div className='min-w-0 flex-1'>
            <div className='mb-2 flex flex-wrap items-center gap-2'>
              <Badge variant='outline' className={statusBadgeClass(reservation.status)}>
                {reservationStatusLabelMap[reservation.status] || reservation.status}
              </Badge>
              <Badge variant='outline' className='bg-slate-50 text-slate-700 border-slate-200'>
                {reservation.class_name || '未命名班级'}
              </Badge>
              <Badge variant='outline' className='bg-white text-slate-700 border-slate-200'>
                {reservation.visibility === 'private' ? '私密房间' : '公开房间'}
              </Badge>
            </div>
            <h4 className='line-clamp-2 text-base font-semibold text-slate-900'>{reservation.topic}</h4>
            <div className='mt-3 grid gap-2 text-sm text-slate-600 md:grid-cols-2'>
              <span className='flex items-center gap-2'>
                <CalendarClock className='h-4 w-4 text-blue-600' />
                {formatDateTime(reservation.scheduled_start_time)}
              </span>
              <span>{formatRelativeStart(reservation.scheduled_start_time)}</span>
              <span>预计时长：{reservation.duration} 分钟</span>
              <span>
                邀请 {reservation.invited_count} 人 · 接受 {reservation.accepted_count} 人 · 签到 {reservation.checked_in_count} 人
              </span>
            </div>
          </div>

          <div className='flex shrink-0 gap-2'>
            <Button variant='outline' size='sm' onClick={() => onViewDetail(reservation)}>
              <Eye className='mr-2 h-4 w-4' />
              详情
            </Button>
            <Button
              variant='outline'
              size='sm'
              disabled={cancelling || ['in_progress', 'completed', 'cancelled'].includes(reservation.status)}
              onClick={handleCancel}
              className='text-red-600 hover:bg-red-50 hover:text-red-700'
            >
              {cancelling ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <Trash2 className='mr-2 h-4 w-4' />}
              取消
            </Button>
          </div>
        </div>

        <div className='mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3'>
          <div className='mb-2 flex items-center gap-2 text-sm font-medium text-slate-700'>
            <Users className='h-4 w-4 text-slate-500' />
            邀请与签到
          </div>
          <div className='grid gap-2 md:grid-cols-2 xl:grid-cols-4'>
            {invitations.map((invitation) => {
              const student = studentById.get(invitation.student_id);
              return (
                <div key={invitation.invitation_id} className='rounded-md border border-slate-200 bg-white p-3'>
                  <div className='flex items-center justify-between gap-2'>
                    <span className='font-medium text-slate-900'>
                      {student?.name || invitation.student_id.slice(0, 8)}
                    </span>
                    {invitation.is_designated_moderator && (
                      <Badge className='bg-amber-500 text-white'>主持</Badge>
                    )}
                  </div>
                  <div className='mt-2 flex flex-wrap gap-1'>
                    <Badge variant='outline' className='bg-blue-50 text-blue-700 border-blue-200'>
                      {roleLabel(invitation.assigned_role || invitation.role)}
                    </Badge>
                    <Badge variant='outline'>
                      {invitationStatusLabelMap[invitation.response_status]}
                    </Badge>
                    <Badge variant='outline'>
                      {checkinStatusLabelMap[invitation.attendance_status]}
                    </Badge>
                  </div>
                </div>
              );
            })}
            {invitations.length === 0 && (
              <div className='text-sm text-slate-500'>暂无邀请学生</div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default TeacherReservationCard;
