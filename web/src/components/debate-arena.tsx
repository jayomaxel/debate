import React, { useState, useEffect, useRef } from 'react';
import DebateHeader from './debate-header';
import ParticipantVideo, { Participant } from './participant-video';
import AIAvatar, { AIAvatar as AIAvatarType } from './ai-avatar';
import DebateControls from './debate-controls';
import DebateAudioControl from './debate-audio-control';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useWebSocket } from '@/hooks/use-websocket';
import { useAuth } from '@/store/auth.context';
import { useToast } from '@/hooks/use-toast';
import { useNavigationBlocker } from '@/lib/router';
import StudentService from '@/services/student.service';
import {
  TRANSCRIPT_PENDING_TEXT,
  type TranscriptEntry,
  type TranscriptEvent,
  buildTranscriptSpeechEntryId,
  normalizeTranscriptEntry,
  upsertTranscriptEntry,
} from '@/lib/debate-transcript';
import { audioPlaybackDebug, debateDebug } from '@/lib/utils';
import PcmStreamPlayer from '@/lib/pcm-stream-player';
import { getApiOriginBaseUrl } from '@/lib/runtime-url';
import { buildDebateWebSocketUrl, type MessageType } from '@/lib/websocket-client';
import {
  Users,
  Bot,
  AlertCircle,
  Loader2,
  Radio
} from 'lucide-react';

interface DebateArenaProps {
  roomId?: string;
  onBack?: () => void;
  onEndDebate?: () => void;
}

interface RoomParticipant {
  user_id: string;
  name: string;
  role: string;
  stance?: string | null;
  user_type?: string | null;
  can_moderate?: boolean;
  can_speak?: boolean;
}

interface AIDebater {
  id: string;
  role: string;
  name?: string | null;
  stance?: string | null;
}

interface FlowSegment {
  id: string;
  title: string;
  phase: string;
}

type WsPayload = Record<string, unknown>;

const isPayload = (value: unknown): value is WsPayload =>
  !!value && typeof value === 'object' && !Array.isArray(value);

const toOptionalString = (value: unknown): string | null => {
  if (value === null || value === undefined) return null;
  return String(value);
};

const toStringArray = (value: unknown): string[] =>
  Array.isArray(value) ? value.map((item) => String(item)) : [];

const toFlowSegments = (value: unknown): FlowSegment[] =>
  Array.isArray(value)
    ? value
        .filter(isPayload)
        .map((item) => ({
          id: String(item.id || ''),
          title: String(item.title || item.id || ''),
          phase: String(item.phase || ''),
        }))
        .filter((item) => !!item.id)
    : [];

const toRoomParticipant = (value: unknown): RoomParticipant | null => {
  if (!isPayload(value) || !value.user_id || !value.name || !value.role) {
    return null;
  }

  return {
    user_id: String(value.user_id),
    name: String(value.name),
    role: String(value.role),
    stance: toOptionalString(value.stance),
    user_type: toOptionalString(value.user_type),
    can_moderate: value.can_moderate === undefined ? undefined : Boolean(value.can_moderate),
    can_speak: value.can_speak === undefined ? undefined : Boolean(value.can_speak),
  };
};

const toRoomParticipants = (value: unknown): RoomParticipant[] =>
  Array.isArray(value)
    ? value.map(toRoomParticipant).filter((item): item is RoomParticipant => item !== null)
    : [];

const toAIDebater = (value: unknown): AIDebater | null => {
  if (!isPayload(value) || !value.id || !value.role) {
    return null;
  }

  return {
    id: String(value.id),
    role: String(value.role),
    name: toOptionalString(value.name),
    stance: toOptionalString(value.stance),
  };
};

const toAIDebaters = (value: unknown): AIDebater[] =>
  Array.isArray(value)
    ? value.map(toAIDebater).filter((item): item is AIDebater => item !== null)
    : [];

