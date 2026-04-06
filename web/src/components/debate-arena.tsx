import React, { useState, useEffect, useRef } from 'react';
import DebateHeader from './debate-header';
import ParticipantVideo, { Participant } from './participant-video';
import AIAvatar, { AIAvatar as AIAvatarType } from './ai-avatar';
import DebateControls from './debate-controls';
import DebateAudioControl from './debate-audio-control';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useWebSocket } from '@/hooks/use-websocket';
import { useAuth } from '@/store/auth.context';
import { useToast } from '@/hooks/use-toast';
import StudentService from '@/services/student.service';
import {
  TRANSCRIPT_PENDING_TEXT,
  type TranscriptEntry,
  buildTranscriptSpeechEntryId,
  normalizeTranscriptEntry,
  upsertTranscriptEntry,
} from '@/lib/debate-transcript';
import { audioPlaybackDebug } from '@/lib/utils';
import PcmStreamPlayer from '@/lib/pcm-stream-player';
import {
  ArrowLeft,
  Settings,
  Users,
  Bot,
  Trophy,
  Zap,
  Shield,
  Target,
  AlertCircle,
  Loader2,
  Radio
} from 'lucide-react';

interface DebateArenaProps {
  roomId?: string;
  onBack?: () => void;
  onEndDebate?: () => void;
}

