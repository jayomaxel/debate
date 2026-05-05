type DebateRoomLike = {
  id?: string | null;
  room_id?: string | null;
  debate_id?: string | null;
};

const normalizeId = (value?: string | null) => String(value || '').trim();

export const getDebateRoomId = (debate?: DebateRoomLike | null) =>
  normalizeId(debate?.room_id) || normalizeId(debate?.debate_id) || normalizeId(debate?.id);
