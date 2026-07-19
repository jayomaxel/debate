import React, { useCallback, useEffect, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type {
  DebateConfigMeta,
  TopicCandidateContract,
  TopicRecommendationDashboardContract,
  TopicRecommendationRunContract,
  TopicRecommendationRunSummary,
} from '@/lib/frontend-contracts';
import TeacherService from '@/services/teacher.service';
import {
  BarChart3,
  CheckCircle,
  History,
  Lightbulb,
  Loader2,
  RefreshCw,
  Search,
} from 'lucide-react';

interface TopicRecommendationPanelProps {
  classId: string;
  onSelect: (topic: string, config: DebateConfigMeta) => void;
}

const formatDateTime = (value?: string | null) => {
  if (!value) return '暂无';
  return new Date(value).toLocaleString('zh-CN');
};

const formatPercent = (value?: number) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '0%';
  return `${Math.round(value * 100)}%`;
};

const buildSelectionConfig = (
  designId: string | null,
  runId: string | null | undefined,
  candidate: TopicCandidateContract,
  activityFocus?: DebateConfigMeta['activity_focus']
): DebateConfigMeta => ({
  teaching_design_version_id: designId || undefined,
  topic_recommendation_run_id: runId || undefined,
  selected_topic_candidate_id: candidate.candidate_id,
  topic_source: 'ai_recommended',
  activity_focus: activityFocus,
  knowledge_points: candidate.mapped_knowledge_points,
  objective: candidate.mapped_course_objectives,
});

