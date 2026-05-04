import React, { useCallback, useEffect, useState } from 'react';
import TeacherReservationForm from '@/components/teacher-reservation-form';
import TeacherReservationList from '@/components/teacher-reservation-list';
import { useToast } from '@/hooks/use-toast';
import TeacherService, {
  type Class,
  type Student,
  type TeacherReservation,
} from '@/services/teacher.service';

interface TeacherReservationManagementProps {
  classes: Class[];
  initialClassId?: string;
}

const TeacherReservationManagement: React.FC<TeacherReservationManagementProps> = ({
  classes,
  initialClassId = '',
}) => {
  const { toast } = useToast();
  const [selectedClassId, setSelectedClassId] = useState(initialClassId || classes[0]?.id || '');
  const [students, setStudents] = useState<Student[]>([]);
  const [studentsLoading, setStudentsLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (!selectedClassId && classes[0]?.id) {
      setSelectedClassId(classes[0].id);
    }
  }, [classes, selectedClassId]);

  const loadStudents = useCallback(async (classId: string) => {
    if (!classId) {
      setStudents([]);
      return;
    }
    try {
      setStudentsLoading(true);
      const data = await TeacherService.getStudents(classId);
      setStudents(data);
    } catch (err: any) {
      toast({
        variant: 'destructive',
        title: '学生列表加载失败',
        description: err?.response?.data?.detail || err?.message || '请稍后重试',
      });
      setStudents([]);
    } finally {
      setStudentsLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void loadStudents(selectedClassId);
  }, [loadStudents, selectedClassId]);

  const handleCreated = (reservation: TeacherReservation) => {
    toast({
      variant: 'success',
      title: '预约创建成功',
      description: `已邀请 ${reservation.invited_count} 名学生。`,
    });
    setRefreshKey((prev) => prev + 1);
  };

  return (
    <div className='space-y-6'>
      <TeacherReservationForm
        classes={classes}
        students={students}
        selectedClassId={selectedClassId}
        studentsLoading={studentsLoading}
        onClassChange={setSelectedClassId}
        onCreated={handleCreated}
      />
      <TeacherReservationList
        key={`${selectedClassId}-${refreshKey}`}
        selectedClassId={selectedClassId}
        students={students}
      />
    </div>
  );
};

export default TeacherReservationManagement;