const DebateArena: React.FC<DebateArenaProps> = ({ roomId = '', onEndDebate }) => {
  const { user } = useAuth();
  const { toast } = useToast();
  const [currentPhase, setCurrentPhase] = useState<string>('waiting');
  const [timeRemaining, setTimeRemaining] = useState(0);
  const [currentSpeakerRole, setCurrentSpeakerRole] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOff, setIsVideoOff] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [subtitle, setSubtitle] = useState<string>('');
  const [speakerMode, setSpeakerMode] = useState<string | null>(null);
  const [speakerOptions, setSpeakerOptions] = useState<string[]>([]);
  const [micOwnerUserId, setMicOwnerUserId] = useState<string | null>(null);
  const [micOwnerRole, setMicOwnerRole] = useState<string | null>(null);
  const [micExpiresAt, setMicExpiresAt] = useState<string | null>(null);
  const [freeDebateNextSide, setFreeDebateNextSide] = useState<string | null>(null);
  const [segmentTitle, setSegmentTitle] = useState<string | null>(null);
  const [segmentId, setSegmentId] = useState<string | null>(null);
  const [segmentIndex, setSegmentIndex] = useState<number | null>(null);
  const [aiTurnStatus, setAiTurnStatus] = useState<string>('idle');
  const [aiTurnSegmentTitle, setAiTurnSegmentTitle] = useState<string | null>(null);
  const [aiTurnSpeakerRole, setAiTurnSpeakerRole] = useState<string | null>(null);
  const [participants, setParticipants] = useState<RoomParticipant[]>([]);
  const [aiDebaters, setAiDebaters] = useState<AIDebater[]>([]);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [autoPlayEnabled, setAutoPlayEnabled] = useState(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [hasActiveLiveTtsStream, setHasActiveLiveTtsStream] = useState(false);
  const [streamedSpeechEntryIds, setStreamedSpeechEntryIds] = useState<string[]>([]);
  const [assignedParticipants, setAssignedParticipants] = useState<Array<{
    user_id: string;
    name: string;
    role: string;
    role_reason?: string | null;
    overall_score?: number;
  }>>([]);
  const [backendFlowSegments, setBackendFlowSegments] = useState<FlowSegment[]>([]);
  const [isProcessingReport, setIsProcessingReport] = useState(false);
  const [roomJoined, setRoomJoined] = useState(false);
  const [participantsLoadError, setParticipantsLoadError] = useState<string | null>(null);
  const [aiThinkingElapsedSec, setAiThinkingElapsedSec] = useState(0);
  const leaveToastLockRef = useRef(false);

  const recordingPermissionWaiters = useRef<Map<string, { resolve: (result: { allowed: boolean; message?: string }) => void; timeoutId: number }>>(new Map());
  const liveTtsPlayerRef = useRef<PcmStreamPlayer | null>(null);
  const arenaRootRef = useRef<HTMLDivElement>(null);
  const ttsStreamStartCountRef = useRef<Map<string, number>>(new Map());
  const ttsStreamChunkCountRef = useRef<Map<string, number>>(new Map());
  const ttsStreamEndCountRef = useRef<Map<string, number>>(new Map());
  // WebSocket 事件只注册一次，事件回调里通过 ref 读取最新状态，避免重复订阅导致同一条 AI 语音被处理多次。
  const currentUserIdRef = useRef<string>('');
  const currentUserRoleRef = useRef<string | null>(null);
  const speakerModeRef = useRef<string | null>(null);
  const autoPlayEnabledRef = useRef(true);
  const ignoredLiveTtsSpeechIdsRef = useRef<Set<string>>(new Set());
  const toastRef = useRef(toast);
  const onEndDebateRef = useRef(onEndDebate);
  const aiSpeechMetaRef = useRef<Map<string, { segmentId?: string; speakerRole?: string }>>(new Map());
  const startDebateWaiterRef = useRef<number | null>(null);

  // WebSocket连接
  const { isConnected, send, on, off } = useWebSocket(roomId, {
    onConnect: () => {
      debateDebug('DebateArena', 'Connected to debate room');
      setError(null);
      setRoomJoined(false);
    },
    onDisconnect: () => {
      debateDebug('DebateArena', 'Disconnected from debate room');
      setRoomJoined(false);
      if (startDebateWaiterRef.current !== null) {
        window.clearTimeout(startDebateWaiterRef.current);
        startDebateWaiterRef.current = null;
      }
    },
    onError: (err) => {
      console.error('WebSocket error:', err);
      setError('连接失败，请检查网络');
    }
  });

  const sendSpeechPlaybackEvent = React.useCallback((payload: {
    status: 'started' | 'finished' | 'failed' | 'skipped';
    speechId?: string;
    segmentId?: string | null;
    speakerRole?: string | null;
    source: 'stream' | 'audio_element' | 'manual_audio';
  }) => {
    const normalizedSpeechId = String(payload.speechId || '').trim();
    if (!normalizedSpeechId) {
      return;
    }
    const cachedMeta = aiSpeechMetaRef.current.get(normalizedSpeechId);
    const resolvedSpeakerRole = String(
      payload.speakerRole || cachedMeta?.speakerRole || ''
    ).trim();
    if (!resolvedSpeakerRole.startsWith('ai_')) {
      return;
    }
    const messageType: MessageType = payload.status === 'started'
      ? 'speech_playback_started'
      : payload.status === 'finished'
      ? 'speech_playback_finished'
      : payload.status === 'skipped'
      ? 'speech_playback_skipped'
      : 'speech_playback_failed';
    send(messageType, {
      speech_id: normalizedSpeechId,
      segment_id: payload.segmentId || cachedMeta?.segmentId || undefined,
      speaker_role: resolvedSpeakerRole,
      playback_source: payload.source,
    });
  }, [send]);

  useEffect(() => {
    liveTtsPlayerRef.current = new PcmStreamPlayer({
      onPlaybackStateChange: (isPlaying) => {
        audioPlaybackDebug('DebateArena', '流式 TTS 播放状态变更', {
          roomId,
          isPlaying,
        });
        setHasActiveLiveTtsStream(isPlaying);
      },
      onStreamPlaybackStart: (streamId) => {
        sendSpeechPlaybackEvent({
          status: 'started',
          speechId: streamId,
          source: 'stream',
        });
      },
      onStreamPlaybackComplete: (streamId) => {
        sendSpeechPlaybackEvent({
          status: 'finished',
          speechId: streamId,
          source: 'stream',
        });
      },
    });

    return () => {
      liveTtsPlayerRef.current?.dispose();
      liveTtsPlayerRef.current = null;
    };
  }, [roomId, sendSpeechPlaybackEvent]);

  useEffect(() => {
    // 切换房间时清空流式播报标记，避免上一场辩论残留到当前房间。
    setStreamedSpeechEntryIds([]);
    ignoredLiveTtsSpeechIdsRef.current.clear();
    ttsStreamStartCountRef.current.clear();
    ttsStreamChunkCountRef.current.clear();
    ttsStreamEndCountRef.current.clear();
    aiSpeechMetaRef.current.clear();
    audioPlaybackDebug('DebateArena', '房间切换，已清空音频排查计数器', { roomId });
  }, [roomId]);

  const debateTopic = '辩论进行中';
  const currentUserId = user?.id || '';
  const currentParticipant =
    participants.find((p) => p.user_id === currentUserId) || null;
  const currentUserRole =
    currentParticipant?.role ||
    assignedParticipants.find((p) => p.user_id === currentUserId)?.role ||
    null;
  const currentUserCanModerate = !!currentParticipant?.can_moderate;
  const isTeacherModeratorMode =
    currentParticipant?.user_type === 'teacher' || user?.user_type === 'teacher';
  const isStudentModeratorMode = currentUserCanModerate && !isTeacherModeratorMode;
  const socketConnected = isConnected;
  const debateReady = socketConnected && roomJoined;
  const accessTokenExists =
    typeof window !== 'undefined' ? !!window.localStorage.getItem('access_token') : false;
  const debugOrigin = typeof window !== 'undefined' ? window.location.origin : '';
  const debugWebSocketUrl = roomId ? buildDebateWebSocketUrl(roomId) : '';

  useEffect(() => {
    // 将会在 websocket 回调中使用到的动态值同步到 ref，避免因为依赖变化重复解绑/重绑事件。
    currentUserIdRef.current = currentUserId;
    currentUserRoleRef.current = currentUserRole;
    speakerModeRef.current = speakerMode;
    autoPlayEnabledRef.current = autoPlayEnabled;
    toastRef.current = toast;
    onEndDebateRef.current = onEndDebate;
  }, [autoPlayEnabled, currentUserId, currentUserRole, speakerMode, toast, onEndDebate]);

  useEffect(() => {
    if (currentPhase !== 'waiting' && startDebateWaiterRef.current !== null) {
      window.clearTimeout(startDebateWaiterRef.current);
      startDebateWaiterRef.current = null;
    }
  }, [currentPhase]);

  useEffect(() => {
    return () => {
      if (startDebateWaiterRef.current !== null) {
        window.clearTimeout(startDebateWaiterRef.current);
      }
    };
  }, []);

  useEffect(() => {
    debateDebug('DebateArena', 'Mount or room changed', {
      roomId,
      origin: debugOrigin,
      hasAccessToken: accessTokenExists,
      userId: currentUserId,
      userType: user?.user_type,
      websocketUrl: debugWebSocketUrl,
    });
  }, [roomId, debugOrigin, accessTokenExists, currentUserId, user?.user_type, debugWebSocketUrl]);

  useEffect(() => {
    if (aiTurnStatus !== 'thinking') {
      setAiThinkingElapsedSec(0);
      return;
    }

    const startedAt = Date.now();
    setAiThinkingElapsedSec(0);
    const timer = window.setInterval(() => {
      setAiThinkingElapsedSec(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
    }, 1000);

    return () => {
      window.clearInterval(timer);
    };
  }, [aiTurnStatus, aiTurnSegmentTitle, aiTurnSpeakerRole]);

  useEffect(() => {
    if (autoPlayEnabled) {
      return;
    }

    // 用户关闭自动播放后，立刻停止当前流式 TTS，避免 AI 继续自动出声。
    audioPlaybackDebug('DebateArena', '自动播放已关闭，停止当前流式 TTS', {
      roomId,
    });
    liveTtsPlayerRef.current?.stop();
  }, [autoPlayEnabled, roomId]);

  const shouldWarnBeforeLeave =
    currentPhase !== 'waiting' && currentPhase !== 'finished';
  const leaveWarningMessage = '离开将影响当前辩论进程。';
  const { allowNextNavigation } = useNavigationBlocker({
    when: shouldWarnBeforeLeave,
    message: leaveWarningMessage,
    onBlock: () => {
      if (leaveToastLockRef.current) {
        return;
      }

      leaveToastLockRef.current = true;
      toast({
        variant: 'destructive',
        title: '暂时不能离开辩论',
        description: leaveWarningMessage,
      });

      window.setTimeout(() => {
        leaveToastLockRef.current = false;
      }, 1000);
    },
  });

  useEffect(() => {
    if (!shouldWarnBeforeLeave) {
      return;
    }

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = leaveWarningMessage;
      return leaveWarningMessage;
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [leaveWarningMessage, shouldWarnBeforeLeave]);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === arenaRootRef.current);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const handleToggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
        return;
      }
      await arenaRootRef.current?.requestFullscreen();
    } catch (err: any) {
      toast({
        variant: 'destructive',
        title: '全屏切换失败',
        description: err?.message || '当前浏览器不允许进入全屏。',
      });
    }
  };

  /**
   * 统计同一 speech_id 在前端收到的流式事件次数，便于排查是否存在重复推送或重复监听。
   */
  const increaseStreamEventCount = (
    counterRef: React.MutableRefObject<Map<string, number>>,
    speechId: string
  ): number => {
    const nextCount = (counterRef.current.get(speechId) || 0) + 1;
    counterRef.current.set(speechId, nextCount);
    return nextCount;
  };

  /**
   * 统一输出当前 speech_id 的流式 TTS 调试信息，便于快速比对 start/chunk/end 的次数。
   */
  const debugStreamEvent = (
    eventName: 'tts_stream_start' | 'tts_stream_chunk' | 'tts_stream_end',
    speechId: string,
    extraPayload?: Record<string, unknown>
  ) => {
    audioPlaybackDebug('DebateArena', `收到 ${eventName}`, {
      roomId,
      speechId,
      startCount: ttsStreamStartCountRef.current.get(speechId) || 0,
      chunkCount: ttsStreamChunkCountRef.current.get(speechId) || 0,
      endCount: ttsStreamEndCountRef.current.get(speechId) || 0,
      ...extraPayload,
    });
  };

  const normalizeRole = (role: unknown) => String(role ?? '').trim();
  const roleMatches = (expected: string, actual: unknown) => {
    const r = normalizeRole(actual);
    if (!r) return false;
    if (r === expected) return true;
    if (r.endsWith(`.${expected}`)) return true;
    return r.includes(expected);
  };

  const phaseLabel = (phase: string) => {
    switch (phase) {
      case 'opening': return '立论陈词';
      case 'questioning': return '攻辩环节';
      case 'free_debate': return '自由辩论';
      case 'closing': return '总结陈词';
      case 'waiting': return '等待开始';
      case 'finished': return '已结束';
      default: return phase;
    }
  };

  const roleToPosition = (role: string) => {
    if (role === 'debater_1' || role === 'ai_1') return '一辩';
    if (role === 'debater_2' || role === 'ai_2') return '二辩';
    if (role === 'debater_3' || role === 'ai_3') return '三辩';
    return '四辩';
  };

  const resolveMediaUrl = (url?: string | null) => {
    if (!url) return undefined;
    const trimmed = String(url).trim();
    if (!trimmed) return undefined;
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) return trimmed;
    
    const base = getApiOriginBaseUrl();
    
    // 如果是上传文件，通常挂载在根目录下的 /uploads
    if (!base) return trimmed;
    if (trimmed.startsWith('/')) return `${base}${trimmed}`;
    return `${base}/${trimmed}`;
  };

  const findWsParticipantByRole = (role: string) => participants.find((x) => roleMatches(role, x?.role));
  const findAssignedByRole = (role: string) => assignedParticipants.find((x) => roleMatches(role, x?.role));

  const humanTeam: Participant[] = ['debater_1', 'debater_2', 'debater_3', 'debater_4'].map((role, idx) => {
    const p = findWsParticipantByRole(role);
    const assigned = p ? undefined : findAssignedByRole(role);
    const isCurrent = p?.user_id === currentUserId;
    const isOnline = !!p; // 用户在participants列表中表示在线
    
    return {
      id: p?.user_id || assigned?.user_id || `placeholder-${role}`,
      name: p?.name || assigned?.name || `等待加入`,
      position: roleToPosition(role) as Participant['position'],
      isAI: false,
      isMuted: p && isCurrent ? isMuted : false,
      isVideoOff: !isOnline || (isCurrent ? isVideoOff : false),
      isSpeaking: roleMatches(role, currentSpeakerRole) || (speakerMode === 'free' && roleMatches(role, micOwnerRole)),
      signalStrength: isOnline ? 85 : undefined, // 只有在线用户才有信号强度
      role: idx === 0 ? 'captain' : 'member',
    };
  });

  const aiTeam: AIAvatarType[] = ['ai_1', 'ai_2', 'ai_3', 'ai_4'].map((id) => {
    const a = aiDebaters.find((x) => x.id === id) || aiDebaters.find((x) => x.role === roleToPosition(id));
    const name = a?.name || id.toUpperCase();
    const aiType = id === 'ai_1' ? 'analytical' : id === 'ai_2' ? 'creative' : id === 'ai_3' ? 'aggressive' : 'balanced';
    return {
      id,
      name,
      position: roleToPosition(id) as AIAvatarType['position'],
      aiType,
      skillLevel: 85,
      isSpeaking: roleMatches(id, currentSpeakerRole) || (speakerMode === 'free' && roleMatches(id, micOwnerRole)),
      processingPower: 90,
    };
  });

  // WebSocket事件监听
  useEffect(() => {
    // 监听状态更新
    const handleStateUpdate = (data: WsPayload) => {
      debateDebug('DebateArena', 'State update', data);
      setRoomJoined(true);
      const nextParticipants = toRoomParticipants(data.participants);
      const currentUserRoleFromState = nextParticipants.length > 0
        ? nextParticipants.find((participant) => participant.user_id === currentUserIdRef.current)?.role || currentUserRoleRef.current
        : currentUserRoleRef.current;
      if (data.current_speaker !== undefined) {
        setCurrentSpeakerRole(toOptionalString(data.current_speaker));
        // 如果轮到当前用户发言，自动取消静音
        if (currentUserRoleFromState && roleMatches(currentUserRoleFromState, data.current_speaker)) {
          setIsMuted(false);
          debateDebug('DebateArena', '轮到当前用户发言，自动取消静音');
        }
      }
      if (data.current_phase) setCurrentPhase(String(data.current_phase));
      if (typeof data.time_remaining === 'number') setTimeRemaining(data.time_remaining);
      if (data.segment_title) setSegmentTitle(String(data.segment_title));
      if (data.segment_id !== undefined) setSegmentId(toOptionalString(data.segment_id));
      if (typeof data.segment_index === 'number') setSegmentIndex(data.segment_index);
      if (data.speaker_mode !== undefined) setSpeakerMode(toOptionalString(data.speaker_mode));
      if (Array.isArray(data.speaker_options)) setSpeakerOptions(toStringArray(data.speaker_options));
      if (data.mic_owner_user_id !== undefined) setMicOwnerUserId(toOptionalString(data.mic_owner_user_id));
      if (data.mic_owner_role !== undefined) setMicOwnerRole(toOptionalString(data.mic_owner_role));
      if (data.mic_expires_at !== undefined) setMicExpiresAt(toOptionalString(data.mic_expires_at));
      if (data.free_debate_next_side !== undefined) setFreeDebateNextSide(toOptionalString(data.free_debate_next_side));
      if (data.ai_turn_status !== undefined) setAiTurnStatus(toOptionalString(data.ai_turn_status) || 'idle');
      if (data.ai_turn_segment_title !== undefined) setAiTurnSegmentTitle(toOptionalString(data.ai_turn_segment_title));
      if (data.ai_turn_speaker_role !== undefined) setAiTurnSpeakerRole(toOptionalString(data.ai_turn_speaker_role));
      if (Array.isArray(data.flow_segments)) setBackendFlowSegments(toFlowSegments(data.flow_segments));
      if (Array.isArray(data.participants)) setParticipants(nextParticipants);
      if (Array.isArray(data.ai_debaters)) setAiDebaters(toAIDebaters(data.ai_debaters));
    };

    const handleRoomJoined = () => {
      setRoomJoined(true);
      setError(null);
    };

    // 监听用户加入事件
    const handleUserJoined = (data: WsPayload) => {
      debateDebug('DebateArena', 'User joined', data);
      const participant = toRoomParticipant(data);
      if (!participant) return;
      // 使用函数式更新基于最新 participants 去重，避免旧闭包导致同一用户被重复插入。
      setParticipants(prev => {
        const exists = prev.some((item) => item.user_id === participant.user_id);
        if (exists) return prev;
        return [...prev, participant];
      });
    };

    // 监听用户离开事件
    const handleUserLeft = (data: WsPayload) => {
      debateDebug('DebateArena', 'User left', data);
      if (data.user_id) {
        // 从participants列表中移除用户
        setParticipants(prev => prev.filter(p => p.user_id !== String(data.user_id)));
      }
    };

    // 监听阶段变化
    const handlePhaseChange = (data: WsPayload) => {
      debateDebug('DebateArena', 'Phase change', data);
      if (data.phase) setCurrentPhase(String(data.phase));
    };

    const handleSegmentChange = (data: WsPayload) => {
      if (data.segment_title) setSegmentTitle(String(data.segment_title));
      if (data.segment_id !== undefined) setSegmentId(toOptionalString(data.segment_id));
      if (typeof data.segment_index === 'number') setSegmentIndex(data.segment_index);
      if (data.speaker_mode !== undefined) setSpeakerMode(toOptionalString(data.speaker_mode));
      if (Array.isArray(data.speaker_options)) setSpeakerOptions(toStringArray(data.speaker_options));
      if (data.phase) setCurrentPhase(String(data.phase));
    };

    // 监听计时器更新
    const handleTimerUpdate = (data: WsPayload) => {
      debateDebug('DebateArena', 'Timer update', data);
      if (typeof data.time_remaining === 'number') {
        setTimeRemaining(data.time_remaining);
      }
    };

    // 监听字幕
    const handleSubtitle = (data: WsPayload) => {
      debateDebug('DebateArena', 'Subtitle', data);
      setSubtitle(toOptionalString(data.text) || '');
      // 5秒后清除字幕
      setTimeout(() => setSubtitle(''), 5000);
    };

    // 监听发言
    const handleSpeech = (data: WsPayload) => {
      debateDebug('DebateArena', 'Speech', data);
      const speechId = String(data?.speech_id || data?.message_id || data?.id || '').trim();
      audioPlaybackDebug('DebateArena', '收到 speech 事件', {
        roomId,
        speechId,
        role: data?.role,
        hasAudioUrl: !!(data?.audio_url || data?.file_url || data?.url),
        contentLength: String(data?.content || data?.text || '').length,
      });
      if (data.role) setCurrentSpeakerRole(String(data.role));
      if (speechId && String(data?.role || '').trim().startsWith('ai_')) {
        aiSpeechMetaRef.current.set(speechId, {
          segmentId: String(data?.segment_id || '').trim() || undefined,
          speakerRole: String(data?.role || '').trim() || undefined,
        });
      }

      // 使用可回填的转录合并工具，兼容“音频先到文本后补”和“文本先到音频后补”。
      const entry = normalizeTranscriptEntry(data as TranscriptEvent, {
        resolveMediaUrl,
        resolvePosition: roleToPosition,
        resolveSpeakerName: (event) =>
          event.name || (String(event.role || '').startsWith('ai_') ? 'AI' : '学生'),
        placeholderText: TRANSCRIPT_PENDING_TEXT,
      });

      if (!entry.message && !entry.audioUrl) {
        return;
      }

      setTranscript((prev) => upsertTranscriptEntry(prev, entry).slice(-200));
      audioPlaybackDebug('DebateArena', 'speech 事件已写入 transcript', {
        roomId,
        entryId: entry.id,
        speechId,
        hasAudioUrl: !!entry.audioUrl,
        isPendingText: !!entry.isPendingText,
      });
      setSubtitle(`${entry.speaker}：${entry.message}`);
      setTimeout(() => setSubtitle(''), 5000);
    };

    const handleTtsStreamStart = (data: WsPayload) => {
      const speechId = String(data?.speech_id || data?.message_id || '').trim();
      if (!speechId) return;
      const startCount = increaseStreamEventCount(ttsStreamStartCountRef, speechId);
      const transcriptEntryId = buildTranscriptSpeechEntryId(speechId);
      if (!autoPlayEnabledRef.current) {
        // 自动播放关闭时，整条流式 TTS 都应静默跳过，直到收到 end 事件再清理忽略标记。
        ignoredLiveTtsSpeechIdsRef.current.add(speechId);
        sendSpeechPlaybackEvent({
          status: 'skipped',
          speechId,
          speakerRole: toOptionalString(data?.role),
          source: 'stream',
        });
        debugStreamEvent('tts_stream_start', speechId, {
          startCount,
          transcriptEntryId,
          skippedBecauseAutoPlayDisabled: true,
        });
        return;
      }
      if (transcriptEntryId) {
        // 这类消息已经由流式 PCM 播过，后续整段 audio_url 回填时不应再自动重播。
        setStreamedSpeechEntryIds((prev) => {
          if (prev.includes(transcriptEntryId)) return prev;
          return [...prev.slice(-199), transcriptEntryId];
        });
      }
      debugStreamEvent('tts_stream_start', speechId, {
        startCount,
        transcriptEntryId,
      });
      void liveTtsPlayerRef.current?.startStream(speechId);
    };

    const handleTtsStreamChunk = (data: WsPayload) => {
      const speechId = String(data?.speech_id || data?.message_id || '').trim();
      const audioBase64 = String(data?.audio_base64 || '').trim();
      if (!speechId || !audioBase64) return;
      if (!autoPlayEnabledRef.current) {
        ignoredLiveTtsSpeechIdsRef.current.add(speechId);
        debugStreamEvent('tts_stream_chunk', speechId, {
          skippedBecauseAutoPlayDisabled: true,
        });
        return;
      }
      if (ignoredLiveTtsSpeechIdsRef.current.has(speechId)) {
        debugStreamEvent('tts_stream_chunk', speechId, {
          skippedBecauseSpeechWasIgnored: true,
        });
        return;
      }
      const chunkCount = increaseStreamEventCount(ttsStreamChunkCountRef, speechId);
      debugStreamEvent('tts_stream_chunk', speechId, {
        chunkCount,
        chunkBytes: Math.floor(audioBase64.length * 0.75),
        sampleRate: typeof data?.sample_rate === 'number' ? data.sample_rate : 24000,
      });
      void liveTtsPlayerRef.current?.appendChunk(speechId, {
        audioBase64,
        sampleRate: typeof data?.sample_rate === 'number' ? data.sample_rate : 24000,
        channels: typeof data?.channels === 'number' ? data.channels : 1,
        sampleWidth: typeof data?.sample_width === 'number' ? data.sample_width : 2,
      });
    };

    const handleTtsStreamEnd = (data: WsPayload) => {
      const speechId = String(data?.speech_id || data?.message_id || '').trim();
      if (!speechId) return;
      if (!autoPlayEnabledRef.current || ignoredLiveTtsSpeechIdsRef.current.has(speechId)) {
        ignoredLiveTtsSpeechIdsRef.current.delete(speechId);
        debugStreamEvent('tts_stream_end', speechId, {
          skippedBecauseAutoPlayDisabled: true,
        });
        return;
      }
      const endCount = increaseStreamEventCount(ttsStreamEndCountRef, speechId);
      debugStreamEvent('tts_stream_end', speechId, {
        endCount,
      });
      void liveTtsPlayerRef.current?.endStream(speechId);
    };


    const handlePermissionDenied = (data: WsPayload) => {
      toastRef.current({
        title: '无法发言',
        description: toOptionalString(data.message) || '当前无发言权限',
        variant: 'destructive',
      });
    };

    const handleMicGrabbed = (data: WsPayload) => {
      if (data.user_id !== undefined) setMicOwnerUserId(toOptionalString(data.user_id));
      if (data.role !== undefined) setMicOwnerRole(toOptionalString(data.role));
      if (data.expires_at !== undefined) setMicExpiresAt(toOptionalString(data.expires_at));
      if (data.role) setCurrentSpeakerRole(String(data.role));
      // 自由辩论阶段：当前用户抢到麦时，自动取消静音，允许发言
      if (data.user_id === currentUserIdRef.current) {
        setIsMuted(false);
        debateDebug('DebateArena', '当前用户抢麦成功，自动取消静音');
      }
    };

    const handleMicReleased = () => {
      setMicOwnerUserId(null);
      setMicOwnerRole(null);
      setMicExpiresAt(null);
      if (speakerModeRef.current === 'free') setCurrentSpeakerRole(null);
    };

    const handleSpeakerSelected = (data: WsPayload) => {
      if (data.role !== undefined) {
        setCurrentSpeakerRole(toOptionalString(data.role));
      }
    };

    const handleModeratorTransferred = (data: WsPayload) => {
      const newModeratorUserId = toOptionalString(data.new_moderator_user_id);
      setParticipants((prev) =>
        prev.map((participant) => ({
          ...participant,
          can_moderate: participant.user_id === newModeratorUserId,
        }))
      );
      if (newModeratorUserId === currentUserIdRef.current) {
        toastRef.current({
          title: '主持权已转移给你',
          description: '你现在可以控制辩论流程，同时继续作为辩手发言。',
        });
      }
    };

    const handleModeratorMissing = () => {
      setParticipants((prev) =>
        prev.map((participant) => ({ ...participant, can_moderate: false }))
      );
      toastRef.current({
        title: '当前暂无主持人在线',
        description: '等待新的学生主持人接管后再开始或推进流程。',
      });
    };

    // 监听错误
    const handleError = (data: WsPayload) => {
      console.error('WebSocket error:', data);
      if (startDebateWaiterRef.current !== null) {
        window.clearTimeout(startDebateWaiterRef.current);
        startDebateWaiterRef.current = null;
      }
      setError(toOptionalString(data.message) || '发生错误');
    };

    const handleDebateProcessing = (data: WsPayload) => {
      debateDebug('DebateArena', 'Debate processing', data);
      setIsProcessingReport(true);
      toastRef.current({
        title: '辩论已结束',
        description: toOptionalString(data.message) || '正在生成辩论报告和评分，请稍候...',
        duration: 10000, 
      });
    };

    const handleDebateEnded = (data: WsPayload) => {
      setIsProcessingReport(false);
      toastRef.current({
        title: '报告生成完成',
        description: data.timestamp ? `结束时间：${String(data.timestamp)}` : undefined,
      });
      setCurrentPhase('finished');
      allowNextNavigation();
      onEndDebateRef.current?.();
    };

    const handleRecordingPermission = (data: WsPayload) => {
      const requestId = data?.request_id;
      if (!requestId) return;
      const waiter = recordingPermissionWaiters.current.get(String(requestId));
      if (!waiter) return;
      clearTimeout(waiter.timeoutId);
      recordingPermissionWaiters.current.delete(String(requestId));
      waiter.resolve({ allowed: !!data.allowed, message: toOptionalString(data.message) || undefined });
    };

    // 注册事件监听器
    audioPlaybackDebug('DebateArena', '开始注册房间 websocket 监听', { roomId });
    const handleAudioProcessed = (data: WsPayload) => {
      const text = toOptionalString(data?.text);
      if (!text) return;
      handleSpeech({
        ...data,
        content: text,
        transcription_status: 'completed',
        is_audio: true,
      });
    };

    on('room_joined', handleRoomJoined);
    on('state_update', handleStateUpdate);
    on('user_joined', handleUserJoined);
    on('user_left', handleUserLeft);
    on('phase_change', handlePhaseChange);
    on('segment_change', handleSegmentChange);
    on('timer_update', handleTimerUpdate);
    on('subtitle', handleSubtitle);
    on('speech', handleSpeech);
    on('tts_stream_start', handleTtsStreamStart);
    on('tts_stream_chunk', handleTtsStreamChunk);
    on('tts_stream_end', handleTtsStreamEnd);
    on('recording_permission', handleRecordingPermission);
    on('audio_processed', handleAudioProcessed);
    on('permission_denied', handlePermissionDenied);
    on('mic_grabbed', handleMicGrabbed);
    on('mic_released', handleMicReleased);
    on('speaker_selected', handleSpeakerSelected);
    on('moderator_transferred', handleModeratorTransferred);
    on('moderator_missing', handleModeratorMissing);
    on('debate_processing', handleDebateProcessing);
    on('debate_ended', handleDebateEnded);
    on('error', handleError);

    // 清理函数
    return () => {
      audioPlaybackDebug('DebateArena', '开始清理房间 websocket 监听', { roomId });
      off('room_joined', handleRoomJoined);
      off('state_update', handleStateUpdate);
      off('user_joined', handleUserJoined);
      off('user_left', handleUserLeft);
      off('phase_change', handlePhaseChange);
      off('segment_change', handleSegmentChange);
      off('timer_update', handleTimerUpdate);
      off('subtitle', handleSubtitle);
      off('recording_permission', handleRecordingPermission);
      off('audio_processed', handleAudioProcessed);
      off('speech', handleSpeech);
      off('tts_stream_start', handleTtsStreamStart);
      off('tts_stream_chunk', handleTtsStreamChunk);
      off('tts_stream_end', handleTtsStreamEnd);
      off('permission_denied', handlePermissionDenied);
      off('mic_grabbed', handleMicGrabbed);
      off('mic_released', handleMicReleased);
      off('speaker_selected', handleSpeakerSelected);
      off('moderator_transferred', handleModeratorTransferred);
      off('moderator_missing', handleModeratorMissing);
      off('debate_processing', handleDebateProcessing);
      off('debate_ended', handleDebateEnded);
      off('error', handleError);
    };
  }, [on, off]);

  useEffect(() => {
    const load = async () => {
      if (!roomId) {
        setAssignedParticipants([]);
        setParticipantsLoadError('缺少 roomId，未发起参与者加载');
        debateDebug('DebateArena', 'Skip loading participants because roomId is empty');
        return;
      }
      try {
        setParticipantsLoadError(null);
        const data = await StudentService.getDebateParticipants(roomId);
        setAssignedParticipants(Array.isArray(data) ? data : []);
      } catch (loadError: any) {
        setAssignedParticipants([]);
        setParticipantsLoadError(
          String(loadError?.response?.data?.detail || loadError?.message || '参与者加载失败')
        );
      }
    };
    load();
  }, [roomId]);

  // 删除模拟发言者轮换（现在由WebSocket控制）
  // 删除辩论阶段推进（现在由WebSocket控制）

  const handleToggleMic = () => {
    setIsMuted(!isMuted);
  };

  const handleToggleVideo = () => {
    setIsVideoOff(!isVideoOff);
  };

  const handleSendMessage = (message: string) => {
    if (isConnected && roomJoined) {
      send('speech', { content: message });
    }
  };

  const handleSendAudio = (audioBlob: Blob, clientTranscript?: string): Promise<void> => {
    if (isConnected && roomJoined) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = () => {
          reject(new Error('读取录音文件失败，请重新录制后再试'));
        };
        reader.onload = () => {
          try {
            const base64Audio = (reader.result as string) || '';
            const parts = base64Audio.split(',');
            const raw = parts.length > 1 ? parts[1] : base64Audio;
            const mime = String(audioBlob.type || '').toLowerCase();
            const format =
              mime.includes('wav')
                ? 'wav'
                : mime.includes('mpeg') || mime.includes('mp3')
                  ? 'mp3'
                  : mime.includes('ogg')
                    ? 'ogg'
                    : mime.includes('mp4')
                      ? 'mp4'
                      : mime.includes('m4a') || mime.includes('x-m4a')
                        ? 'm4a'
                        : 'webm';
            send('audio', {
              audio_data: raw,
              audio_format: format,
              client_transcript: clientTranscript?.trim() || undefined,
            });
            resolve();
          } catch (error) {
            reject(error);
          }
        };
        reader.readAsDataURL(audioBlob);
      });
    }

    return Promise.reject(new Error('未连接到辩论房间，请稍后重试'));
  };

  const requestRecordingPermission = async (): Promise<{ allowed: boolean; message?: string }> => {
    if (!isConnected || !roomJoined) {
      return { allowed: false, message: '未连接到辩论房间，请稍后重试' };
    }
    const requestId =
      typeof globalThis.crypto?.randomUUID === 'function'
        ? globalThis.crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const result = await new Promise<{ allowed: boolean; message?: string }>((resolve) => {
      const timeoutId = window.setTimeout(() => {
        recordingPermissionWaiters.current.delete(String(requestId));
        resolve({ allowed: false, message: '服务端未响应，请稍后重试' });
      }, 3000);
      recordingPermissionWaiters.current.set(String(requestId), { resolve, timeoutId });
      send('request_recording', { request_id: requestId });
    });
    return result;
  };

  const handleRequestStartRecording = async (): Promise<boolean> => {
    const result = await requestRecordingPermission();
    if (result.allowed) return true;
    toast({
      title: '无法开始录音',
      description: result.message || '当前无发言权限',
      variant: 'destructive',
    });
    return false;
  };

  const handleGrabMic = () => {
    if (isConnected && roomJoined) {
      send('grab_mic', {});
    }
  };

  const handleEndTurn = () => {
    if (isConnected && roomJoined) {
      send('end_turn', {});
    } else {
      toast({
        title: '无法结束发言',
        description: '未连接到辩论房间，请稍后重试',
        variant: 'destructive',
      });
    }
  };

  const handleStartDebate = () => {
    if (!isConnected || !roomJoined) {
      toast({
        title: '无法开始辩论',
        description: '未连接到辩论房间，请稍后重试',
        variant: 'destructive',
      });
      return;
    }
    if (!currentUserCanModerate) {
      toast({
        title: '无法开始辩论',
        description: '当前账号没有主持权限，请确认一号辩手已进入该房间。',
        variant: 'destructive',
      });
      return;
    }

    debateDebug('DebateArena', 'Send start_debate', {
      roomId,
      currentUserId,
      currentUserRole,
      currentUserCanModerate,
      roomJoined,
      isConnected,
    });
    send('start_debate', {});
    if (startDebateWaiterRef.current !== null) {
      window.clearTimeout(startDebateWaiterRef.current);
    }
    startDebateWaiterRef.current = window.setTimeout(() => {
      startDebateWaiterRef.current = null;
      if (currentPhase === 'waiting') {
        toast({
          title: '开始辩论未生效',
          description: '服务端未返回开赛状态，请确认后端已重启并且一号辩手主持权限已写入。',
          variant: 'destructive',
        });
      }
    }, 3000);
  };

  const handleAdvanceSegment = () => {
    if (isConnected && roomJoined) {
      send('advance_segment', {});
    }
  };

  const handleSelectSpeaker = () => {
    if (isConnected && roomJoined && currentUserRole) {
      send('select_speaker', { role: currentUserRole });
    }
  };

  const handleEndDebate = () => {
    if (isConnected && roomJoined) {
      send('end_debate', {});
    }
  };

  const getCurrentSpeakerInfo = () => {
    if (!currentSpeakerRole) return null;
    const humanCanonical = ['debater_1', 'debater_2', 'debater_3', 'debater_4'].find((r) =>
      roleMatches(r, currentSpeakerRole)
    );
    if (humanCanonical) {
      return humanTeam.find((m) => m.position === roleToPosition(humanCanonical)) || null;
    }
    const ai = aiTeam.find((m) => roleMatches(m.id, currentSpeakerRole));
    return ai || null;
  };

  const currentSpeakerInfo = getCurrentSpeakerInfo();
  const isFreeDebate = currentPhase === 'free_debate' && speakerMode === 'free';
  const resolveAiSpeakerName = (role?: string | null) => {
    const normalizedRole = String(role || '').trim();
    if (!normalizedRole) return 'AI 智能体';
    const matched = aiDebaters.find((item) => item?.id === normalizedRole);
    if (matched?.name) return matched.name;
    return `反方${roleToPosition(normalizedRole)}`;
  };
  const aiTurnStatusMeta = (() => {
    const normalizedStatus = String(aiTurnStatus || 'idle').trim();
    if (!normalizedStatus || normalizedStatus === 'idle') return null;
    const speakerName = resolveAiSpeakerName(aiTurnSpeakerRole);
    const segmentLabel = aiTurnSegmentTitle || segmentTitle || phaseLabel(currentPhase);

    switch (normalizedStatus) {
      case 'thinking': {
        const waitingSuffix =
          aiThinkingElapsedSec > 0 ? `，已等待 ${aiThinkingElapsedSec} 秒` : '';
        const waitingHint =
          aiThinkingElapsedSec >= 60
            ? '，如果持续很久，通常说明后端卡在 AI 生成或数据库写入阶段'
            : '';
        return {
          label: 'AI思考中',
          detail: `${speakerName} 正在基于最新发言准备回应${waitingSuffix}${waitingHint}`,
          badgeClassName: 'border-amber-200 bg-amber-50 text-amber-800',
        };
      }
      case 'ready':
        return {
          label: 'AI已准备，等待轮次',
          detail: `${speakerName} 已完成草稿准备，目标环节：${segmentLabel}`,
          badgeClassName: 'border-blue-200 bg-blue-50 text-blue-800',
        };
      case 'speaking':
        return {
          label: 'AI正在发言',
          detail: `${speakerName} 正在正式输出`,
          badgeClassName: 'border-[#e0d8ef] bg-[#eae6f6] text-slate-800',
        };
      case 'recomputing':
        return {
          label: 'AI重算中',
          detail: `${speakerName} 正在根据新提交发言重算草稿`,
          badgeClassName: 'border-rose-200 bg-rose-50 text-rose-800',
        };
      default:
        return {
          label: `AI状态：${normalizedStatus}`,
          detail: `${speakerName} 当前目标环节：${segmentLabel}`,
          badgeClassName: 'border-slate-200 bg-slate-50 text-slate-700',
        };
    }
  })();
  
  // 检查麦克风是否处于活跃状态（未过期）
  const micActive = !!micOwnerUserId && !!micExpiresAt && new Date(micExpiresAt).getTime() > Date.now();
  
  // 调试日志
  if (isFreeDebate && micOwnerUserId) {
    debateDebug('DebateArena', '抢麦状态检查', {
      micOwnerUserId,
      currentUserId,
      micExpiresAt,
      micActive,
      expiresTime: micExpiresAt ? new Date(micExpiresAt).getTime() : null,
      nowTime: Date.now(),
      isOwner: micOwnerUserId === currentUserId
    });
  }
  
  const canSpeak = isTeacherModeratorMode
    ? false
    : isFreeDebate
    ? micOwnerUserId === currentUserId && micActive
    : !!currentUserRole && roleMatches(currentUserRole, currentSpeakerRole);
  const canGrabMic =
    !isTeacherModeratorMode && isFreeDebate && !micActive && freeDebateNextSide !== 'ai';
  const micStatusText = isFreeDebate
    ? micActive
      ? `当前持麦：${micOwnerRole || ''}${micOwnerUserId === currentUserId ? '（你）' : ''}`
      : freeDebateNextSide === 'ai'
      ? aiTurnStatusMeta?.detail || '反方 AI 回合进行中，暂不可抢麦'
      : '当前无人持麦'
    : segmentTitle || undefined;
  const canStartDebate = debateReady && currentUserCanModerate && currentPhase === 'waiting';
  const canSelectCurrentUserSpeaker =
    debateReady &&
    speakerMode === 'choice' &&
    !isTeacherModeratorMode &&
    !!currentUserRole &&
    speakerOptions.some((role) => roleMatches(role, currentUserRole));
  const isCurrentUserSelectedSpeaker =
    !!currentUserRole && roleMatches(currentUserRole, currentSpeakerRole);

  const flowSegments = [
    { id: 'opening_positive_1', title: '立论阶段：正方一辩', phase: 'opening' },
    { id: 'opening_negative_1', title: '立论阶段：反方一辩', phase: 'opening' },
    { id: 'questioning_1_ai2_ask', title: '盘问第1轮：反方二辩提问', phase: 'questioning' },
    { id: 'questioning_1_pos_answer', title: '盘问第1轮：正方回答（二辩或三辩）', phase: 'questioning' },
    { id: 'questioning_2_pos2_ask', title: '盘问第2轮：正方二辩提问', phase: 'questioning' },
    { id: 'questioning_2_neg_answer', title: '盘问第2轮：反方回答（二辩或三辩）', phase: 'questioning' },
    { id: 'questioning_3_ai3_ask', title: '盘问第3轮：反方三辩提问', phase: 'questioning' },
    { id: 'questioning_3_pos_answer', title: '盘问第3轮：正方回答（一辩或四辩）', phase: 'questioning' },
    { id: 'questioning_4_pos3_ask', title: '盘问第4轮：正方三辩提问', phase: 'questioning' },
    { id: 'questioning_4_neg_answer', title: '盘问第4轮：反方回答（一辩或四辩）', phase: 'questioning' },
    { id: 'questioning_neg_summary', title: '攻辩小结：反方一辩总结', phase: 'questioning' },
    { id: 'questioning_pos_summary', title: '攻辩小结：正方一辩总结', phase: 'questioning' },
    { id: 'free_debate', title: '自由辩论：抢麦发言（每次≤30秒）', phase: 'free_debate' },
    { id: 'closing_negative_4', title: '总结陈词：反方四辩', phase: 'closing' },
    { id: 'closing_positive_4', title: '总结陈词：正方四辩', phase: 'closing' },
  ];
  const effectiveFlowSegments = backendFlowSegments.length > 0 ? backendFlowSegments : flowSegments;
  const lastSegmentId = effectiveFlowSegments[effectiveFlowSegments.length - 1]?.id;
  const isLastSegment =
    (!!lastSegmentId && segmentId === lastSegmentId) ||
    (typeof segmentIndex === 'number' && segmentIndex === effectiveFlowSegments.length - 1);

  const hasDebater4Online = participants.some((p) => roleMatches('debater_4', p?.role));
  const canAdvanceSegment =
    debateReady &&
    currentUserCanModerate &&
    currentPhase !== 'waiting' &&
    currentPhase !== 'finished' &&
    !isLastSegment;
  const canEndDebate =
    debateReady &&
    currentUserCanModerate &&
    currentPhase !== 'waiting' &&
    currentPhase !== 'finished' &&
    (isLastSegment ||
      (currentPhase === 'closing' && segmentId === 'closing_negative_4' && !hasDebater4Online));
  const humanOnlineMembers = humanTeam.filter((m) => typeof m.signalStrength === 'number' && (m.signalStrength || 0) > 0);
  const humanOnlineCount = humanOnlineMembers.length;
  const humanAvgSignal = humanOnlineCount > 0 ? Math.round(humanOnlineMembers.reduce((sum, m) => sum + (m.signalStrength || 0), 0) / humanOnlineCount) : 0;
  const humanStatusText = humanOnlineCount === 0 ? '等待加入' : humanOnlineCount === 4 ? '在线活跃' : `在线 ${humanOnlineCount}/4`;
  const aiAvgProcessing = Math.round(aiTeam.reduce((sum, m) => sum + (m.processingPower || 0), 0) / Math.max(aiTeam.length, 1));
  const debateProgressPercent =
    typeof segmentIndex === 'number' && effectiveFlowSegments.length > 0
      ? Math.min(100, Math.max(4, ((segmentIndex + 1) / effectiveFlowSegments.length) * 100))
      : currentPhase === 'waiting'
      ? 4
      : currentPhase === 'finished'
      ? 100
      : 12;
  const currentActionTitle = isTeacherModeratorMode
    ? '主持观察中'
    : canSpeak
    ? '轮到你发言'
    : canGrabMic
    ? '可以抢麦'
    : freeDebateNextSide === 'ai'
    ? '等待 AI 回应'
    : '等待轮次';
  const currentActionDescription = isTeacherModeratorMode
    ? '教师模式下只保留流程控制和记录查看，学生发言入口已关闭。'
    : canSpeak
    ? '你已经拥有当前发言权，可以录音发言，也可以用文字补充观点。'
    : canGrabMic
    ? '自由辩论当前无人持麦，点击抢麦后即可开始发言。'
    : micStatusText || '请关注顶部流程和当前发言席位，轮到你时操作区会高亮。';

  return (
    <div
      ref={arenaRootRef}
      className="relative flex min-h-screen flex-col overflow-hidden bg-[radial-gradient(circle_at_8%_10%,rgba(216,231,242,0.78),transparent_25%),radial-gradient(circle_at_90%_18%,rgba(249,236,222,0.82),transparent_24%),linear-gradient(180deg,#fbf7f1_0%,#f8f5f1_52%,#f7f1ea_100%)]"
    >
      {/* 错误提示 */}
      {error && (
        <div className="fixed top-4 right-4 z-50 max-w-md">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </div>
      )}

      {/* 连接状态指示器 */}
      {!roomJoined && (
        <div className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50">
          <Alert className="bg-amber-100 border-amber-300">
            <Loader2 className="h-4 w-4 animate-spin text-amber-600" />
            <AlertDescription className="text-amber-800">
              {isConnected ? 'WebSocket 已连接，正在等待房间确认...' : '正在连接到辩论房间...'}
            </AlertDescription>
          </Alert>
        </div>
      )}

      {participantsLoadError && (
        <div className="fixed top-16 right-4 z-50 max-w-md">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{participantsLoadError}</AlertDescription>
          </Alert>
        </div>
      )}

      {/* 实时字幕 */}
      {subtitle && (
        <div className="fixed bottom-32 left-1/2 transform -translate-x-1/2 z-50 max-w-2xl">
          <div className="student-card-muted px-6 py-3 text-center text-slate-900">
            {subtitle}
          </div>
        </div>
      )}

      <Dialog open={isSettingsOpen} onOpenChange={setIsSettingsOpen}>
        <DialogContent className="rounded-[16px] border-[#d8cdbf] bg-[#fbf5ee] text-slate-900">
          <DialogHeader>
            <DialogTitle>辩论设置</DialogTitle>
          </DialogHeader>
          <div className="space-y-5 py-2">
            <div className="flex items-center justify-between gap-4 rounded-[14px] border border-[#ece4da] bg-white/80 p-4">
              <div>
                <Label htmlFor="debate-autoplay" className="text-sm font-medium text-slate-900">
                  AI 语音自动播放
                </Label>
                <p className="mt-1 text-xs text-slate-500">
                  关闭后，新的 AI 流式语音会被跳过并释放播放等待。
                </p>
              </div>
              <Switch
                id="debate-autoplay"
                checked={autoPlayEnabled}
                onCheckedChange={setAutoPlayEnabled}
              />
            </div>
            <div className="rounded-[14px] border border-[#ece4da] bg-white/80 p-4 text-sm text-slate-700">
              <div className="flex items-center justify-between">
                <span>流式播放状态</span>
                <Badge className={hasActiveLiveTtsStream ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'student-pill'}>
                  {hasActiveLiveTtsStream ? '播放中' : '空闲'}
                </Badge>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* 报告生成中遮罩层 */}
      {isProcessingReport && (
        <div className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-slate-900/35 backdrop-blur-sm">
          <div className="student-card flex max-w-md flex-col items-center p-8 text-center">
            <Loader2 className="mb-4 h-12 w-12 animate-spin text-slate-700" />
            <h3 className="mb-2 text-xl font-semibold text-slate-900">正在生成辩论报告</h3>
            <p className="text-slate-600">
              AI裁判正在对整场辩论进行深度分析和评分...
            </p>
            <p className="mt-4 text-sm text-slate-500">
              这可能需要几十秒的时间，请勿关闭页面
            </p>
          </div>
        </div>
      )}

      {/* 抢麦成功提示 - 显眼的位置 */}
      {isFreeDebate && micActive && (
        <div className="fixed top-24 left-1/2 transform -translate-x-1/2 z-50">
          <Alert className="border-[#e0d8ef] bg-[#eae6f6] shadow-[0_18px_40px_rgba(91,80,120,0.16)]">
            <Radio className="h-5 w-5 text-slate-800" />
            <AlertDescription className="text-lg font-semibold text-slate-900">
              {micOwnerUserId === currentUserId ? (
                <span className="flex items-center gap-2">
                  <span className="inline-block h-3 w-3 rounded-full bg-slate-900"></span>
                  你已抢麦成功！可以开始发言
                </span>
              ) : (
                <span>
                  {participants.find(p => p.user_id === micOwnerUserId)?.name || '某位辩手'} 正在发言中...
                </span>
              )}
            </AlertDescription>
          </Alert>
        </div>
      )}

      {/* 顶部信息栏 */}
      <DebateHeader
        topic={debateTopic}
        currentPhase={phaseLabel(currentPhase)}
        segmentTitle={segmentTitle || undefined}
        timeRemaining={timeRemaining}
        canStartDebate={canStartDebate}
        canAdvanceSegment={canAdvanceSegment}
        canEndDebate={canEndDebate}
        onStartDebate={handleStartDebate}
        onAdvanceSegment={handleAdvanceSegment}
        onEndDebate={handleEndDebate}
        onFullscreen={handleToggleFullscreen}
        onSettings={() => setIsSettingsOpen(true)}
        isFullscreen={isFullscreen}
        autoPlayEnabled={autoPlayEnabled}
        onToggleAutoPlay={() => setAutoPlayEnabled((prev) => !prev)}
      />

      <div className="student-container grid min-h-0 flex-1 gap-5 pb-6 xl:grid-cols-[minmax(0,1fr)_390px] xl:overflow-hidden">
        <main className="flex min-h-0 flex-col gap-5 overflow-y-auto pr-1 custom-scrollbar">
          {isTeacherModeratorMode && (
            <div className="rounded-[18px] border border-amber-200 bg-amber-50/90 px-4 py-3 text-sm text-amber-800">
              当前为教师主持模式。您可以控制辩论流程并查看记录，学生发言入口已关闭。
            </div>
          )}
          {isStudentModeratorMode && (
            <div className="rounded-[18px] border border-emerald-200 bg-emerald-50/90 px-4 py-3 text-sm text-emerald-800">
              当前为学生主持模式。您可以控制辩论流程，同时保留自己的辩手发言入口。
            </div>
          )}

          <section className="student-card overflow-hidden p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Live Stage</p>
                <h2 className="mt-2 truncate text-2xl font-semibold tracking-[-0.03em] text-slate-950">
                  {segmentTitle || phaseLabel(currentPhase)}
                </h2>
                <p className="mt-2 text-sm text-slate-500">
                  {typeof segmentIndex === 'number'
                    ? `流程 ${segmentIndex + 1}/${effectiveFlowSegments.length}`
                    : '等待流程同步'}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:min-w-[520px]">
                <div className="rounded-[16px] border border-[#d8e7f2] bg-[#e2eef8]/80 p-3">
                  <div className="text-xs text-slate-500">正方在线</div>
                  <div className="mt-1 text-xl font-semibold text-slate-900">{humanOnlineCount}/4</div>
                </div>
                <div className="rounded-[16px] border border-[#e0d8ef] bg-[#eae6f6]/80 p-3">
                  <div className="text-xs text-slate-500">AI 状态</div>
                  <div className="mt-1 truncate text-sm font-semibold text-slate-900">{aiTurnStatusMeta?.label || '待命中'}</div>
                </div>
                <div className="rounded-[16px] border border-[#ece4da] bg-white/80 p-3">
                  <div className="text-xs text-slate-500">信号</div>
                  <div className="mt-1 text-xl font-semibold text-slate-900">{humanOnlineCount > 0 ? `${humanAvgSignal}%` : '--'}</div>
                </div>
                <div className="rounded-[16px] border border-[#f0d6c0] bg-[#f9ecde]/80 p-3">
                  <div className="text-xs text-slate-500">AI 负载</div>
                  <div className="mt-1 text-xl font-semibold text-slate-900">{aiAvgProcessing}%</div>
                </div>
              </div>
            </div>

            <div className="mt-5 h-2 overflow-hidden rounded-full bg-[#ede4da]">
              <div
                className="h-full rounded-full bg-[#171717] transition-all duration-700"
                style={{ width: `${debateProgressPercent}%` }}
              />
            </div>
          </section>

          {(currentSpeakerInfo || aiTurnStatusMeta) && (
            <section className="grid gap-4 lg:grid-cols-2">
              {currentSpeakerInfo && (
                <div className="student-card-muted flex items-center gap-4 p-4">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-emerald-50">
                    <div className="h-3 w-3 rounded-full bg-emerald-500" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Now Speaking</p>
                    <p className="mt-1 truncate font-semibold text-slate-900">
                      {currentSpeakerInfo.name} ({currentSpeakerInfo.position})
                    </p>
                  </div>
                  <Badge className={(currentSpeakerRole?.startsWith('ai_')) ? 'border-[#e0d8ef] bg-[#eae6f6] text-slate-800' : 'border-[#d8e7f2] bg-[#e2eef8] text-slate-800'}>
                    {(currentSpeakerRole?.startsWith('ai_')) ? 'AI' : '人类'}
                  </Badge>
                </div>
              )}
              {aiTurnStatusMeta && (
                <div className="student-card-muted p-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <Badge className={aiTurnStatusMeta.badgeClassName}>
                      {aiTurnStatusMeta.label}
                    </Badge>
                    <span className="text-sm text-slate-700">{aiTurnStatusMeta.detail}</span>
                  </div>
                  {aiTurnStatus === 'thinking' && aiThinkingElapsedSec >= 60 && (
                    <p className="mt-2 text-xs text-amber-700">
                      已等待 {aiThinkingElapsedSec} 秒，建议检查后端日志是否停在 AI 生成或数据库写入阶段
                    </p>
                  )}
                </div>
              )}
            </section>
          )}

          <section className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <Users className="h-6 w-6 text-slate-700" />
                  <h2 className="text-xl font-semibold text-slate-900">人类团队</h2>
                </div>
                <Badge className="student-pill">正方 · {humanStatusText}</Badge>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {humanTeam.map((participant) => {
                  const isCurrent = participant.id === currentUserId;
                  return (
                    <ParticipantVideo
                      key={participant.id}
                      participant={participant}
                      isActive={!!participant.isSpeaking}
                      isCurrentUser={isCurrent}
                      onToggleMic={isCurrent ? handleToggleMic : undefined}
                      onToggleVideo={isCurrent ? handleToggleVideo : undefined}
                    />
                  );
                })}
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <Bot className="h-6 w-6 text-slate-700" />
                  <h2 className="text-xl font-semibold text-slate-900">AI 智能团队</h2>
                </div>
                <Badge className="student-pill">反方 · {aiTurnStatusMeta?.label || '待命中'}</Badge>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {aiTeam.map((ai) => (
                  <AIAvatar
                    key={ai.id}
                    ai={ai}
                    isActive={!!ai.isSpeaking}
                  />
                ))}
              </div>
            </div>
          </section>

          <section className="student-card-muted p-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-slate-900">流程卡片</p>
                <p className="mt-1 text-xs text-slate-500">当前环节会高亮，已完成环节自动弱化。</p>
              </div>
              {canSelectCurrentUserSpeaker && (
                <Button
                  type="button"
                  size="sm"
                  variant={isCurrentUserSelectedSpeaker ? 'secondary' : 'default'}
                  disabled={isCurrentUserSelectedSpeaker}
                  onClick={handleSelectSpeaker}
                  className={isCurrentUserSelectedSpeaker ? 'student-light-button h-9 shrink-0' : 'student-dark-button h-9 shrink-0'}
                >
                  {isCurrentUserSelectedSpeaker ? '已由我回答' : '选择我来回答'}
                </Button>
              )}
            </div>
            <div className="mt-4 grid max-h-[154px] grid-cols-1 gap-2 overflow-y-auto pr-2 custom-scrollbar md:grid-cols-2">
              {effectiveFlowSegments.map((seg, idx) => {
                const active = !!segmentId && seg.id === segmentId;
                const done = typeof segmentIndex === 'number' && idx < segmentIndex;
                return (
                  <div
                    key={seg.id}
                    className={`rounded-[12px] border px-3 py-2 text-sm ${
                      active
                        ? 'border-slate-900 bg-slate-900 text-white shadow-[0_12px_28px_rgba(15,23,42,0.16)]'
                        : done
                        ? 'border-[#ece4da] bg-white/50 text-slate-400'
                        : 'border-[#ece4da] bg-white/75 text-slate-700'
                    }`}
                  >
                    {seg.title}
                  </div>
                );
              })}
            </div>
          </section>
        </main>

        <aside className="flex min-h-0 flex-col gap-4 xl:overflow-y-auto xl:pr-1 custom-scrollbar">
          <section className={`rounded-[22px] border p-5 shadow-[0_20px_46px_rgba(174,154,126,0.12)] ${
            canSpeak || canGrabMic
              ? 'border-slate-900 bg-white'
              : 'border-[#ece4da] bg-white/88 backdrop-blur'
          }`}>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Next Move</p>
            <h3 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-slate-950">
              {currentActionTitle}
            </h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {currentActionDescription}
            </p>
          </section>

          <DebateAudioControl
            isMuted={isMuted}
            isVideoOff={isVideoOff}
            canGrabMic={canGrabMic}
            showSpeakingControls={!isTeacherModeratorMode}
            micStatusText={micStatusText}
            onToggleMic={handleToggleMic}
            onToggleVideo={handleToggleVideo}
            onRequestStartRecording={handleRequestStartRecording}
            onSendAudio={handleSendAudio}
            onGrabMic={handleGrabMic}
            onEndTurn={handleEndTurn}
          />

          <DebateControls
            canSpeak={canSpeak}
            showInput={!isTeacherModeratorMode}
            onSendMessage={handleSendMessage}
            transcript={transcript}
            title="赛场发言流"
            badgeText={`${transcript.length} 条记录`}
            autoPlayEnabled={autoPlayEnabled}
            onAutoPlayEnabledChange={setAutoPlayEnabled}
            externalPlaybackLock={hasActiveLiveTtsStream}
            suppressAutoPlayEntryIds={streamedSpeechEntryIds}
            onSpeechPlaybackEvent={(payload) => sendSpeechPlaybackEvent(payload)}
          />
        </aside>
      </div>
    </div>
  );
};

export default DebateArena;
