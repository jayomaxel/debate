import React, { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import StudentService, {
  type CreateLobbyRoomParams,
  type LobbyRoom,
} from '@/services/student.service';
import { Loader2, Plus } from 'lucide-react';

interface CreateRoomDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (room: LobbyRoom) => void;
}

const initialForm: CreateLobbyRoomParams = {
  room_name: '',
  topic: '',
  description: '',
  capacity: 4,
  visibility: 'public',
  password: '',
  allow_spectators: false,
};

const getCreateRoomErrorMessage = (err: any) => {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (err?.response?.status === 404) {
    return '创建房间接口未找到，请确认前端正在请求本机 /api，并且后端已重启到包含匹配大厅接口的版本。';
  }

  return err?.message || '创建房间失败';
};

const CreateRoomDialog: React.FC<CreateRoomDialogProps> = ({
  open,
  onOpenChange,
  onCreated,
}) => {
  const { toast } = useToast();
  const [form, setForm] = useState<CreateLobbyRoomParams>(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setForm(initialForm);
      setError(null);
      setSubmitting(false);
    }
  }, [open]);

  const handleSubmit = async () => {
    const topic = form.topic.trim();
    if (!topic) {
      setError('请填写辩题');
      return;
    }
    if (form.visibility === 'private' && !String(form.password || '').trim()) {
      setError('私密房间必须填写密码');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      const created = await StudentService.createLobbyRoom({
        ...form,
        topic,
        room_name: form.room_name?.trim() || undefined,
        description: form.description?.trim() || undefined,
        password: form.visibility === 'private' ? form.password?.trim() : undefined,
      });
      toast({
        variant: 'success',
        title: '房间已创建',
        description: '你已自动成为一号辩手兼主持人。',
      });
      onCreated(created);
      onOpenChange(false);
    } catch (err: any) {
      setError(getCreateRoomErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='max-w-2xl'>
        <DialogHeader>
          <DialogTitle>创建自发组队房间</DialogTitle>
          <DialogDescription>
            创建后你会自动进入一号辩手席位，并拥有开赛与流程推进权限。
          </DialogDescription>
        </DialogHeader>

        <div className='grid gap-4 py-2'>
          <div className='grid gap-2'>
            <Label htmlFor='room-name'>房间名称</Label>
            <Input
              id='room-name'
              value={form.room_name}
              onChange={(event) => setForm((prev) => ({ ...prev, room_name: event.target.value }))}
              placeholder='例如：AI情感羁绊练习场'
            />
          </div>
          <div className='grid gap-2'>
            <Label htmlFor='room-topic'>辩题</Label>
            <Textarea
              id='room-topic'
              value={form.topic}
              onChange={(event) => setForm((prev) => ({ ...prev, topic: event.target.value }))}
              placeholder='输入本场自发组队辩题'
              className='min-h-[88px]'
            />
          </div>
          <div className='grid gap-2'>
            <Label htmlFor='room-description'>补充说明</Label>
            <Textarea
              id='room-description'
              value={form.description}
              onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
              placeholder='可填写材料范围、讨论重点等'
            />
          </div>

          <div className='grid gap-4 md:grid-cols-3'>
            <div className='grid gap-2'>
              <Label>房间类型</Label>
              <Select
                value={form.visibility}
                onValueChange={(value: 'public' | 'private') =>
                  setForm((prev) => ({ ...prev, visibility: value }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value='public'>公开</SelectItem>
                  <SelectItem value='private'>私密</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className='grid gap-2'>
              <Label>人数上限</Label>
              <Select
                value={String(form.capacity)}
                onValueChange={(value) => setForm((prev) => ({ ...prev, capacity: Number(value) }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value='2'>2 人</SelectItem>
                  <SelectItem value='3'>3 人</SelectItem>
                  <SelectItem value='4'>4 人</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className='flex items-center justify-between rounded-md border border-slate-200 px-3 py-2'>
              <div>
                <Label htmlFor='allow-spectators'>允许旁观</Label>
                <p className='text-xs text-slate-500'>观摩不占辩手席位</p>
              </div>
              <Switch
                id='allow-spectators'
                checked={form.allow_spectators}
                onCheckedChange={(checked) => setForm((prev) => ({ ...prev, allow_spectators: checked }))}
              />
            </div>
          </div>

          {form.visibility === 'private' && (
            <div className='grid gap-2'>
              <Label htmlFor='room-password'>房间密码</Label>
              <Input
                id='room-password'
                type='password'
                value={form.password}
                onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
                placeholder='加入私密房间需要输入密码'
              />
            </div>
          )}

          {error && <div className='rounded-md bg-red-50 px-3 py-2 text-sm text-red-700'>{error}</div>}
        </div>

        <DialogFooter>
          <Button variant='outline' disabled={submitting} onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button disabled={submitting} onClick={handleSubmit}>
            {submitting ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <Plus className='mr-2 h-4 w-4' />}
            创建房间
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default CreateRoomDialog;
