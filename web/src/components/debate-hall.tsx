import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import StudentService from '@/services/student.service';
import { useToast } from '@/hooks/use-toast';
import type { Debate } from '@/services/student.service';
import PreparationAssistant from '@/components/student/preparation-assistant';
import {
  Search,
  Clock,
  Trophy,
  Loader2,
  AlertCircle,
  ArrowRight,
  Calendar,
  Target,
  BookOpen
} from 'lucide-react';

interface DebateHallProps {
  onJoinDebate?: (debateId: string) => void;
}

const DebateHall: React.FC<DebateHallProps> = ({ onJoinDebate }) => {
  const { toast } = useToast();
  const [debates, setDebates] = useState<Debate[]>([]);
  const [loading, setLoading] = useState(false);
  const [invitationCode, setInvitationCode] = useState('');
  const [joiningDebateId, setJoiningDebateId] = useState<string | null>(null);
  const [showPreparationAssistant, setShowPreparationAssistant] = useState(false);

  // 加载可参与的辩论
  useEffect(() => {
    loadDebates();
  }, []);

  const loadDebates = async (force?: boolean) => {
    try {
      setLoading(true);
      const data = await StudentService.getAvailableDebates({ force });
      setDebates(data);
    } catch (err: any) {
      console.error('Failed to load debates:', err);
      toast({
        variant: "destructive",
        title: "加载失败",
        description: err.message || '加载辩论列表失败',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleJoinByCode = async () => {
    if (!invitationCode.trim()) {
      toast({
        variant: "destructive",
        title: "提示",
        description: "请输入邀请码",
      });
      return;
    }

    try {
      setJoiningDebateId('code');
      await StudentService.joinDebate({ invitation_code: invitationCode });
      onJoinDebate?.(invitationCode);
    } catch (err: any) {
      console.error('Failed to join debate:', err);
      toast({
        variant: "destructive",
        title: "加入失败",
        description: err.message || '加入辩论失败',
      });
    } finally {
      setJoiningDebateId(null);
    }
  };

  const handleJoinDebate = async (invitationCode: string) => {
    try {
      setJoiningDebateId(invitationCode);
      await StudentService.joinDebate({ invitation_code: invitationCode });
      onJoinDebate?.(invitationCode);
    } catch (err: any) {
      console.error('Failed to join debate:', err);
      toast({
        variant: "destructive",
        title: "加入失败",
        description: err.message || '加入辩论失败',
      });
    } finally {
      setJoiningDebateId(null);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'draft':
        return <Badge className="bg-gray-100 text-gray-700 border-gray-300">草稿</Badge>;
      case 'published':
        return <Badge className="bg-amber-100 text-amber-700 border-amber-300">已发布</Badge>;
      case 'in_progress':
        return <Badge className="bg-blue-100 text-blue-700 border-blue-300">进行中</Badge>;
      case 'completed':
        return <Badge className="bg-green-100 text-green-700 border-green-300">已结束</Badge>;
      default:
        return <Badge className="bg-gray-100 text-gray-700 border-gray-300">{status}</Badge>;
    }
  };

  const formatDuration = (minutes: number) => {
    if (minutes < 60) {
      return `${minutes}分钟`;
    }
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return mins > 0 ? `${hours}小时${mins}分钟` : `${hours}小时`;
  };

  return (
    <div className="space-y-6">
      {/* 标题和邀请码输入 */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle className="flex items-center gap-2">
              <Target className="w-5 h-5" />
              辩论大厅
            </CardTitle>
            <Button
              variant="outline"
              onClick={() => setShowPreparationAssistant(true)}
              className="flex items-center gap-2"
            >
              <BookOpen className="w-4 h-4" />
              备战辅助
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder="输入6位邀请码加入辩论"
                value={invitationCode}
                onChange={(e) => setInvitationCode(e.target.value.toUpperCase())}
                maxLength={6}
                className="text-center text-lg tracking-widest"
              />
            </div>
            <Button
              onClick={handleJoinByCode}
              disabled={invitationCode.length !== 6 || joiningDebateId === 'code'}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {joiningDebateId === 'code' ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  加入中...
                </>
              ) : (
                <>
                  <ArrowRight className="w-4 h-4 mr-2" />
                  加入辩论
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 可参与的辩论列表 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Trophy className="w-5 h-5" />
              可参与的辩论
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => loadDebates(true)}
              disabled={loading}
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Search className="w-4 h-4" />
              )}
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading && debates.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
            </div>
          ) : debates.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Trophy className="w-12 h-12 mx-auto mb-4 text-gray-400" />
              <p>暂无可参与的辩论</p>
              <p className="text-sm mt-2">请使用邀请码加入辩论</p>
            </div>
          ) : (
            <div className="space-y-4">
              {debates.map((debate) => (
                <Card key={debate.id} className="border-2 hover:border-blue-300 transition-colors">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="text-lg font-semibold">{debate.topic}</h3>
                          {getStatusBadge(debate.status)}
                        </div>
                        
                        <div className="grid grid-cols-2 gap-4 mt-3 text-sm text-gray-600">
                          <div className="flex items-center gap-2">
                            <Clock className="w-4 h-4" />
                            <span>时长: {formatDuration(debate.duration)}</span>
                          </div>
                          {debate.created_at && (
                            <div className="flex items-center gap-2">
                              <Calendar className="w-4 h-4" />
                              <span>创建时间: {new Date(debate.created_at).toLocaleDateString('zh-CN')}</span>
                            </div>
                          )}
                          {debate.description && (
                            <div className="col-span-2 text-gray-500">
                              {debate.description}
                            </div>
                          )}
                        </div>
                      </div>

                      <Button
                        onClick={() => handleJoinDebate(debate.invitation_code)}
                        disabled={
                          debate.status === 'completed' ||
                          debate.status === 'in_progress' ||
                          joiningDebateId === debate.invitation_code
                        }
                        className="ml-4"
                      >
                        {joiningDebateId === debate.invitation_code ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            加入中...
                          </>
                        ) : (
                          <>
                            <ArrowRight className="w-4 h-4 mr-2" />
                            加入
                          </>
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Preparation Assistant Dialog */}
      {showPreparationAssistant && (
        <PreparationAssistant
          onClose={() => setShowPreparationAssistant(false)}
        />
      )}
    </div>
  );
};

export default DebateHall;
