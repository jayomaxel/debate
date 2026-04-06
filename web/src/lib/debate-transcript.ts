export const TRANSCRIPT_PENDING_TEXT = '语音已收到，识别中...';

const AUDIO_EXTENSIONS = [
  '.mp3',
  '.wav',
  '.webm',
  '.ogg',
  '.m4a',
  '.aac',
  '.flac',
  '.opus',
];

const MATCH_WINDOW_MS = 120_000;

export interface TranscriptEntry {
  id: string;
  speaker: string;
  position: string;
  message: string;
  timestamp: Date;
  isAI?: boolean;
  audioUrl?: string;
  audioFormat?: string;
  audioSourceUrl?: string;
  speakerKey?: string;
  speakerRole?: string;
  speakerUserId?: string;
  phase?: string;
  segmentId?: string;
  segmentTitle?: string;
  sourceIds?: string[];
  isPendingText?: boolean;
}

export interface TranscriptEvent {
  id?: string | number | null;
  speech_id?: string | number | null;
  message_id?: string | number | null;
  client_message_id?: string | number | null;
  user_id?: string | number | null;
  speaker_id?: string | number | null;
  role?: string | null;
  speaker_role?: string | null;
  speaker_type?: string | null;
  name?: string | null;
  stance?: string | null;
  content?: string | null;
  text?: string | null;
  audio_url?: string | null;
  file_url?: string | null;
  url?: string | null;
  audio_format?: string | null;
  timestamp?: string | number | Date | null;
  phase?: string | null;
  segment_id?: string | number | null;
  segment_title?: string | null;
}

interface NormalizeTranscriptOptions {
  resolveMediaUrl?: (url?: string | null) => string | undefined;
  resolvePosition?: (role: string) => string;
  resolveSpeakerName?: (event: TranscriptEvent) => string;
  placeholderText?: string;
}

interface MergeTranscriptOptions extends NormalizeTranscriptOptions {
  matchingWindowMs?: number;
}

const normalizeString = (value: unknown): string => {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value).trim();
};

export const buildTranscriptSpeechEntryId = (
  sourceId: string | number | null | undefined
): string => {
  const normalizedId = normalizeString(sourceId);
  return normalizedId ? `speech-${normalizedId}` : '';
};

const parseTimestamp = (value: unknown): Date => {
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return value;
  }

  if (typeof value === 'number' && Number.isFinite(value)) {
    const asMs = value > 1_000_000_000_000 ? value : value * 1000;
    const parsed = new Date(asMs);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed;
    }
  }

  if (typeof value === 'string' && value.trim()) {
    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed;
    }
  }

  return new Date();
};

const stableHash = (value: string): string => {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = ((hash << 5) - hash + value.charCodeAt(i)) | 0;
  }
  return Math.abs(hash).toString(36);
};

const collectSourceIds = (event: TranscriptEvent): string[] => {
  const ids = [
    event.id,
    event.speech_id,
    event.message_id,
    event.client_message_id,
  ]
    .map((item) => normalizeString(item))
    .filter((item) => item.length > 0);

  const audioSource = getAudioSourceUrl(event);
  if (audioSource) {
    ids.push(audioSource);
  }

  return Array.from(new Set(ids));
};

export const getAudioSourceUrl = (event: TranscriptEvent): string => {
  return normalizeString(event.audio_url || event.file_url || event.url);
};

const buildSpeakerKey = (event: TranscriptEvent): string => {
  const userId = normalizeString(event.user_id || event.speaker_id);
  const role = normalizeString(event.role || event.speaker_role);
  const speakerType = normalizeString(event.speaker_type);
  const name = normalizeString(event.name);
  return [userId, role, speakerType, name].filter(Boolean).join('|');
};

const isPendingMessage = (entry: TranscriptEntry): boolean => {
  return entry.isPendingText || !normalizeString(entry.message) || entry.message === TRANSCRIPT_PENDING_TEXT;
};

const sameTimestampWindow = (left: Date, right: Date, windowMs: number): boolean => {
  return Math.abs(left.getTime() - right.getTime()) <= windowMs;
};

