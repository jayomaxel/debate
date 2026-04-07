/**
 * Student Service
 * 学生端服务 - 处理学生相关的所有API调用
 */

import { api } from '../lib/api';

// ==================== 接口定义 ====================

// 个人信息
export interface StudentProfile {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  student_id?: string;
  avatar?: string;
  created_at: string;
}

export interface UpdateProfileParams {
  name?: string;
  email?: string;
  phone?: string;
  student_id?: string;
}

// 能力评估
export interface AssessmentParams {
  personality_type?: string;
  expression_willingness: number;
  logical_thinking: number;
  stablecoin_knowledge: number;
  financial_knowledge: number;
  critical_thinking: number;
}

export interface AssessmentResult {
  id?: string;
  personality_type?: string;
  expression_willingness: number;
  logical_thinking: number;
  stablecoin_knowledge: number;
  financial_knowledge: number;
  critical_thinking: number;
  is_default?: boolean;
  recommended_role: string;
  role_description: string;
  created_at?: string;
}

// 辩论
export interface Debate {
  id: string;
  topic: string;
  description?: string;
  duration: number;
  status: 'draft' | 'published' | 'in_progress' | 'completed';
  invitation_code: string;
  created_at: string;
  class_id?: string;
  student_ids?: string[];
  participant_count?: number;
  is_joined?: boolean;
  role?: 'debater_1' | 'debater_2' | 'debater_3' | 'debater_4' | null;
  role_reason?: string | null;
  participants?: Array<{
    user_id: string;
    name: string;
    role: 'debater_1' | 'debater_2' | 'debater_3' | 'debater_4';
    role_reason?: string | null;
    overall_score?: number;
  }> | null;
}

export type DebateParticipant = NonNullable<Debate['participants']>[number];

export interface JoinDebateParams {
  invitation_code: string;
}

// 历史记录
export interface DebateHistoryItem {
  debate_id: string;
  topic: string;
  role: string;
  stance: 'positive' | 'negative' | 'affirmative';
  status: string;
  score?: number;
  outcome?: 'win' | 'lose' | 'draw';
  duration_seconds?: number;
  created_at: string;
}