const DebateArena: React.FC<DebateArenaProps> = ({ roomId = '', onBack, onEndDebate }) => {
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
  const [segmentTitle, setSegmentTitle] = useState<string | null>(null);
  const [segmentId, setSegmentId] = useState<string | null>(null);
  const [segmentIndex, setSegmentIndex] = useState<number | null>(null);
  const [participants, setParticipants] = useState<any[]>([]);
  const [aiDebaters, setAiDebaters] = useState<any[]>([]);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [autoPlayEnabled, setAutoPlayEnabled] = useState(true);
  const [hasActiveLiveTtsStream, setHasActiveLiveTtsStream] = useState(false);
  const [streamedSpeechEntryIds, setStreamedSpeechEntryIds] = useState<string[]>([]);
  const [assignedParticipants, setAssignedParticipants] = useState<Array<{
    user_id: string;
    name: string;
    role: string;
    role_reason?: string | null;
    overall_score?: number;
  }>>([]);
  const [isProcessingReport, setIsProcessingReport] = useState(false);

  const recordingPermissionWaiters = useRef<Map<string, { resolve: (result: { allowed: boolean; message?: string }) => void; timeoutId: number }>>(new Map());
  const liveTtsPlayerRef = useRef<PcmStreamPlayer | null>(null);
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

  // WebSocket连接
  const { isConnected, send, on, off } = useWebSocket(roomId, {
    onConnect: () => {
      console.log('Connected to debate room');
      setError(null);
    },
    onDisconnect: () => {
      console.log('Disconnected from debate room');
    },
    onError: (err) => {
      console.error('WebSocket error:', err);
      setError('连接失败，请检查网络');
    }
  });

  useEffect(() => {
    liveTtsPlayerRef.current = new PcmStreamPlayer({
      onPlaybackStateChange: (isPlaying) => {
        audioPlaybackDebug('DebateArena', '流式 TTS 播放状态变更', {
          roomId,
          isPlaying,
        });
        setHasActiveLiveTtsStream(isPlaying);
      },
    });

    return () => {
      liveTtsPlayerRef.current?.dispose();
      liveTtsPlayerRef.current = null;
    };
  }, []);

  useEffect(() => {
    // 切换房间时清空流式播报标记，避免上一场辩论残留到当前房间。
    setStreamedSpeechEntryIds([]);
    ignoredLiveTtsSpeechIdsRef.current.clear();
    ttsStreamStartCountRef.current.clear();
    ttsStreamChunkCountRef.current.clear();
    ttsStreamEndCountRef.current.clear();
    audioPlaybackDebug('DebateArena', '房间切换，已清空音频排查计数器', { roomId });
  }, [roomId]);

  const debateTopic = '辩论进行中';
  const phases = ['立论陈词', '攻辩环节', '自由辩论', '总结陈词'];
  const currentUserId = user?.id || '';
  const currentUserRole = participants.find((p) => p.user_id === currentUserId)?.role || null;

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
    if (autoPlayEnabled) {
      return;
    }

    // 用户关闭自动播放后，立刻停止当前流式 TTS，避免 AI 继续自动出声。
    audioPlaybackDebug('DebateArena', '自动播放已关闭，停止当前流式 TTS', {
      roomId,
    });
    liveTtsPlayerRef.current?.stop();
  }, [autoPlayEnabled, roomId]);

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
    
    let base = (((import.meta as any).env?.VITE_API_BASE_URL as string | undefined) || '').replace(/\/+$/, '');
    
    // 如果是上传文件，通常挂载在根目录下的 /uploads
    // 如果 base 包含 /api/v1，需要去除，指向根目录
    if (trimmed.startsWith('/uploads') || trimmed.startsWith('uploads/')) {
       base = base.replace(/\/api\/v1$/, '').replace(/\/api$/, '');
    }

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
    const handleStateUpdate = (data: any) => {
      console.log('State update:', data);
      const currentUserRoleFromState = Array.isArray(data.participants)
        ? data.participants.find((participant: any) => participant?.user_id === currentUserIdRef.current)?.role || currentUserRoleRef.current
        : currentUserRoleRef.current;
      if (data.current_speaker !== undefined) {
        setCurrentSpeakerRole(data.current_speaker);
        // 如果轮到当前用户发言，自动取消静音
        if (currentUserRoleFromState && roleMatches(currentUserRoleFromState, data.current_speaker)) {
          setIsMuted(false);
          console.log('轮到当前用户发言，自动取消静音');
        }
      }
      if (data.current_phase) setCurrentPhase(data.current_phase);
      if (typeof data.time_remaining === 'number') setTimeRemaining(data.time_remaining);
      if (data.segment_title) setSegmentTitle(data.segment_title);
      if (data.segment_id !== undefined) setSegmentId(data.segment_id);
      if (typeof data.segment_index === 'number') setSegmentIndex(data.segment_index);
      if (data.speaker_mode !== undefined) setSpeakerMode(data.speaker_mode);
      if (Array.isArray(data.speaker_options)) setSpeakerOptions(data.speaker_options);
      if (data.mic_owner_user_id !== undefined) setMicOwnerUserId(data.mic_owner_user_id);
      if (data.mic_owner_role !== undefined) setMicOwnerRole(data.mic_owner_role);
      if (data.mic_expires_at !== undefined) setMicExpiresAt(data.mic_expires_at);
      if (Array.isArray(data.participants)) setParticipants(data.participants);
      if (Array.isArray(data.ai_debaters)) setAiDebaters(data.ai_debaters);
    };

    // 监听用户加入事件
    const handleUserJoined = (data: any) => {
      console.log('User joined:', data);
      if (!data.user_id || !data.name || !data.role) return;
      // 使用函数式更新基于最新 participants 去重，避免旧闭包导致同一用户被重复插入。
      setParticipants(prev => {
        const exists = prev.some((participant) => participant.user_id === data.user_id);
        if (exists) return prev;
        return [...prev, {
          user_id: data.user_id,
          name: data.name,
          role: data.role,
          stance: data.stance
        }];
      });
    };

    // 监听用户离开事件
    const handleUserLeft = (data: any) => {
      console.log('User left:', data);
      if (data.user_id) {
        // 从participants列表中移除用户
        setParticipants(prev => prev.filter(p => p.user_id !== data.user_id));
      }
    };

    // 监听阶段变化
    const handlePhaseChange = (data: any) => {
      console.log('Phase change:', data);
      if (data.phase) setCurrentPhase(data.phase);
    };

    const handleSegmentChange = (data: any) => {
      if (data.segment_title) setSegmentTitle(data.segment_title);
      if (data.segment_id !== undefined) setSegmentId(data.segment_id);
      if (typeof data.segment_index === 'number') setSegmentIndex(data.segment_index);
      if (data.speaker_mode !== undefined) setSpeakerMode(data.speaker_mode);
      if (Array.isArray(data.speaker_options)) setSpeakerOptions(data.speaker_options);
      if (data.phase) setCurrentPhase(data.phase);
    };

    // 监听计时器更新
    const handleTimerUpdate = (data: any) => {
      console.log('Timer update:', data);
      if (typeof data.time_remaining === 'number') {
        setTimeRemaining(data.time_remaining);
      }
    };

    // 监听字幕
    const handleSubtitle = (data: any) => {
      console.log('Subtitle:', data);
      setSubtitle(data.text || '');
      // 5秒后清除字幕
      setTimeout(() => setSubtitle(''), 5000);
    };

    // 监听发言
    const handleSpeech = (data: any) => {
      console.log('Speech:', data);
      audioPlaybackDebug('DebateArena', '收到 speech 事件', {
        roomId,
        speechId: String(data?.speech_id || data?.message_id || data?.id || ''),
        role: data?.role,
        hasAudioUrl: !!(data?.audio_url || data?.file_url || data?.url),
        contentLength: String(data?.content || data?.text || '').length,
      });
      if (data.role) setCurrentSpeakerRole(data.role);

      // 使用可回填的转录合并工具，兼容“音频先到文本后补”和“文本先到音频后补”。
      const entry = normalizeTranscriptEntry(data, {
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
        speechId: String(data?.speech_id || data?.message_id || data?.id || ''),
        hasAudioUrl: !!entry.audioUrl,
        isPendingText: !!entry.isPendingText,
      });
      setSubtitle(`${entry.speaker}：${entry.message}`);
      setTimeout(() => setSubtitle(''), 5000);
    };

    const handleTtsStreamStart = (data: any) => {
      const speechId = String(data?.speech_id || data?.message_id || '').trim();
      if (!speechId) return;
      const startCount = increaseStreamEventCount(ttsStreamStartCountRef, speechId);
      const transcriptEntryId = buildTranscriptSpeechEntryId(speechId);
      if (!autoPlayEnabledRef.current) {
        // 自动播放关闭时，整条流式 TTS 都应静默跳过，直到收到 end 事件再清理忽略标记。
        ignoredLiveTtsSpeechIdsRef.current.add(speechId);
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

    const handleTtsStreamChunk = (data: any) => {
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

    const handleTtsStreamEnd = (data: any) => {
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


    const handlePermissionDenied = (data: any) => {
      toastRef.current({
        title: '无法发言',
        description: data?.message || '当前无发言权限',
        variant: 'destructive',
      });
    };

    const handleMicGrabbed = (data: any) => {
      if (data.user_id !== undefined) setMicOwnerUserId(data.user_id);
      if (data.role !== undefined) setMicOwnerRole(data.role);
      if (data.expires_at !== undefined) setMicExpiresAt(data.expires_at);
      if (data.role) setCurrentSpeakerRole(data.role);
      // 自由辩论阶段：当前用户抢到麦时，自动取消静音，允许发言
      if (data.user_id === currentUserIdRef.current) {
        setIsMuted(false);
        console.log('当前用户抢麦成功，自动取消静音');
      }
    };

    const handleMicReleased = () => {
      setMicOwnerUserId(null);
      setMicOwnerRole(null);
      setMicExpiresAt(null);
      if (speakerModeRef.current === 'free') setCurrentSpeakerRole(null);
    };

    // 监听错误
    const handleError = (data: any) => {
      console.error('WebSocket error:', data);
      setError(data.message || '发生错误');
    };

    const handleDebateProcessing = (data: any) => {
      console.log('Debate processing:', data);
      setIsProcessingReport(true);
      toastRef.current({
        title: '辩论已结束',
        description: data?.message || '正在生成辩论报告和评分，请稍候...',
        duration: 10000, 
      });
    };

    const handleDebateEnded = (data: any) => {
      setIsProcessingReport(false);
      toastRef.current({
        title: '报告生成完成',
        description: data?.timestamp ? `结束时间：${data.timestamp}` : undefined,
      });
      setCurrentPhase('finished');
      onEndDebateRef.current?.();
    };

    const handleRecordingPermission = (data: any) => {
      const requestId = data?.request_id;
      if (!requestId) return;
      const waiter = recordingPermissionWaiters.current.get(String(requestId));
      if (!waiter) return;
      clearTimeout(waiter.timeoutId);
      recordingPermissionWaiters.current.delete(String(requestId));
      waiter.resolve({ allowed: !!data.allowed, message: data.message });
    };

    // 注册事件监听器
    audioPlaybackDebug('DebateArena', '开始注册房间 websocket 监听', { roomId });
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
    on('permission_denied', handlePermissionDenied);
    on('mic_grabbed', handleMicGrabbed);
    on('mic_released', handleMicReleased);
    on('debate_processing', handleDebateProcessing);
    on('debate_ended', handleDebateEnded);
    on('error', handleError);

    // 清理函数
    return () => {
      audioPlaybackDebug('DebateArena', '开始清理房间 websocket 监听', { roomId });
      off('state_update', handleStateUpdate);
      off('user_joined', handleUserJoined);
      off('user_left', handleUserLeft);
      off('phase_change', handlePhaseChange);
      off('segment_change', handleSegmentChange);
      off('timer_update', handleTimerUpdate);
      off('subtitle', handleSubtitle);
      off('recording_permission', handleRecordingPermission);
      off('speech', handleSpeech);
      off('tts_stream_start', handleTtsStreamStart);
      off('tts_stream_chunk', handleTtsStreamChunk);
      off('tts_stream_end', handleTtsStreamEnd);
      off('permission_denied', handlePermissionDenied);
      off('mic_grabbed', handleMicGrabbed);
      off('mic_released', handleMicReleased);
      off('debate_processing', handleDebateProcessing);
      off('debate_ended', handleDebateEnded);
      off('error', handleError);
    };
  }, [on, off]);

  useEffect(() => {
    const load = async () => {
      if (!roomId) return;
      try {
        const data = await StudentService.getDebateParticipants(roomId);
        setAssignedParticipants(Array.isArray(data) ? data : []);
      } catch {
        setAssignedParticipants([]);
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
    if (isConnected) {
      send('speech', { content: message });
    }
  };

  const handleSendAudio = (audioBlob: Blob) => {
    if (isConnected) {
      const reader = new FileReader();
      reader.onloadend = () => {
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
        send('audio', { audio_data: raw, audio_format: format });
      };
      reader.readAsDataURL(audioBlob);
    }
  };

  const requestRecordingPermission = async (): Promise<{ allowed: boolean; message?: string }> => {
    if (!isConnected) {
      return { allowed: false, message: '未连接到辩论房间，请稍后重试' };
    }
    const requestId =
      (globalThis.crypto as any)?.randomUUID?.() ||
      `${Date.now()}-${Math.random().toString(16).slice(2)}`;
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
    if (isConnected) {
      send('grab_mic', {});
    }
  };

  const handleEndTurn = () => {
    if (isConnected) {
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
    if (isConnected) {
      send('start_debate', {});
    }
  };

  const handleAdvanceSegment = () => {
    if (isConnected) {
      send('advance_segment', {});
    }
  };

  const handleEndDebate = () => {
    if (isConnected) {
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
  
  // 检查麦克风是否处于活跃状态（未过期）
  const micActive = !!micOwnerUserId && !!micExpiresAt && new Date(micExpiresAt).getTime() > Date.now();
  
  // 调试日志
  if (isFreeDebate && micOwnerUserId) {
    console.log('抢麦状态检查:', {
      micOwnerUserId,
      currentUserId,
      micExpiresAt,
      micActive,
      expiresTime: micExpiresAt ? new Date(micExpiresAt).getTime() : null,
      nowTime: Date.now(),
      isOwner: micOwnerUserId === currentUserId
    });
  }
  
  const canSpeak = isFreeDebate
    ? micOwnerUserId === currentUserId && micActive
    : !!currentUserRole && roleMatches(currentUserRole, currentSpeakerRole);
  const canGrabMic = isFreeDebate && !micActive;
  const canSelectSelf =
    speakerMode === 'choice' &&
    !!currentUserRole &&
    speakerOptions.some((opt) => roleMatches(currentUserRole, opt)) &&
    !roleMatches(currentUserRole, currentSpeakerRole);
  const micStatusText = isFreeDebate
    ? micActive
      ? `当前持麦：${micOwnerRole || ''}${micOwnerUserId === currentUserId ? '（你）' : ''}`
      : '当前无人持麦'
    : segmentTitle || undefined;
  const isDebater1 = currentUserRole === 'debater_1';
  const canStartDebate = isConnected && isDebater1 && currentPhase === 'waiting';

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
  const lastSegmentId = flowSegments[flowSegments.length - 1]?.id;
  const isLastSegment =
    (!!lastSegmentId && segmentId === lastSegmentId) ||
    (typeof segmentIndex === 'number' && segmentIndex === flowSegments.length - 1);

  const hasDebater4Online = participants.some((p) => roleMatches('debater_4', p?.role));
  const canAdvanceSegment = isConnected && isDebater1 && currentPhase !== 'waiting' && currentPhase !== 'finished' && !isLastSegment;
  const canEndDebate =
    isConnected &&
    isDebater1 &&
    currentPhase !== 'waiting' &&
    currentPhase !== 'finished' &&
    (isLastSegment ||
      (currentPhase === 'closing' && segmentId === 'closing_negative_4' && !hasDebater4Online));
  const humanOnlineMembers = humanTeam.filter((m) => typeof m.signalStrength === 'number' && (m.signalStrength || 0) > 0);
  const humanOnlineCount = humanOnlineMembers.length;
  const humanAvgSignal = humanOnlineCount > 0 ? Math.round(humanOnlineMembers.reduce((sum, m) => sum + (m.signalStrength || 0), 0) / humanOnlineCount) : 0;
  const humanStatusText = humanOnlineCount === 0 ? '等待加入' : humanOnlineCount === 4 ? '在线活跃' : `在线 ${humanOnlineCount}/4`;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-purple-900 flex flex-col">
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
      {!isConnected && (
        <div className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50">
          <Alert className="bg-amber-100 border-amber-300">
            <Loader2 className="h-4 w-4 animate-spin text-amber-600" />
            <AlertDescription className="text-amber-800">正在连接到辩论房间...</AlertDescription>
          </Alert>
        </div>
      )}

      {/* 实时字幕 */}
      {subtitle && (
        <div className="fixed bottom-32 left-1/2 transform -translate-x-1/2 z-50 max-w-2xl">
          <div className="bg-black/80 text-white px-6 py-3 rounded-lg text-center">
            {subtitle}
          </div>
        </div>
      )}

      {/* 报告生成中遮罩层 */}
      {isProcessingReport && (
        <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex flex-col items-center justify-center">
          <div className="bg-slate-800 p-8 rounded-xl border border-slate-700 shadow-2xl flex flex-col items-center max-w-md text-center">
            <Loader2 className="h-12 w-12 text-blue-500 animate-spin mb-4" />
            <h3 className="text-xl font-bold text-white mb-2">正在生成辩论报告</h3>
            <p className="text-slate-400">
              AI裁判正在对整场辩论进行深度分析和评分...
            </p>
            <p className="text-slate-500 text-sm mt-4">
              这可能需要几十秒的时间，请勿关闭页面
            </p>
          </div>
        </div>
      )}

      {/* 抢麦成功提示 - 显眼的位置 */}
      {isFreeDebate && micActive && (
        <div className="fixed top-24 left-1/2 transform -translate-x-1/2 z-50">
          <Alert className="bg-purple-100 border-purple-400 shadow-2xl animate-pulse">
            <Radio className="h-5 w-5 text-purple-600" />
            <AlertDescription className="text-purple-900 font-bold text-lg">
              {micOwnerUserId === currentUserId ? (
                <span className="flex items-center gap-2">
                  <span className="inline-block w-3 h-3 bg-purple-600 rounded-full animate-ping"></span>
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
        onFullscreen={() => console.log('Fullscreen')}
        onSettings={() => console.log('Settings')}
      />

      <div className="flex-1 flex overflow-hidden">
        {/* 左侧控制栏 */}
        <div className="flex-none z-20">
          <DebateAudioControl
            isMuted={isMuted}
            isVideoOff={isVideoOff}
            canGrabMic={canGrabMic}
            micStatusText={micStatusText}
            onToggleMic={handleToggleMic}
            onToggleVideo={handleToggleVideo}
            onRequestStartRecording={handleRequestStartRecording}
            onSendAudio={handleSendAudio}
            onGrabMic={handleGrabMic}
            onEndTurn={handleEndTurn}
          />
        </div>

        {/* 主内容区域 */}
        <div className="flex-1 flex flex-col h-full overflow-y-auto custom-scrollbar">
          <div className="max-w-7xl mx-auto w-full px-6 pt-4">
            <div className="bg-slate-800/40 border border-slate-700 rounded-lg p-4">
              <div className="flex items-center justify-between gap-4">
                <div className="text-sm text-slate-200">
                  <span className="text-slate-400">当前环节：</span>
                  <span className="font-medium">{segmentTitle || phaseLabel(currentPhase)}</span>
                  {typeof segmentIndex === 'number' && (
                    <span className="text-slate-500 ml-2">({segmentIndex + 1}/{flowSegments.length})</span>
                  )}
                </div>
              </div>
              <div className="mt-3 max-h-[120px] overflow-y-auto grid grid-cols-1 md:grid-cols-2 gap-2 pr-2 custom-scrollbar">
                {flowSegments.map((seg, idx) => {
                  const active = !!segmentId && seg.id === segmentId;
                  const done = typeof segmentIndex === 'number' && idx < segmentIndex;
                  return (
                    <div
                      key={seg.id}
                      className={`px-3 py-2 rounded border text-sm ${
                        active
                          ? 'bg-blue-600/20 border-blue-500 text-white'
                          : done
                          ? 'bg-slate-900/30 border-slate-700 text-slate-400'
                          : 'bg-slate-900/10 border-slate-700 text-slate-300'
                      }`}
                    >
                      {seg.title}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* 主对战区域 */}
          <div className="flex-1 flex items-center justify-center p-6">
            <div className="w-full max-w-7xl">
              {/* 当前发言者提示 */}
              {currentSpeakerInfo && (
                <div className="mb-6 text-center">
                  <div className="inline-flex items-center gap-3 px-6 py-3 bg-slate-800/80 backdrop-blur rounded-full border border-slate-600">
                    <div className="w-3 h-3 bg-emerald-500 rounded-full animate-pulse" />
                    <span className="text-white font-medium">
                      {currentSpeakerInfo.name} ({currentSpeakerInfo.position}) 正在发言
                    </span>
                    <Badge className={
                      (currentSpeakerRole?.startsWith('ai_'))
                        ? 'bg-purple-600/30 text-purple-300 border-purple-600/50'
                        : 'bg-blue-600/30 text-blue-300 border-blue-600/50'
                    }>
                      {(currentSpeakerRole?.startsWith('ai_')) ? 'AI' : '人类'}
                    </Badge>
                  </div>
                </div>
              )}

              {/* 对战区域 */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* 左侧：人类团队 */}
                <div className="space-y-4">
                  <div className="flex items-center gap-3 mb-4">
                <Users className="w-6 h-6 text-blue-400" />
                <h2 className="text-xl font-bold text-white">人类团队</h2>
                <Badge className="bg-blue-600/30 text-blue-300 border-blue-600/50">
                  正方
                </Badge>
              </div>

              <div className="grid grid-cols-2 gap-4">
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

              {/* 团队统计 */}
              <div className="mt-4 p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-400">团队信号强度</span>
                  <span className="text-emerald-400 font-medium">
                    {humanOnlineCount > 0 ? `${humanAvgSignal}%` : '--'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm mt-2">
                  <span className="text-slate-400">团队状态</span>
                  <span className="text-blue-400 font-medium">{humanStatusText}</span>
                </div>
              </div>
            </div>

            {/* 右侧：AI团队 */}
            <div className="space-y-4">
              <div className="flex items-center gap-3 mb-4">
                <Bot className="w-6 h-6 text-purple-400" />
                <h2 className="text-xl font-bold text-white">AI智能团队</h2>
                <Badge className="bg-purple-600/30 text-purple-300 border-purple-600/50">
                  反方
                </Badge>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {aiTeam.map((ai) => (
                  <AIAvatar
                    key={ai.id}
                    ai={ai}
                    isActive={!!ai.isSpeaking}
                  />
                ))}
              </div>

              {/* AI团队统计 */}
              <div className="mt-4 p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-400">AI处理能力</span>
                  <span className="text-emerald-400 font-medium">
                    {Math.round(aiTeam.reduce((sum, m) => sum + (m.processingPower || 0), 0) / aiTeam.length)}%
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm mt-2">
                  <span className="text-slate-400">AI策略状态</span>
                  <span className="text-purple-400 font-medium">自适应优化中</span>
                </div>
              </div>
            </div>
          </div>

          {/* 对战统计信息 */}
          <div className="mt-8 grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 bg-slate-800/50 rounded-lg border border-slate-700">
              <Users className="w-8 h-8 text-blue-400 mx-auto mb-2" />
              <div className="text-2xl font-bold text-white">4</div>
              <div className="text-sm text-slate-400">人类参与者</div>
            </div>
            <div className="text-center p-4 bg-slate-800/50 rounded-lg border border-slate-700">
              <Bot className="w-8 h-8 text-purple-400 mx-auto mb-2" />
              <div className="text-2xl font-bold text-white">4</div>
              <div className="text-sm text-slate-400">AI 智能体</div>
            </div>
            <div className="text-center p-4 bg-slate-800/50 rounded-lg border border-slate-700">
              <Target className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
              <div className="text-2xl font-bold text-white">92%</div>
              <div className="text-sm text-slate-400">匹配度</div>
            </div>
            <div className="text-center p-4 bg-slate-800/50 rounded-lg border border-slate-700">
              <Trophy className="w-8 h-8 text-amber-400 mx-auto mb-2" />
              <div className="text-2xl font-bold text-white">A+</div>
              <div className="text-sm text-slate-400">对抗等级</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  {/* 底部控制区域 */}
  <DebateControls
    canSpeak={canSpeak}
    onSendMessage={handleSendMessage}
    transcript={transcript}
    autoPlayEnabled={autoPlayEnabled}
    onAutoPlayEnabledChange={setAutoPlayEnabled}
    externalPlaybackLock={hasActiveLiveTtsStream}
    suppressAutoPlayEntryIds={streamedSpeechEntryIds}
  />
</div>
  );
};

export default DebateArena;
