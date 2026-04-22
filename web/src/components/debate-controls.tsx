import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  isTranscriptAudioEntry,
  getTranscriptAudioQueueKey,
  type TranscriptEntry,
} from '@/lib/debate-transcript';
import {
  audioPlaybackDebug,
  getAudioElementDebugSnapshot,
} from '@/lib/utils';
import {
  MessageSquare,
  Send
} from 'lucide-react';

interface SpeechPlaybackEventPayload {
  status: 'started' | 'finished' | 'failed';
  speechId?: string;
  segmentId?: string;
  speakerRole?: string;
  source: 'audio_element' | 'manual_audio';
}

interface DebateControlsProps {
  canSpeak?: boolean;
  onSendMessage?: (message: string) => void;
  transcript?: TranscriptEntry[];
  title?: string;
  badgeText?: string;
  showInput?: boolean;
  autoPlayEnabled?: boolean;
  onAutoPlayEnabledChange?: (enabled: boolean) => void;
  externalPlaybackLock?: boolean;
  suppressAutoPlayEntryIds?: string[];
  onSpeechPlaybackEvent?: (payload: SpeechPlaybackEventPayload) => void;
}

interface AutoPlayQueueItem {
  key: string;
  url: string;
  speechId?: string;
  segmentId?: string;
  speakerRole?: string;
}

