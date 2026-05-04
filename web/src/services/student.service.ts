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
    avatar?: string | null;
    avatar_url?: string | null;
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

export type DebateVisibility = 'public' | 'private';
export type LobbyRoomStatus = 'waiting' | 'full' | 'ongoing' | 'finished' | 'cancelled';
export type DebateMode = 'teacher_assigned' | 'student_lobby' | 'teacher_reserved';
export type ReservationStatus =
  | 'draft'
  | 'scheduled'
  | 'checkin_open'
  | 'waiting'
  | 'in_progress'
  | 'completed'
  | 'cancelled';
export type ReservationInvitationStatus = 'pending' | 'accepted' | 'rejected' | 'expired';
export type ReservationReadStatus = 'unread' | 'read';
export type ReservationCheckinStatus = 'not_checked_in' | 'checked_in' | 'absent';
export type LobbySort = 'latest' | 'hot' | 'start_soon';

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface LobbyRoomMember {
  user_id: string | null;
  name: string;
  avatar?: string | null;
  role: 'debater_1' | 'debater_2' | 'debater_3' | 'debater_4';
  stance?: 'positive' | 'negative' | null;
  role_reason?: string | null;
  seat_order?: number | null;
  is_room_owner?: boolean;
  can_speak?: boolean;
  can_moderate?: boolean;
  joined_at?: string | null;
  membership_status?: 'joined' | 'temporarily_left' | 'permanently_left' | 'kicked' | 'not_joined';
  presence_status?: 'online_in_room' | 'online_out_of_room_page' | 'offline' | 'not_in_room';
  online_status?: 'online_in_room' | 'offline';
  ready_status?: 'not_ready' | 'checklist_in_progress' | 'ready';
}

export interface LobbyRoomPermissions {
  role?: LobbyRoomMember['role'] | null;
  can_speak: boolean;
  can_moderate: boolean;
  is_joined: boolean;
  membership_status?: LobbyRoomMember['membership_status'];
  presence_status?: LobbyRoomMember['presence_status'];
  ready_status?: LobbyRoomMember['ready_status'];
}

export interface LobbyRoom {
  room_id: string;
  debate_id: string;
  topic: string;
  room_name: string;
  description?: string | null;
  current_count: number;
  capacity: number;
  visibility: DebateVisibility;
  has_password: boolean;
  host_user_id?: string | null;
  host_name?: string | null;
  mode: DebateMode;
  room_source?: 'teacher_created' | 'student_created';
  config_source?: 'teacher_preset' | 'room_owner_preset';
  preparation_page_type?: 'teacher_reserved_preparation' | 'student_lobby_preparation' | string;
  status: LobbyRoomStatus;
  scheduled_start_time?: string | null;
  allow_spectators: boolean;
  created_at?: string | null;
  members?: LobbyRoomMember[];
  current_user_permissions?: LobbyRoomPermissions;
  available_roles?: LobbyRoomMember['role'][];
  can_join?: boolean;
  join_block_reason?: string | null;
  is_current_user_joined?: boolean;
  current_user_role?: LobbyRoomMember['role'] | null;
  joined?: boolean;
  participant_role?: LobbyRoomMember['role'];
  is_moderator?: boolean;
}

export interface LobbyRoomQuery {
  keyword?: string;
  visibility?: DebateVisibility | 'all';
  status?: LobbyRoomStatus | 'all';
  sort?: LobbySort;
  page?: number;
  page_size?: number;
}

export interface CreateLobbyRoomParams {
  room_name?: string;
  topic: string;
  description?: string;
  capacity: number;
  visibility: DebateVisibility;
  password?: string;
  allow_spectators: boolean;
}

export interface JoinLobbyRoomParams {
  password?: string;
}

export interface LeaveLobbyRoomParams {
  permanent?: boolean;
}

export interface StudentReservation {
  reservation_id: string;
  room_id: string;
  debate_id: string;
  topic: string;
  description?: string | null;
  duration: number;
  teacher_id: string;
  teacher_name?: string | null;
  scheduled_start_time?: string | null;
  checkin_open_time?: string | null;
  checkin_close_time?: string | null;
  role?: LobbyRoomMember['role'] | null;
  invitation_status: ReservationInvitationStatus;
  read_status: ReservationReadStatus;
  checkin_status: ReservationCheckinStatus;
  checked_in_at?: string | null;
  status: ReservationStatus;
  room_status: LobbyRoomStatus;
  can_check_in: boolean;
  checkin_block_reason?: string | null;
  room_entry_enabled: boolean;
  checked_in?: boolean;
  participant_role?: LobbyRoomMember['role'];
  can_speak?: boolean;
  can_moderate?: boolean;
}

export interface ReservationReminder {
  reservation_id: string;
  room_id: string;
  topic: string;
  reminder_type: string;
  title: string;
  scheduled_start_time?: string | null;
  minutes_until_start?: number;
  read_status?: ReservationReadStatus;
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
  summary?: string;
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

  private static normalizeApiTimestamp(value?: string): string {
    if (!value || typeof value !== 'string') {
      return value || '';
    }

    if (/[zZ]$|[+-]\d{2}:\d{2}$/.test(value)) {
      return value;
    }

    return `${value}Z`;
  }

  private static normalizeConversation(conversation: Conversation): Conversation {
    return {
      ...conversation,
      created_at: this.normalizeApiTimestamp(conversation.created_at),
    };
  }

  private static normalizeSession(session: KBSession): KBSession {
    return {
      ...session,
      updated_at: this.normalizeApiTimestamp(session.updated_at),
    };
  }

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
      console.debug('[StudentService] Loading debate participants', {
        debateId,
        path: `/api/student/debates/${debateId}/participants`,
      });
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

