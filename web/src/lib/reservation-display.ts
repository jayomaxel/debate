import type {
  LobbyRoomMember,
  LobbyRoomStatus,
  ReservationCheckinStatus,
  ReservationInvitationStatus,
  ReservationStatus,
} from '@/services/student.service';

export const roleLabelMap: Record<LobbyRoomMember['role'], string> = {
  debater_1: '一辩',
  debater_2: '二辩',
  debater_3: '三辩',
  debater_4: '四辩',
};

export const stanceLabelMap: Record<'positive' | 'negative', string> = {
  positive: '正方',
  negative: '反方',
};

export const reservationStatusLabelMap: Record<ReservationStatus, string> = {
  draft: '已预约',
  scheduled: '已预约',
  checkin_open: '待签到',
  waiting: '候场中',
  in_progress: '进行中',
  completed: '已结束',
  cancelled: '已取消',
};

export const roomStatusLabelMap: Record<LobbyRoomStatus, string> = {
  waiting: '候场中',
  full: '已满员',
  ongoing: '进行中',
  finished: '已结束',
  cancelled: '已取消',
};

export const invitationStatusLabelMap: Record<ReservationInvitationStatus, string> = {
  pending: '待确认',
  accepted: '已接受',
  rejected: '已拒绝',
  expired: '已过期',
};

export const checkinStatusLabelMap: Record<ReservationCheckinStatus, string> = {
  not_checked_in: '未签到',
  checked_in: '已签到',
  absent: '缺席',
};

export const statusBadgeClass = (status?: ReservationStatus | LobbyRoomStatus | string | null) => {
  switch (status) {
    case 'scheduled':
    case 'waiting':
    case 'draft':
      return 'bg-blue-50 text-blue-700 border-blue-200';
    case 'checkin_open':
      return 'bg-amber-50 text-amber-700 border-amber-200';
    case 'in_progress':
    case 'ongoing':
      return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    case 'completed':
    case 'finished':
      return 'bg-slate-100 text-slate-700 border-slate-200';
    case 'cancelled':
      return 'bg-red-50 text-red-700 border-red-200';
    case 'full':
      return 'bg-purple-50 text-purple-700 border-purple-200';
    default:
      return 'bg-slate-100 text-slate-700 border-slate-200';
  }
};

export const formatDateTime = (value?: string | null) => {
  if (!value) return '未设置';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '时间格式异常';
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const formatDateTimeLocalInput = (value?: string | null) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (num: number) => String(num).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

export const toIsoFromLocalInput = (value: string) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toISOString();
};

export const formatRelativeStart = (value?: string | null) => {
  if (!value) return '未设置开赛时间';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '时间格式异常';
  const diffMs = date.getTime() - Date.now();
  const absMinutes = Math.round(Math.abs(diffMs) / 60000);
  if (diffMs < 0) {
    if (absMinutes < 60) return `已开始 ${absMinutes} 分钟`;
    return `已开始 ${Math.round(absMinutes / 60)} 小时`;
  }
  if (absMinutes < 1) return '即将开始';
  if (absMinutes < 60) return `${absMinutes} 分钟后开始`;
  if (absMinutes < 1440) return `${Math.round(absMinutes / 60)} 小时后开始`;
  return `${Math.round(absMinutes / 1440)} 天后开始`;
};

export const roleLabel = (role?: LobbyRoomMember['role'] | string | null) => {
  if (!role) return '未分配';
  return roleLabelMap[role as LobbyRoomMember['role']] || String(role);
};
