import React, { useEffect, useMemo, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import {
  formatDateTimeLocalInput,
  toIsoFromLocalInput,
} from '@/lib/reservation-display';
import TeacherService, {
  type Class,
  type CreateReservationParams,
  type Student,
  type TeacherReservation,
} from '@/services/teacher.service';
import { AlertCircle, CalendarPlus, Loader2 } from 'lucide-react';

interface TeacherReservationFormProps {
  classes: Class[];
  students: Student[];
  selectedClassId: string;
  studentsLoading: boolean;
  onClassChange: (classId: string) => void;
  onCreated: (reservation: TeacherReservation) => void;
}

const defaultStartTime = () => {
  const date = new Date(Date.now() + 60 * 60 * 1000);
  date.setMinutes(Math.ceil(date.getMinutes() / 5) * 5, 0, 0);
  return formatDateTimeLocalInput(date.toISOString());
};

const TeacherReservationForm: React.FC<TeacherReservationFormProps> = ({
  classes,
  students,
  selectedClassId,
  studentsLoading,
  onClassChange,
  onCreated,
}) => {
  const [topic, setTopic] = useState('人类应不应该与高度拟人化的AI伴侣建立真实的感情羁绊？');
  const [description, setDescription] = useState('');
  const [duration, setDuration] = useState('30');
  const [scheduledStartTime, setScheduledStartTime] = useState(defaultStartTime);
  const [visibility, setVisibility] = useState<'public' | 'private'>('private');
  const [password, setPassword] = useState('');
  const [selectedStudentIds, setSelectedStudentIds] = useState<string[]>([]);
  const [hostUserId, setHostUserId] = useState<string>('teacher');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectableStudents = useMemo(
    () => students.filter((student) => student.class_id === selectedClassId || !selectedClassId),
    [selectedClassId, students]
  );

  useEffect(() => {
    setSelectedStudentIds([]);
    setHostUserId('teacher');
  }, [selectedClassId]);

  const toggleStudent = (studentId: string) => {
    setSelectedStudentIds((prev) => {
      if (prev.includes(studentId)) {
        const next = prev.filter((id) => id !== studentId);
        if (hostUserId === studentId) setHostUserId('teacher');
        return next;
      }
      if (prev.length >= 4) {
        setError('预约辩论最多邀请 4 名学生');
        return prev;
      }
      setError(null);
      return [...prev, studentId];
    });
  };

  const resetForm = () => {
    setTopic('');
    setDescription('');
    setDuration('30');
    setScheduledStartTime(defaultStartTime());
    setVisibility('private');
    setPassword('');
    setSelectedStudentIds([]);
    setHostUserId('teacher');
    setError(null);
  };

  const handleSubmit = async () => {
    if (!selectedClassId) {
      setError('请选择班级');
      return;
    }
    if (!topic.trim()) {
      setError('请填写辩题');
      return;
    }
    if (!scheduledStartTime) {
      setError('请选择开赛时间');
      return;
    }
    if (selectedStudentIds.length === 0) {
      setError('请至少邀请一名学生');
      return;
    }
    if (visibility === 'private' && password && password.length < 4) {
      setError('房间密码至少 4 位，或留空表示仅邀请学生可进入');
      return;
    }

    const scheduledIso = toIsoFromLocalInput(scheduledStartTime);
    if (!scheduledIso) {
      setError('开赛时间格式不正确');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      const params: CreateReservationParams = {
        class_id: selectedClassId,
        topic: topic.trim(),
        description: description.trim() || undefined,
        duration: Number(duration),
        scheduled_start_time: scheduledIso,
        student_ids: selectedStudentIds,
        visibility,
        password: visibility === 'private' && password ? password : undefined,
        host_user_id: hostUserId === 'teacher' ? undefined : hostUserId,
      };
      const created = await TeacherService.createReservationDebate(params);
      onCreated(created);
      resetForm();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '创建预约失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className='border-slate-200 bg-white shadow-sm'>
      <CardHeader>
        <CardTitle className='flex items-center gap-2'>
          <CalendarPlus className='h-5 w-5 text-blue-600' />
          创建预约辩论赛
        </CardTitle>
      </CardHeader>
      <CardContent className='space-y-5'>
        {error && (
          <Alert variant='destructive'>
            <AlertCircle className='h-4 w-4' />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className='grid gap-4 md:grid-cols-2'>
          <div className='space-y-2'>
            <Label>班级</Label>
            <Select value={selectedClassId} onValueChange={onClassChange}>
              <SelectTrigger>
                <SelectValue placeholder='请选择班级' />
              </SelectTrigger>
              <SelectContent>
                {classes.map((cls) => (
                  <SelectItem key={cls.id} value={cls.id}>
                    {cls.name} ({cls.code})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className='space-y-2'>
            <Label>开赛时间</Label>
            <Input
              type='datetime-local'
              value={scheduledStartTime}
              onChange={(event) => setScheduledStartTime(event.target.value)}
            />
          </div>
        </div>

        <div className='space-y-2'>
          <Label>辩题</Label>
          <Textarea
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            className='min-h-[82px]'
            placeholder='输入预约辩题'
          />
        </div>

        <div className='space-y-2'>
          <Label>说明</Label>
          <Textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder='可填写准备材料、注意事项等'
          />
        </div>

        <div className='grid gap-4 md:grid-cols-3'>
          <div className='space-y-2'>
            <Label>预计时长</Label>
            <Select value={duration} onValueChange={setDuration}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='15'>15分钟</SelectItem>
                <SelectItem value='30'>30分钟</SelectItem>
                <SelectItem value='45'>45分钟</SelectItem>
                <SelectItem value='60'>60分钟</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className='space-y-2'>
            <Label>公开性</Label>
            <Select value={visibility} onValueChange={(value: 'public' | 'private') => setVisibility(value)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='private'>私密</SelectItem>
                <SelectItem value='public'>公开</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className='space-y-2'>
            <Label>房间密码</Label>
            <Input
              type='password'
              value={password}
              disabled={visibility === 'public'}
              onChange={(event) => setPassword(event.target.value)}
              placeholder={visibility === 'public' ? '公开房间无需密码' : '可选'}
            />
          </div>
        </div>

        <div className='space-y-3'>
          <div className='flex items-center justify-between'>
            <Label>邀请学生 ({selectedStudentIds.length}/4)</Label>
            <Select value={hostUserId} onValueChange={setHostUserId}>
              <SelectTrigger className='w-[220px]'>
                <SelectValue placeholder='主持人配置' />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='teacher'>教师主持</SelectItem>
                {selectedStudentIds.map((studentId) => {
                  const student = students.find((item) => item.id === studentId);
                  return (
                    <SelectItem key={studentId} value={studentId}>
                      {student?.name || studentId.slice(0, 8)} 主持
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          </div>

          {studentsLoading ? (
            <div className='flex items-center gap-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-slate-500'>
              <Loader2 className='h-4 w-4 animate-spin' />
              正在加载学生...
            </div>
          ) : selectableStudents.length === 0 ? (
            <div className='rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-slate-500'>
              当前班级暂无学生
            </div>
          ) : (
            <div className='grid max-h-72 gap-2 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-3 md:grid-cols-2 xl:grid-cols-3'>
              {selectableStudents.map((student) => (
                <button
                  key={student.id}
                  type='button'
                  onClick={() => toggleStudent(student.id)}
                  className={`flex items-center gap-3 rounded-md border p-3 text-left transition-colors ${
                    selectedStudentIds.includes(student.id)
                      ? 'border-blue-300 bg-blue-50'
                      : 'border-slate-200 bg-white hover:bg-slate-100'
                  }`}
                >
                  <Checkbox
                    checked={selectedStudentIds.includes(student.id)}
                    onClick={(event) => event.stopPropagation()}
                    onCheckedChange={() => toggleStudent(student.id)}
                  />
                  <div className='min-w-0'>
                    <div className='font-medium text-slate-900'>{student.name}</div>
                    <div className='truncate text-xs text-slate-500'>{student.email || student.account}</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className='flex justify-end'>
          <Button disabled={submitting} onClick={handleSubmit}>
            {submitting ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <CalendarPlus className='mr-2 h-4 w-4' />}
            创建预约
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default TeacherReservationForm;