  // ==================== 匹配大厅与预约 ====================

  static async getLobbyRooms(params: LobbyRoomQuery = {}): Promise<PaginatedResponse<LobbyRoom>> {
    try {
      const { visibility, status, page, page_size, ...rest } = params;
      return await api.get<PaginatedResponse<LobbyRoom>>('/api/student/lobby/rooms', {
        params: {
          ...rest,
          ...(visibility && visibility !== 'all' ? { visibility } : {}),
          ...(status && status !== 'all' ? { status } : {}),
          ...(page ? { page } : {}),
          ...(page_size ? { page_size } : {}),
        },
      });
    } catch (error) {
      console.error('[StudentService] Get lobby rooms failed:', error);
      throw error;
    }
  }

  static async getLobbyRoomDetail(roomId: string): Promise<LobbyRoom> {
    try {
      return await api.get<LobbyRoom>(`/api/student/lobby/rooms/${roomId}`);
    } catch (error) {
      console.error('[StudentService] Get lobby room detail failed:', error);
      throw error;
    }
  }

  static async createLobbyRoom(params: CreateLobbyRoomParams): Promise<LobbyRoom> {
    try {
      return await api.post<LobbyRoom>('/api/student/lobby/rooms', params);
    } catch (error) {
      console.error('[StudentService] Create lobby room failed:', error);
      throw error;
    }
  }

  static async joinLobbyRoom(roomId: string, params: JoinLobbyRoomParams = {}): Promise<LobbyRoom> {
    try {
      return await api.post<LobbyRoom>(`/api/student/lobby/rooms/${roomId}/join`, params);
    } catch (error) {
      console.error('[StudentService] Join lobby room failed:', error);
      throw error;
    }
  }

  static async leaveLobbyRoom(
    roomId: string,
    params: LeaveLobbyRoomParams = {}
  ): Promise<{
    room_id: string;
    debate_id: string;
    membership_status: string;
    presence_status: string;
    room_source?: string;
  }> {
    try {
      return await api.post(`/api/student/lobby/rooms/${roomId}/leave`, params);
    } catch (error) {
      console.error('[StudentService] Leave lobby room failed:', error);
      throw error;
    }
  }

  static async getMyLobbyRooms(): Promise<LobbyRoom[]> {
    try {
      const response = await this.getLobbyRooms({
        sort: 'latest',
        page: 1,
        page_size: 40,
      });
      const candidateRooms = response.items.filter((room) => room.current_count > 0);
      const details = await Promise.allSettled(
        candidateRooms.map((room) => this.getLobbyRoomDetail(room.room_id))
      );
      return details
        .filter((result): result is PromiseFulfilledResult<LobbyRoom> => result.status === 'fulfilled')
        .map((result) => result.value)
        .filter((room) => !!room.current_user_permissions?.is_joined || !!room.is_current_user_joined);
    } catch (error) {
      console.error('[StudentService] Get my lobby rooms failed:', error);
      throw error;
    }
  }

  static async getMyReservations(params: {
    status?: ReservationStatus | 'all';
    include_cancelled?: boolean;
    page?: number;
    page_size?: number;
  } = {}): Promise<PaginatedResponse<StudentReservation>> {
    try {
      const { status, ...rest } = params;
      return await api.get<PaginatedResponse<StudentReservation>>('/api/student/reservations', {
        params: {
          ...rest,
          ...(status && status !== 'all' ? { status } : {}),
        },
      });
    } catch (error) {
      console.error('[StudentService] Get my reservations failed:', error);
      throw error;
    }
  }

  static async respondReservationInvitation(
    reservationId: string,
    action: 'accept' | 'reject'
  ): Promise<StudentReservation> {
    try {
      return await api.post<StudentReservation>(`/api/student/reservations/${reservationId}/respond`, {
        action,
      });
    } catch (error) {
      console.error('[StudentService] Respond reservation invitation failed:', error);
      throw error;
    }
  }

  static async checkInReservation(reservationId: string): Promise<StudentReservation> {
    try {
      return await api.post<StudentReservation>(`/api/student/reservations/${reservationId}/check-in`);
    } catch (error) {
      console.error('[StudentService] Check in reservation failed:', error);
      throw error;
    }
  }

  static async getReservationReminders(options: {
    unread_only?: boolean;
    limit?: number;
  } = {}): Promise<ReservationReminder[]> {
    try {
      return await api.get<ReservationReminder[]>('/api/student/reservation-reminders', {
        params: options,
      });
    } catch (error) {
      console.error('[StudentService] Get reservation reminders failed:', error);
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
      return (response.conversations || []).map((conversation) => (
        this.normalizeConversation(conversation)
      ));
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
      const sessions = await api.get<KBSession[]>('/api/student/kb/sessions');
      return sessions.map((session) => this.normalizeSession(session));
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

  static getKBDocumentPreviewUrl(documentId: string): string {
    return `/api/student/kb/documents/${documentId}/download`;
  }

  static async getKBDocumentBlob(documentId: string): Promise<Blob> {
    return await api.get<Blob>(
      `/api/student/kb/documents/${documentId}/download`,
      {
        responseType: 'blob',
      }
    );
  }

  static async downloadKBDocument(kbDocument: KBDocument): Promise<void> {
    try {
      const response = await this.getKBDocumentBlob(kbDocument.id);

      const url = window.URL.createObjectURL(response as any);
      const link = document.createElement('a');
      link.href = url;
      link.download = kbDocument.filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('[StudentService] Download KB document failed:', error);
      throw error;
    }
  }
}

export default StudentService;