const TopicRecommendationPanel: React.FC<TopicRecommendationPanelProps> = ({
  classId,
  onSelect,
}) => {
  const [designId, setDesignId] = useState<string | null>(null);
  const [chapterFocus, setChapterFocus] = useState('');
  const [trainingFocus, setTrainingFocus] = useState('');
  const [classroomScene, setClassroomScene] = useState('');
  const [candidates, setCandidates] = useState<TopicCandidateContract[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [history, setHistory] = useState<TopicRecommendationRunSummary[]>([]);
  const [dashboard, setDashboard] = useState<TopicRecommendationDashboardContract | null>(null);
  const [selectedRun, setSelectedRun] = useState<TopicRecommendationRunContract | null>(null);
  const [loading, setLoading] = useState(false);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [detailLoadingRunId, setDetailLoadingRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activityFocus = {
    chapter_focus: chapterFocus || undefined,
    training_focus: trainingFocus || undefined,
    classroom_scene: classroomScene || undefined,
  };

  const loadInsights = useCallback(async () => {
    if (!classId) {
      setHistory([]);
      setDashboard(null);
      setSelectedRun(null);
      return;
    }

    setInsightsLoading(true);
    try {
      const [dashboardData, historyData] = await Promise.all([
        TeacherService.getTopicRecommendationDashboard(classId, {
          recent_limit: 5,
          leaderboard_limit: 5,
          observation_limit: 5,
        }),
        TeacherService.listTopicRecommendationRuns(classId, { limit: 8 }),
      ]);
      setDashboard(dashboardData);
      setHistory(historyData);
    } catch (err) {
      console.warn('[TopicRecommendationPanel] Failed to load recommendation insights:', err);
    } finally {
      setInsightsLoading(false);
    }
  }, [classId]);

  useEffect(() => {
    setCandidates([]);
    setRunId(null);
    setSelectedRun(null);
    if (!classId) {
      setDesignId(null);
      return;
    }
    TeacherService.getCurrentTeachingDesign(classId)
      .then((value) => setDesignId(value?.id || null))
      .catch(() => setDesignId(null));
    void loadInsights();
  }, [classId, loadInsights]);

  const generate = async (regenerate = false) => {
    if (!classId || !designId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await TeacherService.generateTopicRecommendations(classId, {
        teaching_design_version_id: designId,
        mode: 'teaching',
        preferred_count: 4,
        regenerate_from_run_id: regenerate ? runId || undefined : undefined,
        activity_focus: activityFocus,
      });
      setCandidates(result.candidates || []);
      setRunId(result.run_id);
      setSelectedRun(result);
      if (!result.candidates?.length) setError(result.warnings?.[0] || '没有生成可用辩题');
      void loadInsights();
    } catch (err: any) {
      setError(err?.message || '候选辩题生成失败，手动填写仍可继续');
    } finally {
      setLoading(false);
    }
  };

  const loadRunDetail = async (nextRunId: string) => {
    setDetailLoadingRunId(nextRunId);
    setError(null);
    try {
      const result = await TeacherService.getTopicRecommendationRun(nextRunId);
      setSelectedRun(result);
    } catch (err: any) {
      setError(err?.message || '推荐详情加载失败');
    } finally {
      setDetailLoadingRunId(null);
    }
  };

  const latestSummary = dashboard?.summary;
  const candidateAdoptionRate = formatPercent(latestSummary?.candidate_adoption_rate);
  const runAdoptionRate = formatPercent(latestSummary?.run_adoption_rate);
  const activeVersion = dashboard?.quality.version_breakdown.find((item) => item.is_active);

  return (
    <div className='space-y-4 rounded-lg border border-blue-100 bg-blue-50/40 p-4'>
      <div className='flex flex-wrap items-center justify-between gap-3'>
        <div>
          <div className='flex items-center gap-2 font-medium text-slate-900'>
            <Lightbulb className='h-4 w-4 text-blue-600' />
            教学设计与辩题推荐
          </div>
          <p className='mt-1 text-sm text-slate-500'>
            {designId ? '已读取当前班级教学设计' : '当前班级没有教学设计，仍可手动填写辩题'}
          </p>
        </div>
        <div className='flex flex-wrap gap-2'>
          <Button type='button' variant='outline' disabled={insightsLoading || !classId} onClick={() => void loadInsights()}>
            {insightsLoading ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <BarChart3 className='mr-2 h-4 w-4' />}
            刷新看板
          </Button>
          <Button type='button' variant='outline' disabled={!designId || loading} onClick={() => void generate(Boolean(runId))}>
            {loading ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : runId ? <RefreshCw className='mr-2 h-4 w-4' /> : null}
            {runId ? '重新生成' : '生成候选辩题'}
          </Button>
        </div>
      </div>

      <div className='grid gap-3 md:grid-cols-3'>
        <div className='space-y-1'>
          <Label>章节重点</Label>
          <Input value={chapterFocus} onChange={(event) => setChapterFocus(event.target.value)} />
        </div>
        <div className='space-y-1'>
          <Label>训练目标</Label>
          <Input value={trainingFocus} onChange={(event) => setTrainingFocus(event.target.value)} />
        </div>
        <div className='space-y-1'>
          <Label>课堂场景</Label>
          <Input value={classroomScene} onChange={(event) => setClassroomScene(event.target.value)} />
        </div>
      </div>

      {error && (
        <Alert>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue='current'>
        <TabsList>
          <TabsTrigger value='current'>本次候选</TabsTrigger>
          <TabsTrigger value='dashboard'>推荐看板</TabsTrigger>
          <TabsTrigger value='history'>历史记录</TabsTrigger>
        </TabsList>

        <TabsContent value='current' className='mt-4'>
          {candidates.length > 0 ? (
            <div className='grid gap-3 lg:grid-cols-2'>
              {candidates.map((candidate) => (
                <Card key={candidate.candidate_id} className='border-slate-200'>
                  <CardContent className='space-y-3 p-4'>
                    <div className='font-medium text-slate-900'>{candidate.topic_text}</div>
                    <div className='flex flex-wrap gap-1'>
                      {candidate.mapped_knowledge_points.map((item) => <Badge key={item} variant='secondary'>{item}</Badge>)}
                      {candidate.difficulty_level && <Badge variant='outline'>{candidate.difficulty_level}</Badge>}
                      {candidate.quality_score != null && <Badge variant='outline'>质量 {candidate.quality_score}</Badge>}
                    </div>
                    <p className='text-sm text-slate-600'>{candidate.debatability_reason || candidate.recommendation_reason}</p>
                    <Button
                      type='button'
                      size='sm'
                      onClick={() => onSelect(
                        candidate.topic_text,
                        buildSelectionConfig(designId, runId, candidate, activityFocus)
                      )}
                    >
                      选用此辩题
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <div className='rounded-md border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500'>
              暂无本次候选辩题。
            </div>
          )}
        </TabsContent>

        <TabsContent value='dashboard' className='mt-4 space-y-4'>
          <div className='grid gap-3 md:grid-cols-4'>
            <div className='rounded-md border bg-white p-3'>
              <div className='text-xs text-slate-500'>推荐次数</div>
              <div className='mt-1 text-2xl font-semibold'>{latestSummary?.total_runs ?? 0}</div>
            </div>
            <div className='rounded-md border bg-white p-3'>
              <div className='text-xs text-slate-500'>候选辩题</div>
              <div className='mt-1 text-2xl font-semibold'>{latestSummary?.total_candidates ?? 0}</div>
            </div>
            <div className='rounded-md border bg-white p-3'>
              <div className='text-xs text-slate-500'>推荐采用率</div>
              <div className='mt-1 text-2xl font-semibold'>{runAdoptionRate}</div>
            </div>
            <div className='rounded-md border bg-white p-3'>
              <div className='text-xs text-slate-500'>候选采用率</div>
              <div className='mt-1 text-2xl font-semibold'>{candidateAdoptionRate}</div>
            </div>
          </div>

          <div className='grid gap-3 lg:grid-cols-2'>
            <div className='rounded-md border bg-white p-4'>
              <div className='mb-3 flex items-center gap-2 text-sm font-medium text-slate-800'>
                <CheckCircle className='h-4 w-4 text-emerald-600' />
                热门采用辩题
              </div>
              <div className='space-y-2'>
                {(dashboard?.leaderboards.top_adopted_candidates || []).map((item) => (
                  <div key={`${item.run_id}-${item.candidate_id}`} className='rounded-md bg-slate-50 p-3 text-sm'>
                    <div className='font-medium text-slate-900'>{item.topic_text}</div>
                    <div className='mt-1 text-xs text-slate-500'>采用 {item.total_adoptions} 次，编辑后采用 {item.edited_adoptions} 次</div>
                  </div>
                ))}
                {!dashboard?.leaderboards.top_adopted_candidates.length && <div className='text-sm text-slate-500'>暂无采用数据。</div>}
              </div>
            </div>

            <div className='rounded-md border bg-white p-4'>
              <div className='mb-3 flex items-center gap-2 text-sm font-medium text-slate-800'>
                <Search className='h-4 w-4 text-blue-600' />
                高质量待观察
              </div>
              <div className='space-y-2'>
                {(dashboard?.observations.high_quality_low_adoption_candidates || []).map((item) => (
                  <div key={`${item.run_id}-${item.candidate_id}`} className='rounded-md bg-slate-50 p-3 text-sm'>
                    <div className='font-medium text-slate-900'>{item.topic_text}</div>
                    <div className='mt-1 text-xs text-slate-500'>质量 {item.quality_score ?? '-'}，采用 {item.total_adoptions} 次</div>
                  </div>
                ))}
                {!dashboard?.observations.high_quality_low_adoption_candidates.length && <div className='text-sm text-slate-500'>暂无观察项。</div>}
              </div>
            </div>
          </div>

          <div className='rounded-md border bg-white p-4 text-sm text-slate-600'>
            当前活跃版本：{activeVersion?.version_name || activeVersion?.title || activeVersion?.teaching_design_version_id || '暂无'}
            <span className='mx-2 text-slate-300'>|</span>
            最近生成：{formatDateTime(dashboard?.timeline.last_generated_at)}
            <span className='mx-2 text-slate-300'>|</span>
            最近采用：{formatDateTime(dashboard?.timeline.last_adopted_at)}
          </div>
        </TabsContent>

        <TabsContent value='history' className='mt-4 space-y-3'>
          {history.length === 0 ? (
            <div className='rounded-md border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500'>
              暂无推荐历史。
            </div>
          ) : (
            history.map((item) => (
              <div key={item.run_id} className='rounded-md border bg-white p-3'>
                <div className='flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between'>
                  <div className='min-w-0'>
                    <div className='flex flex-wrap items-center gap-2'>
                      <Badge variant='outline'>{item.status}</Badge>
                      {item.generation_quality && <Badge variant='secondary'>{item.generation_quality}</Badge>}
                      <span className='text-xs text-slate-500'>{formatDateTime(item.generated_at)}</span>
                    </div>
                    <div className='mt-2 space-y-1'>
                      {(item.candidate_topics || []).slice(0, 3).map((topic) => (
                        <div key={topic} className='truncate text-sm text-slate-800'>{topic}</div>
                      ))}
                    </div>
                    <div className='mt-2 text-xs text-slate-500'>
                      候选 {item.candidate_count ?? item.candidate_topics?.length ?? 0} 个，采用 {item.adoption_summary?.total_adoptions ?? 0} 次
                    </div>
                  </div>
                  <Button type='button' variant='outline' size='sm' onClick={() => void loadRunDetail(item.run_id)}>
                    {detailLoadingRunId === item.run_id ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <History className='mr-2 h-4 w-4' />}
                    详情
                  </Button>
                </div>
              </div>
            ))
          )}

          {selectedRun && (
            <div className='rounded-md border border-blue-100 bg-white p-4'>
              <div className='mb-3 text-sm font-medium text-slate-900'>
                推荐详情：{formatDateTime(selectedRun.generated_at)}
              </div>
              <div className='grid gap-3 lg:grid-cols-2'>
                {selectedRun.candidates.map((candidate) => (
                  <div key={candidate.candidate_id} className='rounded-md border border-slate-200 p-3'>
                    <div className='font-medium text-slate-900'>{candidate.topic_text}</div>
                    <div className='mt-2 flex flex-wrap gap-1'>
                      {candidate.mapped_knowledge_points.map((item) => <Badge key={item} variant='secondary'>{item}</Badge>)}
                      {candidate.adoption_stats?.is_adopted && <Badge className='bg-emerald-100 text-emerald-700'>已采用</Badge>}
                    </div>
                    <p className='mt-2 text-sm text-slate-600'>{candidate.recommendation_reason || candidate.debatability_reason}</p>
                    <Button
                      type='button'
                      size='sm'
                      variant='outline'
                      className='mt-3'
                      onClick={() => onSelect(
                        candidate.topic_text,
                        buildSelectionConfig(
                          selectedRun.teaching_design_version_id || designId,
                          selectedRun.run_id,
                          candidate,
                          selectedRun.activity_focus || activityFocus
                        )
                      )}
                    >
                      回填到新建辩论
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default TopicRecommendationPanel;
