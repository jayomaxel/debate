import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { toTeachingDesignViewModel } from '@/lib/frontend-adapters';
import type { TeachingDesignPayload, TeachingDesignViewModel } from '@/lib/frontend-contracts';
import { mapUploadError } from '@/lib/upload-error-mapper';
import TeacherService, { type Class } from '@/services/teacher.service';
import { AlertCircle, FileUp, Loader2, Save } from 'lucide-react';

interface TeachingDesignManagerProps {
  classes: Class[];
  initialClassId?: string;
}

const emptyPayload = (): TeachingDesignPayload => ({
  learning_objectives: [],
  knowledge_points: [],
  key_difficulties: [],
  capability_targets: [],
  debate_focuses: [],
  forbidden_boundaries: [],
});

const listFields: Array<{ key: keyof TeachingDesignPayload; label: string }> = [
  { key: 'learning_objectives', label: '课程目标' },
  { key: 'knowledge_points', label: '知识点' },
  { key: 'key_difficulties', label: '重点难点' },
  { key: 'capability_targets', label: '能力培养目标' },
  { key: 'debate_focuses', label: '可辩焦点' },
  { key: 'forbidden_boundaries', label: '内容边界' },
];

const TeachingDesignManager: React.FC<TeachingDesignManagerProps> = ({
  classes,
  initialClassId = '',
}) => {
  const [classId, setClassId] = useState(initialClassId || classes[0]?.id || '');
  const [design, setDesign] = useState<TeachingDesignViewModel | null>(null);
  const [payload, setPayload] = useState<TeachingDesignPayload>(emptyPayload);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!classId) return;
    setLoading(true);
    setError(null);
    try {
      const current = await TeacherService.getCurrentTeachingDesign(classId);
      const viewModel = current ? toTeachingDesignViewModel(current) : null;
      setDesign(viewModel);
      setPayload(viewModel?.payload || emptyPayload());
    } catch (err: any) {
      setError(err?.message || '教学设计加载失败');
    } finally {
      setLoading(false);
    }
  }, [classId]);

  useEffect(() => {
    void load();
  }, [load]);

  const reviewFields = useMemo(
    () => new Set([...(design?.missingFields || []), ...(design?.lowConfidenceFields || [])]),
    [design]
  );

  const updateList = (key: keyof TeachingDesignPayload, value: string) => {
    setPayload((previous) => ({
      ...previous,
      [key]: value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean),
    }));
  };

  const upload = async (file?: File) => {
    if (!file || !classId) return;
    setLoading(true);
    setError(null);
    setMessage('正在提取教学设计...');
    try {
      const result = await TeacherService.uploadTeachingDesign(classId, file);
      const viewModel = toTeachingDesignViewModel(result);
      setDesign(viewModel);
      setPayload(viewModel.payload);
      setMessage('教学设计已上传，请检查低置信度和缺失字段。');
    } catch (err) {
      setError(mapUploadError(err));
      setMessage(null);
    } finally {
      setLoading(false);
    }
  };

  const save = async () => {
    if (!classId) return;
    setSaving(true);
    setError(null);
    try {
      const result = await TeacherService.saveTeachingDesign(classId, payload, design?.name);
      const viewModel = toTeachingDesignViewModel(result);
      setDesign(viewModel);
      setPayload(viewModel.payload);
      setMessage('校正结果已保存为当前版本。');
    } catch (err: any) {
      setError(err?.message || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className='border-slate-200 bg-white shadow-sm'>
      <CardHeader>
        <CardTitle>教学设计中心</CardTitle>
      </CardHeader>
      <CardContent className='space-y-6'>
        {error && <Alert variant='destructive'><AlertCircle className='h-4 w-4' /><AlertDescription>{error}</AlertDescription></Alert>}
        {message && <Alert><AlertDescription>{message}</AlertDescription></Alert>}
        <div className='grid gap-4 md:grid-cols-[1fr_auto]'>
          <div className='space-y-2'>
            <Label>班级</Label>
            <Select value={classId} onValueChange={setClassId}>
              <SelectTrigger><SelectValue placeholder='请选择班级' /></SelectTrigger>
              <SelectContent>{classes.map((item) => <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className='flex items-end'>
            <Label className='cursor-pointer'>
              <Input className='hidden' type='file' accept='.pdf,.docx' onChange={(event) => void upload(event.target.files?.[0])} />
              <span className='inline-flex h-10 items-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700'>
                {loading ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <FileUp className='mr-2 h-4 w-4' />}上传或替换
              </span>
            </Label>
          </div>
        </div>
        {design ? (
          <>
            <div className='flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 p-3 text-sm'>
              <span className='font-medium'>{design.name}</span>
              <span className='text-slate-500'>{design.fileName}</span>
              <Badge variant={design.status === 'ready' ? 'default' : 'secondary'}>{design.status}</Badge>
            </div>
            <div className='grid gap-4 md:grid-cols-2'>
              <div className='space-y-2'><Label>课程名称</Label><Input value={payload.course_title || ''} onChange={(event) => setPayload({ ...payload, course_title: event.target.value })} /></div>
              <div className='space-y-2'><Label>章节主题</Label><Input value={payload.chapter_theme || ''} onChange={(event) => setPayload({ ...payload, chapter_theme: event.target.value })} /></div>
              {listFields.map((field) => (
                <div key={field.key} className='space-y-2'>
                  <Label className='flex items-center gap-2'>{field.label}{reviewFields.has(field.key) && <Badge variant='outline'>需要确认</Badge>}</Label>
                  <Textarea value={((payload[field.key] as string[]) || []).join('\n')} onChange={(event) => updateList(field.key, event.target.value)} placeholder='每行一项' />
                </div>
              ))}
            </div>
            <div className='flex justify-end'><Button onClick={() => void save()} disabled={saving}>{saving ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <Save className='mr-2 h-4 w-4' />}保存校正</Button></div>
          </>
        ) : (
          !loading && <div className='rounded-lg border border-dashed p-8 text-center text-slate-500'>当前班级还没有教学设计，可上传 PDF 或 DOCX。</div>
        )}
      </CardContent>
    </Card>
  );
};

export default TeachingDesignManager;
