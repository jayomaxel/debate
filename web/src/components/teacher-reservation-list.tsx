import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import TeacherReservationCard from '@/components/teacher-reservation-card';
import {
  checkinStatusLabelMap,
  formatDateTime,
  invitationStatusLabelMap,
  reservationStatusLabelMap,
  roleLabel,
  statusBadgeClass,
} from '@/lib/reservation-display';
import TeacherService, {
  type Student,
  type TeacherReservation,
} from '@/services/teacher.service';
import { CalendarClock, Loader2, RefreshCw } from 'lucide-react';

interface TeacherReservationListProps {
  selectedClassId?: string;
  students: Student[];
}

const TeacherReservationList: React.FC<TeacherReservationListProps> = ({
  selectedClassId,
  students,
}) => {
  const [reservations, setReservations] = useState<TeacherReservation[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [detail, setDetail] = useState<TeacherReservation | null>(null);

  const loadReservations = useCallback(async (mode: 'initial' | 'manual' = 'manual') => {
    try {
      if (mode === 'initial') setLoading(true);
      if (mode === 'manual') setRefreshing(true);
      const data = await TeacherService.getReservationDebates({
        class_id: selectedClassId || undefined,
        page: 1,
        page_size: 30,
      });
      setReservations(data.items);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedClassId]);

  useEffect(() => {
    void loadReservations('initial');
  }, [loadReservations]);

  const studentById = useMemo(
    () => new Map(students.map((student) => [student.id, student])),
    [students]
  );

  const handleChanged = (reservation: TeacherReservation) => {
    setReservations((prev) =>
      prev.map((item) => (item.reservation_id === reservation.reservation_id ? reservation : item))
    );
    setDetail((prev) => (prev?.reservation_id === reservation.reservation_id ? reservation : prev));
  };

  return (
    <>
      <Card className='border-slate-200 bg-white shadow-sm'>
        <CardHeader>
          <CardTitle className='flex flex-col gap-3 md:flex-row md:items-center md:justify-between'>
            <div className='flex items-center gap-2'>
              <CalendarClock className='h-5 w-5 text-blue-600' />
              预约列表
              <Badge variant='outline'>{reservations.length} 场</Badge>
            </div>
            <Button variant='outline' size='sm' disabled={loading || refreshing} onClick={() => loadReservations('manual')}>
              {loading || refreshing ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <RefreshCw className='mr-2 h-4 w-4' />}
              刷新
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className='flex items-center justify-center gap-2 py-12 text-slate-500'>
              <Loader2 className='h-5 w-5 animate-spin' />
              正在加载预约...
            </div>
          ) : reservations.length === 0 ? (
            <div className='rounded-lg border border-dashed border-slate-300 bg-slate-50 py-12 text-center text-slate-500'>
              暂无预约辩论赛
            </div>
          ) : (
            <div className='space-y-3'>
              {reservations.map((reservation) => (
                <TeacherReservationCard
                  key={reservation.reservation_id}
                  reservation={reservation}
                  students={students}
                  onChanged={handleChanged}
                  onViewDetail={setDetail}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={!!detail} onOpenChange={(open) => !open && setDetail(null)}>
        <DialogContent className='max-w-3xl'>
          <DialogHeader>
            <DialogTitle>预约详情</DialogTitle>
          </DialogHeader>
          {detail && (
            <div className='space-y-5'>
              <div className='rounded-lg border border-slate-200 p-4'>
                <div className='mb-2 flex flex-wrap items-center gap-2'>
                  <Badge variant='outline' className={statusBadgeClass(detail.status)}>
                    {reservationStatusLabelMap[detail.status]}
                  </Badge>
                  <Badge variant='outline'>{detail.class_name}</Badge>
                </div>
                <h3 className='font-semibold text-slate-900'>{detail.topic}</h3>
                <div className='mt-3 grid gap-2 text-sm text-slate-600 md:grid-cols-2'>
                  <span>开赛：{formatDateTime(detail.scheduled_start_time)}</span>
                  <span>签到：{formatDateTime(detail.checkin_open_time)} - {formatDateTime(detail.checkin_close_time)}</span>
                  <span>预计时长：{detail.duration} 分钟</span>
                  <span>房间：{detail.visibility === 'private' ? '私密' : '公开'}</span>
                </div>
                {detail.description && <p className='mt-3 text-sm text-slate-600'>{detail.description}</p>}
              </div>

              <div className='grid gap-2 md:grid-cols-2'>
                {Object.values(detail.invitations || {}).map((invitation) => {
                  const student = studentById.get(invitation.student_id);
                  return (
                    <div key={invitation.invitation_id} className='rounded-lg border border-slate-200 p-4'>
                      <div className='flex items-center justify-between gap-2'>
                        <div>
                          <div className='font-medium text-slate-900'>{student?.name || invitation.student_id.slice(0, 8)}</div>
                          <div className='text-xs text-slate-500'>{student?.email || student?.account || invitation.student_id}</div>
                        </div>
                        {invitation.is_designated_moderator && <Badge className='bg-amber-500 text-white'>主持人</Badge>}
                      </div>
                      <div className='mt-3 flex flex-wrap gap-2'>
                        <Badge variant='outline' className='bg-blue-50 text-blue-700 border-blue-200'>
                          {roleLabel(invitation.assigned_role || invitation.role)}
                        </Badge>
                        <Badge variant='outline'>{invitationStatusLabelMap[invitation.response_status]}</Badge>
                        <Badge variant='outline'>{checkinStatusLabelMap[invitation.attendance_status]}</Badge>
                      </div>
                      <div className='mt-2 text-xs text-slate-500'>
                        响应：{formatDateTime(invitation.responded_at)} · 签到：{formatDateTime(invitation.checked_in_at)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
};

export default TeacherReservationList;