const sameSourceId = (entry: TranscriptEntry, sourceIds: string[]): boolean => {
  if (!entry.sourceIds || entry.sourceIds.length === 0) {
    return false;
  }

  return sourceIds.some((id) => entry.sourceIds!.includes(id));
};

const resolveEntryId = (event: TranscriptEvent): string => {
  const directEntryId = buildTranscriptSpeechEntryId(
    event.speech_id || event.message_id || event.client_message_id || event.id
  );
  if (directEntryId) {
    return directEntryId;
  }

  const audioSource = getAudioSourceUrl(event);
  if (audioSource) {
    return `audio-${stableHash(audioSource)}`;
  }

  const speakerKey = buildSpeakerKey(event);
  const phaseKey = normalizeString(event.phase || event.segment_id || event.segment_title);
  const contentKey = normalizeString(event.content || event.text);
  const timeKey = String(Math.floor(parseTimestamp(event.timestamp).getTime() / MATCH_WINDOW_MS));
  return `speech-${stableHash([speakerKey, phaseKey, contentKey, timeKey].join('|'))}`;
};

const resolveSpeakerLabel = (
  event: TranscriptEvent,
  resolveSpeakerName?: (event: TranscriptEvent) => string
): string => {
  const candidate = normalizeString(resolveSpeakerName?.(event) || event.name);
  if (candidate) {
    return candidate;
  }

  if (normalizeString(event.speaker_type).toLowerCase() === 'ai') {
    return 'AI';
  }

  return '学生';
};

const resolvePositionLabel = (
  event: TranscriptEvent,
  resolvePosition?: (role: string) => string
): string => {
  const role = normalizeString(event.role || event.speaker_role);
  if (!role) {
    return '未知';
  }

  return resolvePosition ? resolvePosition(role) : role;
};

export const normalizeTranscriptEntry = (
  event: TranscriptEvent,
  options: NormalizeTranscriptOptions = {}
): TranscriptEntry => {
  // 统一把服务端各种消息格式归一成前端可直接渲染的转录结构。
  const audioSourceUrl = getAudioSourceUrl(event);
  const content = normalizeString(event.content || event.text);
  const placeholderText = options.placeholderText || TRANSCRIPT_PENDING_TEXT;
  const message = content || (audioSourceUrl ? placeholderText : '');
  const speakerKey = buildSpeakerKey(event);
  const timestamp = parseTimestamp(event.timestamp);
  const sourceIds = collectSourceIds(event);
  const audioFormat = normalizeString(event.audio_format);

  return {
    id: resolveEntryId(event),
    speaker: resolveSpeakerLabel(event, options.resolveSpeakerName),
    position: resolvePositionLabel(event, options.resolvePosition),
    message,
    timestamp,
    isAI: normalizeString(event.speaker_type).toLowerCase() === 'ai'
      || normalizeString(event.role || event.speaker_role).startsWith('ai_'),
    audioUrl: audioSourceUrl ? (options.resolveMediaUrl?.(audioSourceUrl) || audioSourceUrl) : undefined,
    audioFormat: audioFormat || undefined,
    audioSourceUrl: audioSourceUrl || undefined,
    speakerKey,
    speakerRole: normalizeString(event.role || event.speaker_role) || undefined,
    speakerUserId: normalizeString(event.user_id || event.speaker_id) || undefined,
    phase: normalizeString(event.phase) || undefined,
    segmentId: normalizeString(event.segment_id) || undefined,
    segmentTitle: normalizeString(event.segment_title) || undefined,
    sourceIds,
    isPendingText: !content && !!audioSourceUrl,
  };
};

