import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import TeamDisplay from './team-display';
import StanceDisplay from './stance-display';
import TeamMember, { TeamMember as TeamMemberType } from './team-member';
import StudentService from '@/services/student.service';
import type { Debate, DebateParticipant } from '@/services/student.service';
import {
  ArrowLeft,
  Volume2,
  VolumeX,
  Maximize,
  Minimize,
  Settings,
  Trophy,
  Users,
  Bot,
  Sparkles
} from 'lucide-react';

interface DebateMatchResultProps {
  initialDebate?: Debate | null;
  onBack?: () => void;
  onStartDebate?: (debateId?: string) => void;
  onCountdownEnd?: () => void;
}

const DebateMatchResult: React.FC<DebateMatchResultProps> = ({
  initialDebate,
  onBack,
  onStartDebate,
  onCountdownEnd
}) => {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [joinedDebate, setJoinedDebate] = useState<Debate | null>(null);

  useEffect(() => {
    if (initialDebate) {
      setJoinedDebate(initialDebate);
      return;
    }
    const load = async () => {
      try {
        const debates = await StudentService.getAvailableDebates();
        const joinedCandidates = debates.filter((d) => d.is_joined);
        const statusPriority: Record<Debate['status'], number> = {
          in_progress: 0,
          published: 1,
          draft: 2,
          completed: 3,
        };
        const joined = joinedCandidates
          .slice()
          .sort((a, b) => {
            const statusDelta = (statusPriority[a.status] ?? 99) - (statusPriority[b.status] ?? 99);
            if (statusDelta !== 0) return statusDelta;
            const roleDelta = Number(!!b.role) - Number(!!a.role);
            if (roleDelta !== 0) return roleDelta;
            return Date.parse(b.created_at) - Date.parse(a.created_at);
          })[0];
        setJoinedDebate(joined ?? null);
      } catch {
        setJoinedDebate(null);
      }
    };
    load();
  }, [initialDebate]);

  useEffect(() => {
    const debateId = joinedDebate?.id;
    if (!debateId) return;
    const hasParticipants = Array.isArray(joinedDebate?.participants) && joinedDebate.participants.length > 0;
    if (hasParticipants) return;

    let cancelled = false;
    (async () => {
      try {
        const participants = await StudentService.getDebateParticipants(debateId);
        if (cancelled) return;
        setJoinedDebate((prev) => {
          if (!prev || prev.id !== debateId) return prev;
          return { ...prev, participants: participants as DebateParticipant[] };
        });
      } catch {
        if (cancelled) return;
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [joinedDebate?.id]);

  const roleToPosition: Record<NonNullable<Debate['role']>, TeamMemberType['position']> = {
    debater_1: '一辩',
    debater_2: '二辩',
    debater_3: '三辩',
    debater_4: '四辩',
  };

  const humanTeam: TeamMemberType[] = (joinedDebate?.participants || [])
    .filter((p) => !!p.role)
    .map((p) => ({
      id: p.user_id,
      name: p.name || p.user_id.slice(0, 8),
      position: roleToPosition[p.role],
      skillLevel: typeof p.overall_score === 'number' ? p.overall_score : 60,
      isAI: false,
    }));

  const aiTeam: TeamMemberType[] = [
    {
      id: 'ai-1',
      name: 'Alpha-Logic',
      position: '一辩',
      skillLevel: 85,
      isAI: true,
      aiType: 'analytical'
    },
    {
      id: 'ai-2',
      name: 'Beta-Creative',
      position: '二辩',
      skillLevel: 78,
      isAI: true,
      aiType: 'creative'
    },
    {
      id: 'ai-3',
      name: 'Gamma-Strategic',
      position: '三辩',
      skillLevel: 88,
      isAI: true,
      aiType: 'aggressive'
    },
    {
      id: 'ai-4',
      name: 'Delta-Balance',
      position: '四辩',
      skillLevel: 80,
      isAI: true,
      aiType: 'balanced'
    }
  ];

  const topic = joinedDebate?.topic || '辩题加载中...';
  const userStance: 'positive' | 'negative' = 'positive';

  const humanAvg =
    humanTeam.length > 0
      ? Math.round(humanTeam.reduce((sum, m) => sum + (m.skillLevel || 0), 0) / humanTeam.length)
      : 0;
  const aiAvg = Math.round(aiTeam.reduce((sum, m) => sum + (m.skillLevel || 0), 0) / aiTeam.length);

  const handleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
    // 实际项目中这里会调用全屏API
  };

  const handleMute = () => {
    setIsMuted(!isMuted);
  };

  const handleReady = () => {
    // 用户点击准备就绪
    console.log('用户准备就绪');
    onStartDebate?.(joinedDebate?.id);
  };

  return (
    <div className={`min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-purple-900 ${isFullscreen ? 'fixed inset-0 z-50' : ''}`}>
      {/* 顶部控制栏 */}
      <header className="bg-slate-800/90 backdrop-blur border-b border-slate-700 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={onBack}
                className="text-slate-300 hover:text-white hover:bg-slate-700"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                返回
              </Button>

              <div className="flex items-center gap-3">
                <Badge className="bg-blue-600 text-white">
                  <Trophy className="w-3 h-3 mr-1" />
                  辩论匹配完成
                </Badge>
                <Badge variant="outline" className="text-slate-300 border-slate-600">
                  <Users className="w-3 h-3 mr-1" />
                  4v4 对抗
                </Badge>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowDetails(!showDetails)}
                className="text-slate-300 hover:text-white hover:bg-slate-700"
              >
                <Settings className="w-4 h-4 mr-2" />
                {showDetails ? '简化' : '详情'}
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleMute}
                className="text-slate-300 hover:text-white hover:bg-slate-700"
              >
                {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleFullscreen}
                className="text-slate-300 hover:text-white hover:bg-slate-700"
              >
                {isFullscreen ? <Minimize className="w-4 h-4" /> : <Maximize className="w-4 h-4" />}
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* 主要内容 */}
      <div className="p-6 space-y-6">
        <div className="max-w-7xl mx-auto">
          {/* 立场展示 */}
          <div className="mb-8">
            <StanceDisplay
              stance={userStance}
              topic={topic}
              onCountdownEnd={onCountdownEnd}
            />
          </div>

          {/* 分屏对战展示 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            {/* 人类团队 */}
            <div className={`transition-all duration-700 ${showDetails ? 'opacity-100' : 'opacity-70 hover:opacity-100'}`}>
              <TeamDisplay
                title="人类团队"
                members={humanTeam}
                isHuman={true}
                isAnimating={true}
                teamColor="blue"
              />
            </div>

            {/* AI团队 */}
            <div className={`transition-all duration-700 delay-100 ${showDetails ? 'opacity-100' : 'opacity-70 hover:opacity-100'}`}>
              <TeamDisplay
                title="AI智能团队"
                members={aiTeam}
                isHuman={false}
                isAnimating={true}
                teamColor="purple"
              />
            </div>
          </div>

          {/* 底部操作区域 */}
          <div className="flex flex-col items-center space-y-4">
            {/* 匹配统计 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full max-w-2xl">
              <div className="text-center p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                <div className="text-2xl font-bold text-blue-400">{humanAvg || '--'}</div>
                <div className="text-sm text-slate-400">人类团队均分</div>
              </div>
              <div className="text-center p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                <div className="text-2xl font-bold text-purple-400">{aiAvg}</div>
                <div className="text-sm text-slate-400">AI团队均分</div>
              </div>
              <div className="text-center p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                <div className="text-2xl font-bold text-emerald-400">92%</div>
                <div className="text-sm text-slate-400">匹配成功率</div>
              </div>
              <div className="text-center p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                <div className="text-2xl font-bold text-amber-400">A+</div>
                <div className="text-sm text-slate-400">对抗等级</div>
              </div>
            </div>

            {/* 操作按钮 */}
            <div className="flex items-center gap-4">
              <Button
                size="lg"
                onClick={handleReady}
                className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white px-8 py-3 text-lg"
              >
                <Sparkles className="w-5 h-5 mr-2" />
                准备就绪，开始辩论
              </Button>

              <div className="text-sm text-slate-400">
                系统将在倒计时结束后自动开始
              </div>
            </div>

            {/* 对战预告 */}
            <div className="max-w-4xl w-full p-6 bg-slate-800/30 rounded-lg border border-slate-700">
              <h3 className="text-lg font-semibold text-slate-200 mb-3 text-center">
                对战预告
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-blue-400">
                    <Users className="w-4 h-4" />
                    <span className="font-medium">人类团队优势</span>
                  </div>
                  <ul className="text-slate-400 space-y-1 ml-6">
                    <li>• 团队协作与默契配合</li>
                    <li>• 创新思维与人文视角</li>
                    <li>• 灵活应对与临场发挥</li>
                  </ul>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-purple-400">
                    <Bot className="w-4 h-4" />
                    <span className="font-medium">AI团队优势</span>
                  </div>
                  <ul className="text-slate-400 space-y-1 ml-6">
                    <li>• 逻辑推理与数据分析</li>
                    <li>• 知识储备与信息检索</li>
                    <li>• 多样化策略与快速响应</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 添加CSS动画 */}
      <style>{`
        @keyframes fadeInScale {
          from {
            opacity: 0;
            transform: scale(0.95);
          }
          to {
            opacity: 1;
            transform: scale(1);
          }
        }
      `}</style>
    </div>
  );
};

export default DebateMatchResult;
