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
import {
  Clock3,
  DoorOpen,
  Lock,
  Shield,
  Sparkles,
  Unlock,
  Users,
} from 'lucide-react';

interface LobbyRoomCardProps {
  room: LobbyRoom;
  onJoin: (room: LobbyRoom) => void;
  onView: (room: LobbyRoom) => void;
}

const LobbyRoomCard: React.FC<LobbyRoomCardProps> = ({
  room,
  onJoin,
  onView,
}) => {
  const joined =
    !!room.is_current_user_joined || !!room.current_user_permissions?.is_joined;
  const canJoin = joined || (room.can_join ?? room.status === 'waiting');
  const occupancy = Math.min(
    100,
    (room.current_count / Math.max(room.capacity, 1)) * 100
  );

  return (
    <Card className="student-card overflow-hidden border-[#d9e8fb] bg-[#f8fbff]">
      <CardContent className="p-6 md:p-7">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="line-clamp-1 text-lg font-semibold text-slate-900">
                {room.room_name}
              </h3>
              <Badge variant="outline" className={statusBadgeClass(room.status)}>
                {roomStatusLabelMap[room.status] || room.status}
              </Badge>
              {room.mode === 'teacher_reserved' ? (
                <Badge className="student-pill">预约房间</Badge>
              ) : null}
            </div>
            <p className="line-clamp-2 text-sm leading-6 text-slate-600">
              {room.topic}
            </p>
          </div>

          <div className="student-card-soft-blue min-w-[132px] px-4 py-3 text-right">
            <div className="text-xs text-slate-500">当前人数</div>
            <div className="mt-1 text-2xl font-semibold tracking-[-0.03em] text-slate-900">
              {room.current_count}
              <span className="ml-1 text-sm font-medium text-slate-500">
                / {room.capacity}
              </span>
            </div>
          </div>
        </div>

        <div className="mt-5 h-2 overflow-hidden rounded-full bg-[#ece3d8]">
          <div
            className="h-full rounded-full bg-[#1b2436] transition-all"
            style={{ width: `${occupancy}%` }}
          />
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <div className="student-card-muted flex items-center gap-3 px-4 py-3 text-sm text-slate-600">
            <div className="student-icon-bubble h-10 w-10 text-slate-900">
              <Users className="h-4 w-4" />
            </div>
            <div>
              <div className="text-xs text-slate-500">席位状态</div>
              <div className="font-medium text-slate-900">
                {room.current_count}/{room.capacity} 人已入座
              </div>
            </div>
          </div>

          <div className="student-card-muted flex items-center gap-3 px-4 py-3 text-sm text-slate-600">
            <div className="student-icon-bubble h-10 w-10 text-slate-900">
              {room.visibility === 'private' ? (
                <Lock className="h-4 w-4" />
              ) : (
                <Unlock className="h-4 w-4" />
              )}
            </div>
            <div>
              <div className="text-xs text-slate-500">房间类型</div>
              <div className="font-medium text-slate-900">
                {room.visibility === 'private' ? '私密房间' : '公开房间'}
                {room.has_password ? ' · 已设密码' : ' · 无密码'}
              </div>
            </div>
          </div>

          <div className="student-card-muted flex items-center gap-3 px-4 py-3 text-sm text-slate-600">
            <div className="student-icon-bubble h-10 w-10 text-slate-900">
              <Shield className="h-4 w-4" />
            </div>
            <div>
              <div className="text-xs text-slate-500">主持人</div>
              <div className="font-medium text-slate-900">
                {room.host_name || '等待分配'}
              </div>
            </div>
          </div>

          <div className="student-card-muted flex items-center gap-3 px-4 py-3 text-sm text-slate-600">
            <div className="student-icon-bubble h-10 w-10 text-slate-900">
              <Clock3 className="h-4 w-4" />
            </div>
            <div>
              <div className="text-xs text-slate-500">开始时间</div>
              <div className="font-medium text-slate-900">
                {formatDateTime(room.scheduled_start_time || room.created_at)}
              </div>
            </div>
          </div>
        </div>

        {room.description ? (
          <div className="student-card-soft-lavender mt-4 px-4 py-3 text-sm leading-6 text-slate-700">
            <div className="mb-1 flex items-center gap-2 font-medium text-slate-900">
              <Sparkles className="h-4 w-4" />
              房间说明
            </div>
            {room.description}
          </div>
        ) : null}

        <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-end">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onView(room)}
            className="student-light-button h-auto px-4 py-2"
          >
            查看详情
          </Button>
          <Button
            size="sm"
            disabled={!canJoin}
            onClick={() => onJoin(room)}
            className="student-dark-button h-auto px-4 py-2"
          >
            <DoorOpen className="mr-2 h-4 w-4" />
            {joined
              ? '进入候场'
              : room.visibility === 'private'
              ? '密码加入'
              : '加入房间'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default LobbyRoomCard;