const mergeTranscriptEntry = (
  existing: TranscriptEntry,
  incoming: TranscriptEntry,
  placeholderText: string
): TranscriptEntry => {
  // 同一条发言可能先到文本、后到音频，也可能先到音频、后到文本，这里统一合并。
  const mergedSourceIds = Array.from(
    new Set([...(existing.sourceIds || []), ...(incoming.sourceIds || [])])
  );

  const nextMessage = normalizeString(incoming.message);
  const shouldReplaceMessage =
    !!nextMessage && nextMessage !== placeholderText;

  return {
    ...existing,
    ...incoming,
    id: existing.id,
    speaker: incoming.speaker || existing.speaker,
    position: incoming.position || existing.position,
    message: shouldReplaceMessage ? nextMessage : existing.message,
    timestamp: existing.timestamp || incoming.timestamp,
    isAI: typeof incoming.isAI === 'boolean' ? incoming.isAI : existing.isAI,
    audioUrl: incoming.audioUrl || existing.audioUrl,
    audioFormat: incoming.audioFormat || existing.audioFormat,
    audioSourceUrl: incoming.audioSourceUrl || existing.audioSourceUrl,
    speakerKey: incoming.speakerKey || existing.speakerKey,
    speakerRole: incoming.speakerRole || existing.speakerRole,
    speakerUserId: incoming.speakerUserId || existing.speakerUserId,
    phase: incoming.phase || existing.phase,
    segmentId: incoming.segmentId || existing.segmentId,
    segmentTitle: incoming.segmentTitle || existing.segmentTitle,
    sourceIds: mergedSourceIds,
    isPendingText: shouldReplaceMessage ? false : (incoming.isPendingText ?? existing.isPendingText),
  };
};

const findTranscriptEntryIndex = (
  entries: TranscriptEntry[],
  incoming: TranscriptEntry,
  matchingWindowMs: number
): number => {
  // 先按最稳定的speech_id / message_id / audio_url匹配，再退化到“同一说话人 + 时间窗口”匹配。
  const sourceIds = incoming.sourceIds || [];

  for (let i = entries.length - 1; i >= 0; i -= 1) {
    if (sameSourceId(entries[i], sourceIds)) {
      return i;
    }
  }

  if (incoming.audioSourceUrl) {
    for (let i = entries.length - 1; i >= 0; i -= 1) {
      const current = entries[i];
      if (current.audioSourceUrl && current.audioSourceUrl === incoming.audioSourceUrl) {
        return i;
      }
    }
  }

  for (let i = entries.length - 1; i >= 0; i -= 1) {
    const current = entries[i];
    if (current.speakerKey !== incoming.speakerKey) {
      continue;
    }
    if (current.phase && incoming.phase && current.phase !== incoming.phase) {
      continue;
    }
    if (!sameTimestampWindow(current.timestamp, incoming.timestamp, matchingWindowMs)) {
      continue;
    }
    if (current.isPendingText || incoming.isPendingText || incoming.audioSourceUrl || current.audioSourceUrl) {
      return i;
    }
  }

  return -1;
};

export const upsertTranscriptEntry = (
  entries: TranscriptEntry[],
  incoming: TranscriptEntry,
  options: MergeTranscriptOptions = {}
): TranscriptEntry[] => {
  // 对外只暴露“新增或更新一条发言”的统一入口，组件层不需要关心具体匹配细节。
  const placeholderText = options.placeholderText || TRANSCRIPT_PENDING_TEXT;
  const matchingWindowMs = options.matchingWindowMs || MATCH_WINDOW_MS;
  const index = findTranscriptEntryIndex(entries, incoming, matchingWindowMs);

  if (index >= 0) {
    const nextEntries = entries.slice();
    nextEntries[index] = mergeTranscriptEntry(nextEntries[index], incoming, placeholderText);
    return nextEntries;
  }

  return [...entries, incoming];
};

export const isTranscriptAudioEntry = (entry: TranscriptEntry): boolean => {
  if (entry.audioSourceUrl || entry.audioUrl || entry.audioFormat) {
    return true;
  }

  if (!entry.message) {
    return false;
  }

  const normalized = entry.audioUrl ? entry.audioUrl.split('?')[0].toLowerCase() : '';
  return AUDIO_EXTENSIONS.some((extension) => normalized.endsWith(extension));
};

export const getTranscriptAudioQueueKey = (entry: TranscriptEntry): string | undefined => {
  const audioKey = normalizeString(entry.audioSourceUrl || entry.audioUrl);
  if (!audioKey) {
    return undefined;
  }

  return `${entry.id}::${audioKey}`;
};