export interface DebateHistory {
  list: DebateHistoryItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface FilterHistoryParams {
  status?: string;
  role?: string;
  stance?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

export interface Speech {
  id: string;
  debate_id: string;
  user_id: string;
  content: string;
  audio_url?: string;
  duration: number;
  phase: string;
  created_at: string;
}

export interface Score {
  id: string;
  debate_id: string;
  user_id: string;
  logic: number;
  expression: number;
  rebuttal: number;
  teamwork: number;
  knowledge: number;
  total: number;
  feedback?: string;
  created_at: string;
}

export interface DebateDetails {
  debate: Debate;
  participation: {
    role?: string | null;
    stance?: string | null;
    score?: number;
  };
  speeches: Speech[];
  scores: Score[];
}

// 数据分析
export interface StudentAnalytics {
  total_debates: number;
  completed_debates: number;
  average_score: number;
  ability_scores: {
    logic: number;
    expression: number;
    rebuttal: number;
    teamwork: number;
    knowledge: number;
  };
  speech_stats: {
    total_speeches: number;
    average_duration: number;
  };
  role_distribution: Record<string, number>;
}

export interface GrowthTrendItem {
  debate_id: string;
  topic: string;
  date: string;
  score: number;
  ability_scores: {
    logic: number;
    expression: number;
    rebuttal: number;
    teamwork: number;
    knowledge: number;
  };
}

export interface GrowthTrend {
  debates: GrowthTrendItem[];
}

// 成就系统
export interface Achievement {
  id: string;
  name: string;
  description: string;
  category: 'milestone' | 'performance' | 'ability';
  icon: string;
  unlocked: boolean;
  unlocked_at?: string;
  progress?: number;
  target?: number;
  unlock_hint?: string;
}

export interface ClassComparisonAbilityScores {
  logic: number;
  argument: number;
  response: number;
  persuasion: number;
  teamwork: number;
}

export interface ClassComparisonItem {
  rank: number;
  student_id: string;
  student_name: string;
  score: number;
  overall_score: number;
  ability_scores: ClassComparisonAbilityScores;
}

export interface ClassComparisonMyStats {
  student_id: string;
  student_name: string;
  rank: number;
  percentile: number | null;
  score: number;
  overall_score: number;
  ability_scores: ClassComparisonAbilityScores;
}

export interface ClassComparisonAvgStats {
  score: number;
  overall_score: number;
  ability_scores: ClassComparisonAbilityScores;
}

export interface ClassComparison {
  class_id: string;
  class_name: string;
  metric: string;
  my: ClassComparisonMyStats | null;
  class_avg: ClassComparisonAvgStats | null;
  leaderboard: ClassComparisonItem[];
  sample_size: number;
}

// 辩论报告（学生端报告查看接口 /api/student/reports/{debate_id}）
export interface DebateReport {
  debate_id: string;
  topic: string;
  start_time: string | null;
  end_time: string | null;
  duration: number;
  participants: Array<{
    user_id: string;
    name: string;
    role: string;
    stance: string;
    is_ai?: boolean;
    final_score: {
      logic_score: number;
      argument_score: number;
      response_score: number;
      persuasion_score: number;
      teamwork_score: number;
      overall_score: number;
      speech_count: number;
      total_duration?: number;
    };
  }>;
  speeches: Array<{
    id: string;
    speaker_type?: string;
    speaker_role?: string;
    speaker_name?: string;
    stance?: string | null;
    role?: string | null;
    phase: string;
    content: string;
    duration: number;
    timestamp: string;
    score: {
      logic_score: number;
      argument_score: number;
      response_score: number;
      persuasion_score: number;
      teamwork_score: number;
      overall_score: number;
      feedback: string;
    } | null;
  }>;
  statistics: Record<string, unknown>;
  winner: string;
}

// 知识库
export interface KBSource {
  document_id: string;
  document_name: string;
  excerpt: string;
  similarity_score: number;
}

export interface KBAnswer {
  answer: string;
  sources: KBSource[];
  used_kb: boolean;
}

export interface Conversation {
  id: string;
  question: string;
  answer: string;
  sources: KBSource[];
  created_at: string;
}

export interface KBSession {
  session_id: string;
  title: string;
  updated_at: string;
}

export interface KBDocument {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  upload_status: string;
  uploaded_by: string;
  uploaded_at: string;
  processed_at?: string;
}

export interface KBDocumentList {
  documents: KBDocument[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ==================== Student Service ====================

class StudentService {
  private static availableDebatesCache: { data: Debate[]; ts: number } | null = null;
  private static availableDebatesInFlight: Promise<Debate[]> | null = null;
  private static readonly availableDebatesCacheTtlMs = 1000;

  // ==================== 个人信息 ====================

  /**
   * 获取个人资料
   */
  static async getProfile(): Promise<StudentProfile> {
    try {
      return await api.get<StudentProfile>('/api/student/profile');
    } catch (error) {
      console.error('[StudentService] Get profile failed:', error);
      throw error;
    }
  }

  /**
   * 更新个人资料
   */
  static async updateProfile(params: UpdateProfileParams): Promise<StudentProfile> {
    try {
      return await api.put<StudentProfile>('/api/student/profile', params);
    } catch (error) {
      console.error('[StudentService] Update profile failed:', error);
      throw error;
    }
  }

  // ==================== 能力评估 ====================

  /**
   * 提交能力评估
   */
  static async submitAssessment(params: AssessmentParams): Promise<AssessmentResult> {
    try {
      return await api.post<AssessmentResult>('/api/student/assessment', params);
    } catch (error) {
      console.error('[StudentService] Submit assessment failed:', error);
      throw error;
    }
  }

  /**
   * 获取能力评估结果
   */
  static async getAssessment(): Promise<AssessmentResult | null> {
    try {
      return await api.get<AssessmentResult | null>('/api/student/assessment');
    } catch (error) {
      console.error('[StudentService] Get assessment failed:', error);
      throw error;
    }
  }

  // ==================== 辩论参与 ====================

  /**
   * 获取可参与的辩论列表
   */
  static async getAvailableDebates(options?: { force?: boolean }): Promise<Debate[]> {
    try {
      const force = options?.force === true;
      const now = Date.now();

      if (!force && this.availableDebatesCache && now - this.availableDebatesCache.ts < this.availableDebatesCacheTtlMs) {
        return this.availableDebatesCache.data;
      }

      if (this.availableDebatesInFlight) {
        return await this.availableDebatesInFlight;
      }

      this.availableDebatesInFlight = (async () => {
        try {
          const data = await api.get<Debate[]>('/api/student/debates');
          this.availableDebatesCache = { data, ts: Date.now() };
          return data;
        } finally {
          this.availableDebatesInFlight = null;
        }
      })();

      return await this.availableDebatesInFlight;
    } catch (error) {
      console.error('[StudentService] Get available debates failed:', error);
      throw error;
    }
  }

  static async getDebateParticipants(debateId: string): Promise<DebateParticipant[]> {
    try {
      return await api.get<DebateParticipant[]>(`/api/student/debates/${debateId}/participants`);
    } catch (error) {
      console.error('[StudentService] Get debate participants failed:', error);
      throw error;
    }
  }

  /**
   * 通过邀请码加入辩论
   */
  static async joinDebate(params: JoinDebateParams): Promise<Debate> {
    try {
      return await api.post<Debate>('/api/student/debates/join', params);
    } catch (error) {
      console.error('[StudentService] Join debate failed:', error);
      throw error;
    }
  }

  // ==================== 历史记录 ====================

  /**
   * 获取辩论历史记录
   */
  static async getHistory(limit: number = 20, offset: number = 0): Promise<DebateHistory> {
    try {
      return await api.get<DebateHistory>('/api/student/history', {
        params: { limit, offset },
      });
    } catch (error) {
      console.error('[StudentService] Get history failed:', error);
      throw error;
    }
  }

  /**
   * 筛选历史记录
   */
  static async filterHistory(params: FilterHistoryParams): Promise<DebateHistory> {
    try {
      return await api.get<DebateHistory>('/api/student/history/filter', {
        params,
      });
    } catch (error) {
      console.error('[StudentService] Filter history failed:', error);
      throw error;
    }
  }

  /**
   * 获取辩论详情
   */
  static async getDebateDetails(debateId: string): Promise<DebateDetails> {
    try {
      return await api.get<DebateDetails>(`/api/student/history/${debateId}`);
    } catch (error) {
      console.error('[StudentService] Get debate details failed:', error);
      throw error;
    }
  }

  // ==================== 数据分析 ====================

  /**
   * 获取学生数据分析
   */
  static async getAnalytics(): Promise<StudentAnalytics> {
    try {
      return await api.get<StudentAnalytics>('/api/student/analytics');
    } catch (error) {
      console.error('[StudentService] Get analytics failed:', error);
      throw error;
    }
  }

  /**
   * 获取成长趋势
   */
  static async getGrowthTrend(limit: number = 10): Promise<GrowthTrend> {
    try {
      return await api.get<GrowthTrend>('/api/student/analytics/growth', {
        params: { limit },
      });
    } catch (error) {
      console.error('[StudentService] Get growth trend failed:', error);
      throw error;
    }
  }

  // ==================== 成就系统 ====================

  /**
   * 获取成就列表
   */
  static async getAchievements(): Promise<Achievement[]> {
    try {
      return await api.get<Achievement[]>('/api/student/achievements/v2');
    } catch (error) {
      console.error('[StudentService] Get achievements failed:', error);
      throw error;
    }
  }

  /**
   * 检查并解锁新成就
   */
  static async checkAchievements(): Promise<{ newly_unlocked: Achievement[]; count: number }> {
    try {
      return await api.post<{ newly_unlocked: Achievement[]; count: number }>(
        '/api/student/achievements/check/v2'
      );
    } catch (error) {
      console.error('[StudentService] Check achievements failed:', error);
      throw error;
    }
  }

  // ==================== 对比分析 ====================

  static async getClassComparison(options?: { metric?: string; top?: number }): Promise<ClassComparison> {
    try {
      const metric = options?.metric || 'overall';
      const top = typeof options?.top === 'number' ? options.top : 10;

      return await api.get<ClassComparison>('/api/student/comparison/class', {
        params: { metric, top },
      });
    } catch (error) {
      console.error('[StudentService] Get class comparison failed:', error);
      throw error;
    }
  }

  // ==================== 报告查看 ====================

  /**
   * 获取辩论报告
   */
  static async getReport(debateId: string): Promise<DebateReport> {
    try {
      return await api.get<DebateReport>(`/api/student/reports/${debateId}`);
    } catch (error) {
      console.error('[StudentService] Get report failed:', error);
      throw error;
    }
  }

  /**
   * 导出PDF报告
   */
  static async exportReportPDF(debateId: string): Promise<void> {
    try {
      const response = await api.get<Blob>(`/api/student/reports/${debateId}/export/pdf`, {
        responseType: 'blob',
      });

      // 创建下载链接
      const url = window.URL.createObjectURL(response as any);
      const link = document.createElement('a');
      link.href = url;
      link.download = `debate_report_${debateId}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('[StudentService] Export PDF failed:', error);
      throw error;
    }
  }

  /**
   * 导出Excel报告
   */
  static async exportReportExcel(debateId: string): Promise<void> {
    try {
      const response = await api.get<Blob>(`/api/student/reports/${debateId}/export/excel`, {
        responseType: 'blob',
      });

      // 创建下载链接
      const url = window.URL.createObjectURL(response as any);
      const link = document.createElement('a');
      link.href = url;
      link.download = `debate_report_${debateId}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('[StudentService] Export Excel failed:', error);
      throw error;
    }
  }

  /**
   * 发送报告邮件
   */
  static async sendReportEmail(debateId: string): Promise<void> {
    try {
      await api.post(`/api/student/reports/${debateId}/send-email`);
    } catch (error) {
      console.error('[StudentService] Send report email failed:', error);
      throw error;
    }
  }

  // ==================== 知识库 ====================

  /**
   * 向知识库提问
   */
  static async askKBQuestion(question: string, sessionId: string): Promise<KBAnswer> {
    try {
      return await api.post<KBAnswer>('/api/student/kb/ask', {
        question,
        session_id: sessionId,
      });
    } catch (error) {
      console.error('[StudentService] Ask KB question failed:', error);
      throw error;
    }
  }

  /**
   * 获取知识库对话历史
   */
  static async getKBConversationHistory(sessionId: string, limit: number = 20): Promise<Conversation[]> {
    try {
      const response = await api.get<{ conversations: Conversation[], count: number }>(`/api/student/kb/conversations/${sessionId}`, {
        params: { limit },
      });
      // The API returns { code, message, data: { conversations: [], count: 0 } }
      // The api.get interceptor unwraps 'data', so we get { conversations: [], count: 0 }
      // We need to return the conversations array
      return response.conversations || [];
    } catch (error) {
      console.error('[StudentService] Get KB conversation history failed:', error);
      throw error;
    }
  }

  /**
   * 获取知识库会话列表
   */
  static async getKBSessions(): Promise<KBSession[]> {
    try {
      return await api.get<KBSession[]>('/api/student/kb/sessions');
    } catch (error) {
      console.error('[StudentService] Get KB sessions failed:', error);
      throw error;
    }
  }

  /**
   * 获取知识库文档列表
   */
  static async getKBDocuments(page: number = 1, pageSize: number = 20): Promise<KBDocumentList> {
    try {
      return await api.get<KBDocumentList>('/api/student/kb/documents', {
        params: { page, page_size: pageSize },
      });
    } catch (error) {
      console.error('[StudentService] Get KB documents failed:', error);
      throw error;
    }
  }
}

export default StudentService;
