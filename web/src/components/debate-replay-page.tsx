import React, { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import ParticipantVideo, { Participant } from './participant-video';
import AIAvatar, { AIAvatar as AIAvatarType } from './ai-avatar';
import DebateControls from './debate-controls';
import StudentService, { type DebateDetails, type DebateParticipant } from '@/services/student.service';
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

  let base = (((import.meta as any).env?.VITE_API_BASE_URL as string | undefined) || '').replace(/\/+$/, '');
  if (trimmed.startsWith('/uploads') || trimmed.startsWith('uploads/')) {
    base = base.replace(/\/api\/v1$/, '').replace(/\/api$/, '');
  }

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
        const [loadedDetails, loadedParticipants] = await Promise.all([
          StudentService.getDebateDetails(debateId),
          StudentService.getDebateParticipants(debateId),
        ]);
        if (cancelled) return;
        setDetails(loadedDetails);
        setParticipants(Array.isArray(loadedParticipants) ? loadedParticipants : []);
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
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-purple-900 flex flex-col">
      {error && (
        <div className="fixed top-4 right-4 z-50 max-w-md">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </div>
      )}

      <div className="border-b border-slate-700/50 bg-slate-900/60 backdrop-blur">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <Button
              type="button"
              variant="outline"
              onClick={onBack}
              className="border-slate-600 text-slate-200 hover:text-white hover:bg-slate-700"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              返回
            </Button>
            <div className="min-w-0">
              <div className="text-white font-semibold truncate">{topic}</div>
              {createdAt && <div className="text-xs text-slate-400 mt-1">{createdAt}</div>}
            </div>
          </div>
          <Badge className="bg-slate-700/40 text-slate-200 border border-slate-600">回放模式</Badge>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="max-w-7xl mx-auto w-full px-6 py-6">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
              <span className="ml-3 text-slate-200">正在加载回放数据...</span>
            </div>
          ) : (
            <div className="space-y-8">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <Users className="w-6 h-6 text-blue-400" />
                    <h2 className="text-xl font-bold text-white">对阵人员（人类）</h2>
                    <Badge className="bg-blue-600/30 text-blue-300 border-blue-600/50">正方</Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    {humanTeam.map((p) => (
                      <ParticipantVideo key={p.id} participant={p} isActive={false} isCurrentUser={false} />
                    ))}
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <Bot className="w-6 h-6 text-purple-400" />
                    <h2 className="text-xl font-bold text-white">对阵人员（AI）</h2>
                    <Badge className="bg-purple-600/30 text-purple-300 border-purple-600/50">反方</Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    {aiTeam.map((ai) => (
                      <AIAvatar key={ai.id} ai={ai} isActive={false} />
                    ))}
                  </div>
                </div>
              </div>

              <div className="text-sm text-slate-300">
                <span className="text-slate-400">发言记录：</span>
                {transcript.length > 0 ? `共 ${transcript.length} 条` : '暂无'}
              </div>
            </div>
          )}
        </div>
      </div>

      <DebateControls
        canSpeak={false}
        transcript={transcript}
        title="发言记录"
        badgeText="回放"
        showInput={false}
      />
    </div>
  );
};

export default DebateReplayPage;

