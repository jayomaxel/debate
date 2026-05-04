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
import StudentService, { type LobbyRoom } from '@/services/student.service';
import { Loader2, Lock } from 'lucide-react';

interface JoinPrivateRoomDialogProps {
  room: LobbyRoom | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onJoined: (room: LobbyRoom) => void;
}

const JoinPrivateRoomDialog: React.FC<JoinPrivateRoomDialogProps> = ({
  room,
  open,
  onOpenChange,
  onJoined,
}) => {
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setPassword('');
      setError(null);
      setSubmitting(false);
    }
  }, [open]);

  const handleSubmit = async () => {
    if (!room) return;
    try {
      setSubmitting(true);
      setError(null);
      const joined = await StudentService.joinLobbyRoom(room.room_id, { password });
      onJoined(joined);
      onOpenChange(false);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || '加入房间失败';
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>加入私密房间</DialogTitle>
          <DialogDescription>
            {room ? `请输入「${room.room_name}」的房间密码。` : '请输入房间密码。'}
          </DialogDescription>
        </DialogHeader>

        <div className='grid gap-3 py-2'>
          <Label htmlFor='join-room-password'>房间密码</Label>
          <Input
            id='join-room-password'
            type='password'
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                void handleSubmit();
              }
            }}
            placeholder='输入密码'
          />
          {error && <div className='rounded-md bg-red-50 px-3 py-2 text-sm text-red-700'>{error}</div>}
        </div>

        <DialogFooter>
          <Button variant='outline' disabled={submitting} onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button disabled={submitting || !password.trim()} onClick={handleSubmit}>
            {submitting ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <Lock className='mr-2 h-4 w-4' />}
            确认加入
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default JoinPrivateRoomDialog;
