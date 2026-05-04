import React from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  formatDateTime,
  roomStatusLabelMap,
  statusBadgeClass,
} from '@/lib/reservation-display';
import type { LobbyRoom } from '@/services/student.service';
import { Clock, DoorOpen, Lock, Shield, Unlock, Users } from 'lucide-react';

interface LobbyRoomCardProps {
  room: LobbyRoom;
  onJoin: (room: LobbyRoom) => void;
  onView: (room: LobbyRoom) => void;
}

const LobbyRoomCard: React.FC<LobbyRoomCardProps> = ({ room, onJoin, onView }) => {
  const joined = !!room.is_current_user_joined || !!room.current_user_permissions?.is_joined;
  const canJoin = joined || (room.can_join ?? room.status === 'waiting');

  return (
    <Card className='border-slate-200 bg-white shadow-sm transition-colors hover:border-blue-200 hover:bg-blue-50/20'>
      <CardContent className='p-5'>
        <div className='mb-3 flex flex-wrap items-center justify-between gap-2'>
          <div className='flex min-w-0 items-center gap-2'>
            <h3 className='line-clamp-1 font-semibold text-slate-900'>{room.room_name}</h3>
            {room.mode === 'teacher_reserved' && (
              <Badge variant='outline' className='bg-amber-50 text-amber-700 border-amber-200'>
                预约
              </Badge>
            )}
          </div>
          <Badge variant='outline' className={statusBadgeClass(room.status)}>
            {roomStatusLabelMap[room.status] || room.status}
          </Badge>
        </div>

        <p className='line-clamp-2 min-h-[44px] text-sm text-slate-600'>{room.topic}</p>

        <div className='mt-4 grid gap-2 text-sm text-slate-600 md:grid-cols-2'>
          <div className='flex items-center gap-2'>
            <Users className='h-4 w-4 text-blue-600' />
            {room.current_count}/{room.capacity} 人
          </div>
          <div className='flex items-center gap-2'>
            {room.visibility === 'private' ? (
              <Lock className='h-4 w-4 text-amber-600' />
            ) : (
              <Unlock className='h-4 w-4 text-emerald-600' />
            )}
            {room.visibility === 'private' ? '私密房间' : '公开房间'}
            {room.has_password ? ' · 已设密码' : ' · 无密码'}
          </div>
          <div className='flex items-center gap-2'>
            <Shield className='h-4 w-4 text-purple-600' />
            {room.host_name || '主持人待定'}
          </div>
          <div className='flex items-center gap-2'>
            <Clock className='h-4 w-4 text-slate-500' />
            {formatDateTime(room.scheduled_start_time || room.created_at)}
          </div>
        </div>

        <div className='mt-5 flex flex-col gap-2 sm:flex-row sm:justify-end'>
          <Button variant='outline' size='sm' onClick={() => onView(room)}>
            查看详情
          </Button>
          <Button size='sm' disabled={!canJoin} onClick={() => onJoin(room)}>
            <DoorOpen className='mr-2 h-4 w-4' />
            {joined ? '进入候场' : room.visibility === 'private' ? '密码加入' : '加入房间'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default LobbyRoomCard;