const DebateControls: React.FC<DebateControlsProps> = ({
  canSpeak = false,
  onSendMessage,
  transcript = [],
  title = '实时记录',
  badgeText = '实时转录',
  showInput = true,
  autoPlayEnabled: controlledAutoPlayEnabled,
  onAutoPlayEnabledChange,
  externalPlaybackLock = false,
  suppressAutoPlayEntryIds = [],
  onSpeechPlaybackEvent,
}) => {
  const [newMessage, setNewMessage] = useState('');
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const [internalAutoPlayEnabled, setInternalAutoPlayEnabled] = useState(true);
  const [autoPlayQueue, setAutoPlayQueue] = useState<AutoPlayQueueItem[]>([]);
  const [currentAutoPlayItem, setCurrentAutoPlayItem] = useState<AutoPlayQueueItem | null>(null);
  const [manualPlayingId, setManualPlayingId] = useState<string | null>(null);
  const autoPlayAudioRef = useRef<HTMLAudioElement>(null);
  const visibleAudioRefs = useRef<Map<string, HTMLAudioElement>>(new Map());
  const visibleAudioRefCallbacksRef = useRef<Map<string, (element: HTMLAudioElement | null) => void>>(new Map());
  const playedAudioKeysRef = useRef<Set<string>>(new Set());
  const queuedAudioKeysRef = useRef<Set<string>>(new Set());
  const autoPlayEnabled = controlledAutoPlayEnabled ?? internalAutoPlayEnabled;

  // 自动滚动到最新消息
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  const pauseVisibleAudios = (exceptId?: string | null) => {
    // 页面上可能同时存在多个可点击的audio控件，这里统一做串行化暂停。
    visibleAudioRefs.current.forEach((audioEl, entryId) => {
      if (!audioEl) return;
      if (exceptId && entryId === exceptId) return;
      if (!audioEl.paused) {
        audioPlaybackDebug('DebateControls', '暂停可见 audio 控件', {
          entryId,
          exceptId: exceptId || null,
          audio: getAudioElementDebugSnapshot(audioEl),
        });
        audioEl.pause();
      }
    });
  };

  useEffect(() => {
    if (!autoPlayEnabled) return;
    if (externalPlaybackLock) return;
    const suppressedEntryIds = new Set(suppressAutoPlayEntryIds);
    const newQueueItems: AutoPlayQueueItem[] = [];
    for (const entry of transcript) {
      // 只有真正拿到音频URL的新消息才会进入自动播放队列，文本补丁不会重复入队。
      if (!isTranscriptAudioEntry(entry) || !entry.audioUrl) continue;
      // 流式 PCM 已经播过的消息，不再让最终整段音频自动重播。
      if (suppressedEntryIds.has(entry.id)) continue;
      const queueKey = getTranscriptAudioQueueKey(entry);
      if (!queueKey) continue;
      if (playedAudioKeysRef.current.has(queueKey)) continue;
      if (queuedAudioKeysRef.current.has(queueKey)) continue;
      if (currentAutoPlayItem?.key === queueKey) continue;
      queuedAudioKeysRef.current.add(queueKey);
      newQueueItems.push({
        key: queueKey,
        url: entry.audioUrl,
        speechId: entry.speechId,
        segmentId: entry.segmentId,
        speakerRole: entry.speakerRole,
      });
    }
    if (newQueueItems.length === 0) return;
    audioPlaybackDebug('DebateControls', '新增自动播放队列项', {
      queueKeys: newQueueItems.map((item) => item.key),
      suppressCount: suppressedEntryIds.size,
      transcriptCount: transcript.length,
    });
    setAutoPlayQueue((prev) => [...prev, ...newQueueItems]);
  }, [autoPlayEnabled, currentAutoPlayItem, externalPlaybackLock, suppressAutoPlayEntryIds, transcript]);

  useEffect(() => {
    if (!autoPlayEnabled) return;
    if (externalPlaybackLock) return;
    if (manualPlayingId) return;
    if (currentAutoPlayItem) return;
    if (autoPlayQueue.length === 0) return;
    const [nextItem, ...restItems] = autoPlayQueue;
    audioPlaybackDebug('DebateControls', '取出新的自动播放项', {
      nextKey: nextItem.key,
      remainingQueueKeys: restItems.map((item) => item.key),
      manualPlayingId,
    });
    queuedAudioKeysRef.current.delete(nextItem.key);
    setCurrentAutoPlayItem(nextItem);
    setAutoPlayQueue(restItems);
  }, [autoPlayEnabled, externalPlaybackLock, autoPlayQueue, currentAutoPlayItem, manualPlayingId]);

  useEffect(() => {
    const el = autoPlayAudioRef.current;
    if (!el) return;
    if (!autoPlayEnabled) {
      audioPlaybackDebug('DebateControls', '自动播放已关闭，清空隐藏播放器状态', {
        currentAutoPlayKey: currentAutoPlayItem?.key || null,
        queueLength: autoPlayQueue.length,
      });
      el.pause();
      el.removeAttribute('src');
      el.load();
      queuedAudioKeysRef.current.clear();
      setAutoPlayQueue([]);
      setCurrentAutoPlayItem(null);
      return;
    }
    if (externalPlaybackLock) {
      // 实时流播放期间暂停整段音频和可见audio控件，避免和流式AI播报重叠。
      el.pause();
      audioPlaybackDebug('DebateControls', '检测到流式 TTS 锁，暂停整段自动播放', {
        currentAutoPlayKey: currentAutoPlayItem?.key || null,
      });
      setCurrentAutoPlayItem(null);
      setManualPlayingId(null);
      pauseVisibleAudios();
      return;
    }
    if (!currentAutoPlayItem) return;
    // 自动播放开始前，先暂停用户手动打开的其他音频，避免双声道叠加。
    pauseVisibleAudios();
    el.src = currentAutoPlayItem.url;
    playedAudioKeysRef.current.add(currentAutoPlayItem.key);
    audioPlaybackDebug('DebateControls', '开始自动播放整段音频', {
      currentAutoPlayKey: currentAutoPlayItem.key,
      audio: getAudioElementDebugSnapshot(el),
    });
    const promise = el.play();
    if (promise && typeof (promise as Promise<void>).catch === 'function') {
      (promise as Promise<void>).catch(() => {});
    }
  }, [autoPlayEnabled, currentAutoPlayItem, externalPlaybackLock]);

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  };

  const handleSendMessage = () => {
    if (!canSpeak) {
      return;
    }
    if (newMessage.trim()) {
      const msg = newMessage.trim();
      setNewMessage('');
      onSendMessage?.(msg);
    }
  };

  const emitSpeechPlaybackEvent = (
    payload: Omit<SpeechPlaybackEventPayload, 'source'> & {
      source: SpeechPlaybackEventPayload['source'];
    }
  ) => {
    if (!payload.speechId) {
      return;
    }
    onSpeechPlaybackEvent?.(payload);
  };

  const registerVisibleAudio = (entryId: string, element: HTMLAudioElement | null) => {
    if (element) {
      audioPlaybackDebug('DebateControls', '注册可见 audio 控件', {
        entryId,
        audio: getAudioElementDebugSnapshot(element),
      });
      visibleAudioRefs.current.set(entryId, element);
      return;
    }
    audioPlaybackDebug('DebateControls', '移除可见 audio 控件', {
      entryId,
    });
    visibleAudioRefs.current.delete(entryId);
  };

  const getVisibleAudioRef = (entryId: string) => {
    const existingCallback = visibleAudioRefCallbacksRef.current.get(entryId);
    if (existingCallback) {
      return existingCallback;
    }

    // 这里缓存稳定的 ref 回调，避免父组件每次重渲染都让 React 先卸载旧 ref、再挂载新 ref。
    const stableCallback = (element: HTMLAudioElement | null) => {
      registerVisibleAudio(entryId, element);
    };
    visibleAudioRefCallbacksRef.current.set(entryId, stableCallback);
    return stableCallback;
  };

  useEffect(() => {
    const activeEntryIds = new Set(
      transcript
        .filter((entry) => isTranscriptAudioEntry(entry) && !!entry.audioUrl)
        .map((entry) => entry.id)
    );

    // 音频消息已经从转录列表里移除后，对应的 ref 回调也一起清理，避免长期累积无效条目。
    visibleAudioRefCallbacksRef.current.forEach((_, entryId) => {
      if (!activeEntryIds.has(entryId)) {
        visibleAudioRefCallbacksRef.current.delete(entryId);
      }
    });
  }, [transcript]);

  const handleVisibleAudioPlay = (entry: TranscriptEntry) => {
    const entryId = entry.id;
    if (externalPlaybackLock) {
      audioPlaybackDebug('DebateControls', '手动点播被流式 TTS 锁拦截', {
        entryId,
      });
      visibleAudioRefs.current.get(entryId)?.pause();
      return;
    }
    // 手动播放某条音频时，立即暂停自动播放和其他手动音频，避免双声道叠加。
    setManualPlayingId(entryId);
    audioPlaybackDebug('DebateControls', '用户手动播放可见音频', {
      entryId,
      currentAutoPlayKey: currentAutoPlayItem?.key || null,
      audio: getAudioElementDebugSnapshot(visibleAudioRefs.current.get(entryId)),
    });
    if (autoPlayAudioRef.current && !autoPlayAudioRef.current.paused) {
      autoPlayAudioRef.current.pause();
      setCurrentAutoPlayItem(null);
    }
    pauseVisibleAudios(entryId);
    emitSpeechPlaybackEvent({
      status: 'started',
      speechId: entry.speechId,
      segmentId: entry.segmentId,
      speakerRole: entry.speakerRole,
      source: 'manual_audio',
    });
  };

  const handleVisibleAudioStop = (entryId: string) => {
    audioPlaybackDebug('DebateControls', '可见音频停止播放', {
      entryId,
      audio: getAudioElementDebugSnapshot(visibleAudioRefs.current.get(entryId)),
    });
    setManualPlayingId((current) => (current === entryId ? null : current));
  };

  const handleToggleAutoPlay = () => {
    const nextEnabled = !autoPlayEnabled;
    // 自动播放开关可能由父组件统一托管，这里同时兼容受控和非受控两种用法。
    if (controlledAutoPlayEnabled === undefined) {
      setInternalAutoPlayEnabled(nextEnabled);
    }
    onAutoPlayEnabledChange?.(nextEnabled);
  };

  return (
    <div className="bg-slate-900/95 backdrop-blur-lg border-t border-slate-700/50">
      <div className="max-w-7xl mx-auto p-4">
        <Card className="bg-slate-800/50 border-slate-700">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-white font-medium flex items-center gap-2">
                <MessageSquare className="w-4 h-4" />
                {title}
              </h3>
              <div className="flex items-center gap-2">
                <Badge className="bg-emerald-600/30 text-emerald-300 border-emerald-600/50">
                  {badgeText}
                </Badge>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleToggleAutoPlay}
                  className="h-6 px-2 text-xs border-slate-600 text-slate-200 hover:text-white hover:bg-slate-700"
                >
                  自动播放：{autoPlayEnabled ? '开' : '关'}
                </Button>
                {externalPlaybackLock && (
                  <Badge className="bg-amber-600/30 text-amber-200 border-amber-600/50">
                    AI流式播报中
                  </Badge>
                )}
              </div>
            </div>

            {/* 字幕滚动区域 */}
            <ScrollArea className="h-60 bg-slate-900/50 rounded-lg p-3">
              <div className="space-y-4">
                {transcript.map((entry) => (
                  <div key={entry.id} className="flex items-start gap-3 group">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`font-medium text-sm ${
                          entry.isAI ? 'text-purple-400' : 'text-blue-400'
                        }`}>
                          {entry.speaker}
                        </span>
                        <Badge variant="outline" className="text-xs border-slate-600 text-slate-400">
                          {entry.position}
                        </Badge>
                        <span className="text-xs text-slate-500">
                          {formatTime(entry.timestamp)}
                        </span>
                      </div>
                      <p className="text-slate-300 text-sm leading-relaxed">
                        {entry.message}
                      </p>
                      {isTranscriptAudioEntry(entry) && entry.audioUrl && (
                        <div className="mt-2 max-w-md">
                          <audio 
                            ref={getVisibleAudioRef(entry.id)}
                            controls 
                            preload="metadata" 
                            src={entry.audioUrl} 
                            onPlay={() => handleVisibleAudioPlay(entry)}
                            onPause={() => handleVisibleAudioStop(entry.id)}
                            onEnded={() => {
                              emitSpeechPlaybackEvent({
                                status: 'finished',
                                speechId: entry.speechId,
                                segmentId: entry.segmentId,
                                speakerRole: entry.speakerRole,
                                source: 'manual_audio',
                              });
                              handleVisibleAudioStop(entry.id);
                            }}
                            onError={() => {
                              emitSpeechPlaybackEvent({
                                status: 'failed',
                                speechId: entry.speechId,
                                segmentId: entry.segmentId,
                                speakerRole: entry.speakerRole,
                                source: 'manual_audio',
                              });
                              handleVisibleAudioStop(entry.id);
                            }}
                            className="w-full h-8 rounded opacity-90 hover:opacity-100 transition-opacity" 
                          />
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                <audio
                  ref={autoPlayAudioRef}
                  onEnded={() => {
                    audioPlaybackDebug('DebateControls', '隐藏自动播放器播放结束', {
                      currentAutoPlayKey: currentAutoPlayItem?.key || null,
                      audio: getAudioElementDebugSnapshot(autoPlayAudioRef.current),
                    });
                    emitSpeechPlaybackEvent({
                      status: 'finished',
                      speechId: currentAutoPlayItem?.speechId,
                      segmentId: currentAutoPlayItem?.segmentId,
                      speakerRole: currentAutoPlayItem?.speakerRole,
                      source: 'audio_element',
                    });
                    setCurrentAutoPlayItem(null);
                  }}
                  onError={() => {
                    audioPlaybackDebug('DebateControls', '隐藏自动播放器播放失败', {
                      currentAutoPlayKey: currentAutoPlayItem?.key || null,
                      audio: getAudioElementDebugSnapshot(autoPlayAudioRef.current),
                    });
                    emitSpeechPlaybackEvent({
                      status: 'failed',
                      speechId: currentAutoPlayItem?.speechId,
                      segmentId: currentAutoPlayItem?.segmentId,
                      speakerRole: currentAutoPlayItem?.speakerRole,
                      source: 'audio_element',
                    });
                    setCurrentAutoPlayItem(null);
                  }}
                  onPlay={() => {
                    audioPlaybackDebug('DebateControls', '隐藏自动播放器开始播放', {
                      currentAutoPlayKey: currentAutoPlayItem?.key || null,
                      audio: getAudioElementDebugSnapshot(autoPlayAudioRef.current),
                    });
                    pauseVisibleAudios();
                    emitSpeechPlaybackEvent({
                      status: 'started',
                      speechId: currentAutoPlayItem?.speechId,
                      segmentId: currentAutoPlayItem?.segmentId,
                      speakerRole: currentAutoPlayItem?.speakerRole,
                      source: 'audio_element',
                    });
                  }}
                  preload="auto"
                  className="hidden"
                />
              </div>
            </ScrollArea>


            {/* 发送消息输入框 */}
            {showInput && (
              <div className="mt-3 flex gap-2">
                <input
                  type="text"
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                  placeholder="输入您的观点或反驳..."
                  className="flex-1 px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  disabled={!canSpeak}
                />
                <Button
                  onClick={handleSendMessage}
                  disabled={!canSpeak || !newMessage.trim()}
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                >
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default DebateControls;
