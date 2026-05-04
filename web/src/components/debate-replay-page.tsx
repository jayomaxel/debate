import React, { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import ParticipantVideo, { Participant } from './participant-video';
import AIAvatar, { AIAvatar as AIAvatarType } from './ai-avatar';
import DebateControls from './debate-controls';
import StudentService, { type DebateDetails, type DebateParticipant } from '@/services/student.service';
import { getApiOriginBaseUrl } from '@/lib/runtime-url';
import { AlertCircle, ArrowLeft, Bot, Loader2, Users } from 'lucide-react';

interface DebateReplayPageProps {
  debateId: string;
  onBack?: () => void;
}

type TranscriptEntry = {
  id: string;
  speaker: string;
  position: string;
  message: string;
  timestamp: Date;
  isAI?: boolean;
  audioUrl?: string;
  audioFormat?: string;
};

const normalizeRole = (role: unknown) => String(role ?? '').trim();

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

  if (!base) return trimmed;
  if (trimmed.startsWith('/')) return `${base}${trimmed}`;
  return `${base}/${trimmed}`;
};

const DebateReplayPage: React.FC<DebateReplayPageProps> = ({ debateId, onBack }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [details, setDetails] = useState<DebateDetails | null>(null);
  const [participants, setParticipants] = useState<DebateParticipant[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const loadedDetails = await StudentService.getDebateDetails(debateId);
        if (cancelled) return;
        setDetails(loadedDetails);

        const rosterFromHistory = loadedDetails.debate?.participants;
        if (Array.isArray(rosterFromHistory) && rosterFromHistory.length > 0) {
          setParticipants(rosterFromHistory);
          return;
        }

        try {
          const loadedParticipants = await StudentService.getDebateParticipants(debateId);
          if (!cancelled) {
            setParticipants(Array.isArray(loadedParticipants) ? loadedParticipants : []);
          }
        } catch (participantsError) {
          console.warn('[DebateReplayPage] Failed to load live participants, continue with history details:', participantsError);
          if (!cancelled) {
            setParticipants([]);
          }
        }
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.message || '加载回放失败，请稍后重试');
        setDetails(null);
        setParticipants([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [debateId]);

  const participantByUserId = useMemo(() => {
    const map = new Map<string, DebateParticipant>();
    for (const p of participants) {
      if (p?.user_id) map.set(String(p.user_id), p);
    }
    return map;
  }, [participants]);

  const transcript = useMemo<TranscriptEntry[]>(() => {
    const speeches = Array.isArray(details?.speeches) ? details!.speeches.slice() : [];
    speeches.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    return speeches.map((s) => {
      const userId = String(s.user_id || '');
      const p = participantByUserId.get(userId);
      const role = normalizeRole(p?.role);
      const isAI =
        !p ||
        userId.toLowerCase().includes('ai') ||
        role.toLowerCase().includes('ai') ||
        role.toLowerCase().includes('bot');
      const speaker = p?.name || (isAI ? 'AI智能体' : '未知辩手');
      const position = role ? roleToPosition(role) : (isAI ? 'AI' : '');

      return {
        id: String(s.id || `${s.created_at}-${userId}`),
        speaker,
        position,
        message: String(s.content || ''),
        timestamp: s.created_at ? new Date(s.created_at) : new Date(),
        isAI,
        audioUrl: resolveMediaUrl((s as any).audio_url),
      };
    });
  }, [details, participantByUserId]);

  const humanTeam = useMemo<Participant[]>(() => {
    const roles = ['debater_1', 'debater_2', 'debater_3', 'debater_4'] as const;
    return roles.map((role, idx) => {
      const p = participants.find((x) => normalizeRole(x?.role) === role) || null;
      return {
        id: p?.user_id || `placeholder-${role}`,
        name: p?.name || '—',
        position: roleToPosition(role) as Participant['position'],
        isAI: false,
        isMuted: false,
        isVideoOff: false,
        isSpeaking: false,
        signalStrength: undefined,
        role: idx === 0 ? 'captain' : 'member',
      };
    });
  }, [participants]);

  const aiTeam = useMemo<AIAvatarType[]>(() => {
    const ids = ['ai_1', 'ai_2', 'ai_3', 'ai_4'] as const;
    return ids.map((id) => ({
      id,
      name: `AI${roleToPosition(id)}`,
      position: roleToPosition(id) as AIAvatarType['position'],
      aiType: id === 'ai_1' ? 'analytical' : id === 'ai_2' ? 'creative' : id === 'ai_3' ? 'aggressive' : 'balanced',
      skillLevel: 85,
      isSpeaking: false,
      processingPower: 80,
    }));
  }, []);

  const topic = details?.debate?.topic || '辩论回放';
  const createdAt = details?.debate?.created_at
    ? new Date(details.debate.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
    : '';

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-[radial-gradient(circle_at_8%_10%,rgba(216,231,242,0.78),transparent_25%),radial-gradient(circle_at_90%_18%,rgba(249,236,222,0.82),transparent_24%),linear-gradient(180deg,#fbf7f1_0%,#f8f5f1_52%,#f7f1ea_100%)]">
      {error && (
        <div className="app-top-layer fixed top-4 right-4 max-w-md">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </div>
      )}

      <div className="sticky top-0 z-40 px-4 py-4 sm:px-6">
        <div className="student-container">
          <div className="student-header-frame px-4 py-3 sm:px-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex min-w-0 items-center gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={onBack}
                  className="student-light-button h-auto px-4 py-2"
            >
                  <ArrowLeft className="mr-2 h-4 w-4" />
              返回
            </Button>
            <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Replay Arena</p>
                  <h1 className="mt-1 truncate text-xl font-semibold tracking-[-0.03em] text-slate-950">{topic}</h1>
                  {createdAt && <div className="mt-1 text-xs text-slate-500">{createdAt}</div>}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge className="student-pill">回放模式</Badge>
                <Badge className="student-pill">{transcript.length} 条发言</Badge>
                <Badge className="student-pill">正方 {participants.length || 0}/4</Badge>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="student-container min-h-0 flex-1 overflow-y-auto pb-6 custom-scrollbar">
          {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="student-card flex min-w-[280px] items-center justify-center px-8 py-10">
              <Loader2 className="h-8 w-8 animate-spin text-slate-700" />
              <span className="ml-3 text-slate-600">正在加载回放数据...</span>
            </div>
          </div>
          ) : (
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
            <main className="space-y-5">
              <section className="student-card overflow-hidden p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Replay Stage</p>
                <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                  <div>
                    <h2 className="text-2xl font-semibold tracking-[-0.04em] text-slate-950">赛后复盘舞台</h2>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                      保留正式辩论页的席位视角，方便回看双方阵容和完整发言流。
                    </p>
                  </div>
                  <div className="grid grid-cols-3 gap-3 sm:min-w-[420px]">
                    <div className="rounded-[16px] border border-[#d8e7f2] bg-[#e2eef8]/80 p-3">
                      <div className="text-xs text-slate-500">人类席位</div>
                      <div className="mt-1 text-xl font-semibold text-slate-900">{humanTeam.length}</div>
                    </div>
                    <div className="rounded-[16px] border border-[#e0d8ef] bg-[#eae6f6]/80 p-3">
                      <div className="text-xs text-slate-500">AI 席位</div>
                      <div className="mt-1 text-xl font-semibold text-slate-900">{aiTeam.length}</div>
                    </div>
                    <div className="rounded-[16px] border border-[#f0d6c0] bg-[#f9ecde]/80 p-3">
                      <div className="text-xs text-slate-500">发言</div>
                      <div className="mt-1 text-xl font-semibold text-slate-900">{transcript.length}</div>
                    </div>
                  </div>
                </div>
              </section>

              <section className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                <div className="space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <Users className="h-6 w-6 text-slate-700" />
                      <h2 className="text-xl font-semibold text-slate-900">对阵人员（人类）</h2>
                    </div>
                    <Badge className="student-pill">正方</Badge>
                  </div>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {humanTeam.map((p) => (
                      <ParticipantVideo key={p.id} participant={p} isActive={false} isCurrentUser={false} />
                    ))}
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <Bot className="h-6 w-6 text-slate-700" />
                      <h2 className="text-xl font-semibold text-slate-900">对阵人员（AI）</h2>
                    </div>
                    <Badge className="student-pill">反方</Badge>
                  </div>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {aiTeam.map((ai) => (
                      <AIAvatar key={ai.id} ai={ai} isActive={false} />
                    ))}
                  </div>
                </div>
              </section>
            </main>

            <aside className="min-h-0 xl:sticky xl:top-28 xl:self-start">
              <section className="mb-4 rounded-[22px] border border-[#ece4da] bg-white/88 p-5 shadow-[0_20px_46px_rgba(174,154,126,0.12)] backdrop-blur">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Playback</p>
                <h3 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-slate-950">发言记录</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  回放模式不可发言，可以在这里查看文本与音频记录。
                </p>
              </section>
              <DebateControls
                canSpeak={false}
                transcript={transcript}
                title="赛场发言流"
                badgeText="回放"
                showInput={false}
              />
            </aside>
          </div>
          )}
      </div>
    </div>
  );
};

export default DebateReplayPage;
