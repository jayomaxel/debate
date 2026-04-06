import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Loader2, Clock, Users, Wifi, CheckCircle, SkipForward } from 'lucide-react';

interface WaitingStatus {
  stage: 'connecting' | 'matching' | 'ready' | 'waiting';
  message: string;
  details: string;
  progress?: number;
}

interface WaitingStatusBarProps {
  onMatchFound?: () => void;
}

const WaitingStatusBar: React.FC<WaitingStatusBarProps> = ({ onMatchFound }) => {
  const [status, setStatus] = useState<WaitingStatus>({
    stage: 'connecting',
    message: '正在连接服务器...',
    details: '建立与辩论平台的连接',
    progress: 20
  });

  const [dots, setDots] = useState('');

  // 模拟状态变化
  useEffect(() => {
    const statusSequence = [
      { stage: 'connecting' as const, message: '正在连接服务器...', details: '建立与辩论平台的连接', progress: 20 },
      { stage: 'matching' as const, message: '系统分配中', details: 'AI 正在根据您的能力评估匹配对手', progress: 50 },
      { stage: 'waiting' as const, message: '等待其他参与者加入...', details: '需要2-4名参与者即可开始辩论', progress: 80 },
      { stage: 'ready' as const, message: '准备就绪！', details: '辩论即将开始，请做好准备', progress: 100 }
    ];

    let currentIndex = 0;
    const interval = setInterval(() => {
      currentIndex = (currentIndex + 1) % statusSequence.length;
      setStatus(statusSequence[currentIndex]);
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  // 动画点效果
  useEffect(() => {
    const dotInterval = setInterval(() => {
      setDots(prev => prev.length >= 3 ? '' : prev + '.');
    }, 500);
    return () => clearInterval(dotInterval);
  }, []);

  const getStatusIcon = () => {
    switch (status.stage) {
      case 'connecting':
        return <Loader2 className="w-5 h-5 animate-spin text-blue-600" />;
      case 'matching':
        return <Users className="w-5 h-5 text-amber-600" />;
      case 'waiting':
        return <Clock className="w-5 h-5 text-slate-600" />;
      case 'ready':
        return <CheckCircle className="w-5 h-5 text-emerald-600" />;
      default:
        return <Loader2 className="w-5 h-5 animate-spin text-slate-600" />;
    }
  };

  const getStatusColor = () => {
    switch (status.stage) {
      case 'connecting':
        return 'bg-blue-50 border-blue-200';
      case 'matching':
        return 'bg-amber-50 border-amber-200';
      case 'waiting':
        return 'bg-slate-50 border-slate-200';
      case 'ready':
        return 'bg-emerald-50 border-emerald-200';
      default:
        return 'bg-slate-50 border-slate-200';
    }
  };

  const getProgressColor = () => {
    switch (status.stage) {
      case 'connecting':
        return 'bg-blue-600';
      case 'matching':
        return 'bg-amber-600';
      case 'waiting':
        return 'bg-slate-600';
      case 'ready':
        return 'bg-emerald-600';
      default:
        return 'bg-slate-600';
    }
  };

  return (
    <Card className={`${getStatusColor()} border-2 shadow-sm`}>
      <CardContent className="p-6">
        <div className="flex items-center gap-4 mb-4">
          <div className="flex items-center gap-3">
            {getStatusIcon()}
            <div>
              <h3 className="font-semibold text-slate-900">
                {status.message}{dots}
              </h3>
              <p className="text-sm text-slate-600">{status.details}</p>
            </div>
          </div>

          <div className="ml-auto">
            <Badge
              variant="outline"
              className={
                status.stage === 'ready'
                  ? 'bg-emerald-100 text-emerald-700 border-emerald-300'
                  : 'bg-blue-100 text-blue-700 border-blue-300'
              }
            >
              <Wifi className="w-3 h-3 mr-1" />
              {status.stage === 'ready' ? '在线' : '连接中'}
            </Badge>
          </div>
        </div>

        {/* 进度条 */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-slate-600">
            <span>准备进度</span>
            <span>{status.progress}%</span>
          </div>
          <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-1000 ease-out ${getProgressColor()}`}
              style={{ width: `${status.progress}%` }}
            />
          </div>
        </div>

        {/* 状态说明 */}
        <div className="mt-4 p-3 bg-white/60 rounded-lg border border-slate-200">
          <div className="flex items-start gap-2">
            <div className="w-2 h-2 rounded-full bg-blue-600 mt-2 flex-shrink-0" />
            <div className="text-sm text-slate-600">
              <p className="font-medium text-slate-700 mb-1">准备提示</p>
              <ul className="space-y-1 text-xs">
                <li>• 请确保您已完成个人能力评估</li>
                <li>• 准备好麦克风和摄像头（如需要）</li>
                <li>• 熟悉本次辩题的背景资料</li>
                <li>• 系统将在所有参与者就绪后自动开始辩论</li>
              </ul>
            </div>
          </div>
        </div>

        {/* 开发测试按钮 - 跳过等待 */}
        {onMatchFound && (
          <div className="mt-4">
            <Button
              onClick={onMatchFound}
              variant="outline"
              size="sm"
              className="w-full border-blue-300 text-blue-700 hover:bg-blue-50"
            >
              <SkipForward className="w-4 h-4 mr-2" />
              跳过等待，查看匹配结果
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default WaitingStatusBar;