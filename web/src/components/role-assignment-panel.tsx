import React, { useEffect, useMemo, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toAssignmentViewModel } from '@/lib/frontend-adapters';
import type { DebateConfigMeta, DebateRole, RoleAssignmentInput } from '@/lib/frontend-contracts';
import TeacherService, { type Student } from '@/services/teacher.service';
import { Loader2, Shuffle } from 'lucide-react';

interface RoleAssignmentPanelProps {
  classId: string;
  students: Student[];
  selectedStudentIds: string[];
  configMeta: DebateConfigMeta;
  onChange: (assignments: RoleAssignmentInput[], assignmentRunId?: string) => void;
}

const roleLabels: Record<DebateRole, string> = {
  debater_1: '正方一辩',
  debater_2: '正方二辩',
  debater_3: '反方一辩',
  debater_4: '反方二辩',
};

const RoleAssignmentPanel: React.FC<RoleAssignmentPanelProps> = ({
  classId,
  students,
  selectedStudentIds,
  configMeta,
  onChange,
}) => {
  const [assignments, setAssignments] = useState<RoleAssignmentInput[]>([]);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [scores, setScores] = useState<Record<string, number | null | undefined>>({});
  const [runId, setRunId] = useState<string | undefined>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedKey = useMemo(() => selectedStudentIds.join(','), [selectedStudentIds]);

  useEffect(() => {
    setAssignments([]);
    setReasons({});
    setScores({});
    setRunId(undefined);
    onChange([]);
  }, [selectedKey]);

  const preview = async () => {
    if (!classId || !selectedStudentIds.length) return;
    setLoading(true);
    setError(null);
    try {
      const result = await TeacherService.previewRoleAssignment({
        class_id: classId,
        student_ids: selectedStudentIds,
        config_meta: configMeta,
      });
      const viewModel = toAssignmentViewModel(result);
      const next = viewModel.items.map((item) => ({ user_id: item.userId, role: item.role }));
      setAssignments(next);
      setReasons(Object.fromEntries(viewModel.items.map((item) => [item.userId, item.reason])));
      setScores(Object.fromEntries(viewModel.items.map((item) => [item.userId, item.score])));
      setRunId(viewModel.runId || undefined);
      onChange(next, viewModel.runId || undefined);
    } catch (err: any) {
      setError(err?.message || '辩位推荐失败');
    } finally {
      setLoading(false);
    }
  };

  const changeRole = (userId: string, role: DebateRole) => {
    const currentRole = assignments.find((item) => item.user_id === userId)?.role;
    const next = assignments.map((item) => {
      if (item.user_id === userId) {
        return { ...item, role, override_reason: '教师手动调整' };
      }
      if (currentRole && item.role === role) {
        return { ...item, role: currentRole, override_reason: '教师手动调整' };
      }
      return item;
    });
    setAssignments(next);
    onChange(next, runId);
  };

  return (
    <div className='space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4'>
      <div className='flex flex-wrap items-center justify-between gap-3'>
        <div>
          <div className='font-medium text-slate-900'>AI 辩位推荐与教师确认</div>
          <p className='text-sm text-slate-500'>推荐会显示原因，教师可在提交前调整。</p>
        </div>
        <Button type='button' variant='outline' disabled={loading || !selectedStudentIds.length} onClick={() => void preview()}>
          {loading ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <Shuffle className='mr-2 h-4 w-4' />}生成推荐
        </Button>
      </div>
      {error && <Alert variant='destructive'><AlertDescription>{error}</AlertDescription></Alert>}
      {assignments.map((assignment) => {
        const student = students.find((item) => item.id === assignment.user_id);
        return (
          <div key={assignment.user_id} className='grid gap-3 rounded-md border bg-white p-3 md:grid-cols-[1fr_180px]'>
            <div>
              <div className='flex items-center gap-2 font-medium'>{student?.name || assignment.user_id}<Badge variant='secondary'>{scores[assignment.user_id] ?? '—'}</Badge></div>
              <p className='mt-1 text-xs text-slate-500'>{reasons[assignment.user_id]}</p>
            </div>
            <Select value={assignment.role} onValueChange={(value: DebateRole) => changeRole(assignment.user_id, value)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{Object.entries(roleLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        );
      })}
    </div>
  );
};

export default RoleAssignmentPanel;
