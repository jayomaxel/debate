export function formatDebateRole(role?: string | null): string {
  switch (role) {
    case 'debater_1':
      return '一辩';
    case 'debater_2':
      return '二辩';
    case 'debater_3':
      return '三辩';
    case 'debater_4':
      return '四辩';
    default:
      return String(role || '').trim() || '待分配';
  }
}

const studentDateTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
});

const studentTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  hour: '2-digit',
  minute: '2-digit',
});

const studentDateFormatter = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

const studentMonthDayFormatter = new Intl.DateTimeFormat('zh-CN', {
  month: '2-digit',
  day: '2-digit',
});

function parseStudentDisplayDate(value?: string | Date | null): Date | null {
  if (!value) {
    return null;
  }

  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatStudentDateTime(value?: string | Date | null): string | null {
  const date = parseStudentDisplayDate(value);
  return date ? studentDateTimeFormatter.format(date) : null;
}

export function formatStudentTime(value?: string | Date | null): string | null {
  const date = parseStudentDisplayDate(value);
  return date ? studentTimeFormatter.format(date) : null;
}

export function formatStudentDate(value?: string | Date | null): string | null {
  const date = parseStudentDisplayDate(value);
  return date ? studentDateFormatter.format(date) : null;
}

export function formatStudentMonthDay(value?: string | Date | null): string | null {
  const date = parseStudentDisplayDate(value);
  return date ? studentMonthDayFormatter.format(date) : null;
}

export function formatDebateStance(stance?: string | null): string {
  switch (stance) {
    case 'positive':
    case 'affirmative':
      return '正方';
    case 'negative':
      return '反方';
    default:
      return String(stance || '').trim() || '未分配';
  }
}

export function formatDebateStatus(status?: string | null): string {
  switch (status) {
    case 'published':
      return '等待开赛';
    case 'in_progress':
      return '进行中';
    case 'completed':
      return '已结束';
    case 'draft':
      return '草稿中';
    default:
      return String(status || '').trim() || '未知状态';
  }
}
