export const WAITING_CHECKLIST_ITEM_COUNT = 4;

export interface WaitingChecklistEntry {
  items: boolean[];
  ready: boolean;
  completed_count: number;
  updated_at?: string | null;
  role?: string | null;
  name?: string | null;
  online?: boolean;
}

export interface WaitingStatus {
  required_roles: string[];
  required_count: number;
  online_count: number;
  ready_count: number;
  online_roles: string[];
  ready_roles: string[];
  online_user_ids: string[];
  ready_user_ids: string[];
  missing_roles: string[];
  all_online: boolean;
  all_ready: boolean;
  ready_to_start: boolean;
}

export interface WaitingRoomState {
  room_id?: string;
  debate_id?: string;
  current_phase?: string;
  participants?: Array<Record<string, unknown>>;
  waiting_checklists?: Record<string, WaitingChecklistEntry>;
  waiting_status?: WaitingStatus;
}

const normalizeChecklistItems = (items: unknown): boolean[] => {
  const raw = Array.isArray(items) ? items : [];
  const normalized = raw.slice(0, WAITING_CHECKLIST_ITEM_COUNT).map(Boolean);
  while (normalized.length < WAITING_CHECKLIST_ITEM_COUNT) {
    normalized.push(false);
  }
  return normalized;
};

export const parseWaitingRoomState = (
  value: unknown
): WaitingRoomState | null => {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const state = value as Record<string, unknown>;
  const rawChecklists =
    state.waiting_checklists && typeof state.waiting_checklists === 'object'
      ? (state.waiting_checklists as Record<string, Record<string, unknown>>)
      : {};

  const waiting_checklists: Record<string, WaitingChecklistEntry> = {};
  Object.entries(rawChecklists).forEach(([userId, entry]) => {
    const items = normalizeChecklistItems(entry?.items);
    waiting_checklists[userId] = {
      items,
      ready: Boolean(entry?.ready ?? items.every(Boolean)),
      completed_count:
        typeof entry?.completed_count === 'number'
          ? entry.completed_count
          : items.filter(Boolean).length,
      updated_at:
        typeof entry?.updated_at === 'string' ? entry.updated_at : null,
      role: typeof entry?.role === 'string' ? entry.role : null,
      name: typeof entry?.name === 'string' ? entry.name : null,
      online: Boolean(entry?.online),
    };
  });

  return {
    room_id: typeof state.room_id === 'string' ? state.room_id : undefined,
    debate_id: typeof state.debate_id === 'string' ? state.debate_id : undefined,
    current_phase:
      typeof state.current_phase === 'string' ? state.current_phase : undefined,
    participants: Array.isArray(state.participants)
      ? (state.participants as Array<Record<string, unknown>>)
      : [],
    waiting_checklists,
    waiting_status:
      state.waiting_status && typeof state.waiting_status === 'object'
        ? (state.waiting_status as WaitingStatus)
        : undefined,
  };
};

export const getRealtimeParticipantCount = (
  waitingState: WaitingRoomState | null,
  fallback = 0
) => waitingState?.waiting_status?.online_count ?? fallback;

export const getCurrentUserChecklist = (
  waitingState: WaitingRoomState | null,
  userId?: string | null
) =>
  (userId && waitingState?.waiting_checklists?.[userId]?.items) ||
  normalizeChecklistItems([]);

export const getWaitingReadyToStart = (
  waitingState: WaitingRoomState | null
) => Boolean(waitingState?.waiting_status?.ready_to_start);

export const hasDebateStarted = (waitingState: WaitingRoomState | null) =>
  Boolean(waitingState?.current_phase && waitingState.current_phase !== 'waiting');
