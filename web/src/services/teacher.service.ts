/**
 * Teacher Service
 * 处理教师端相关 API 调用
 */

import { api } from '../lib/api';

export interface DebateGroupingItem {
  user_id: string;
  name: string;
  role: 'debater_1' | 'debater_2' | 'debater_3' | 'debater_4';
  role_reason?: string | null;
}

export interface TeacherDebate {
  id: string;
  topic: string;
  description?: string;
  duration: number;
  status: 'draft' | 'published' | 'in_progress' | 'completed';
  invitation_code: string;
  created_at: string;
  class_id?: string;
  student_ids?: string[];
  grouping?: DebateGroupingItem[];
}

export interface Class {
  id: string;
  name: string;
  code: string;
  teacher_id: string;
  student_count: number;
  created_at: string;
}

export interface CreateClassParams {
  name: string;
}

export interface Student {
  id: string;
  name: string;
  account: string;
  email?: string;
  student_id?: string;
  class_id: string;
  created_at: string;
}

export interface AddStudentParams {
  account: string;
  password: string;
  name: string;
  class_id: string;
  email?: string;
  student_id?: string;
}

export interface CreateDebateParams {
  class_id: string;
  topic: string;
  duration: number;
  description?: string;
  student_ids?: string[];
  status?: 'draft' | 'published';
}

export interface TeacherDashboardStats {
  managed_students: number;
  participating_students: number;
  active_debates: number;
  completed_debates: number;
  today_debates: number;
  total_debates: number;
  updated_at: string;
}

export type ReservationStatus =
  | 'draft'
  | 'scheduled'
  | 'checkin_open'
  | 'waiting'
  | 'in_progress'
  | 'completed'
  | 'cancelled';
export type ReservationInvitationStatus = 'pending' | 'accepted' | 'rejected' | 'expired';
export type ReservationCheckinStatus = 'not_checked_in' | 'checked_in' | 'absent';
export type ReservationVisibility = 'public' | 'private';

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface TeacherReservationInvitation {
  invitation_id: string;
  student_id: string;
  invited_by_teacher_id: string;
  assigned_role?: 'debater_1' | 'debater_2' | 'debater_3' | 'debater_4' | null;
  assigned_stance?: 'positive' | 'negative' | null;
  role?: 'debater_1' | 'debater_2' | 'debater_3' | 'debater_4' | null;
  stance?: 'positive' | 'negative' | null;
  is_designated_moderator: boolean;
  is_backup_moderator: boolean;
  read_status: 'unread' | 'read';
  response_status: ReservationInvitationStatus;
  attendance_status: ReservationCheckinStatus;
  expires_at?: string | null;
  revoked_at?: string | null;
  read_at?: string | null;
  responded_at?: string | null;
  checked_in_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TeacherReservation {
  reservation_id: string;
  room_id: string;
  topic: string;
  description?: string | null;
  duration: number;
  class_id: string;
  class_name: string;
  scheduled_start_time?: string | null;
  checkin_open_time?: string | null;
  checkin_close_time?: string | null;
  visibility: ReservationVisibility;
  host_user_id?: string | null;
  status: ReservationStatus;
  room_status: 'waiting' | 'full' | 'ongoing' | 'finished' | 'cancelled';
  invitations: Record<string, TeacherReservationInvitation>;
  invited_count: number;
  accepted_count: number;
  rejected_count: number;
  checked_in_count: number;
  revoked_count: number;
  cancelled_at?: string | null;
  cancel_reason?: string | null;
}

export interface CreateReservationParams {
  class_id: string;
  topic: string;
  duration: number;
  description?: string;
  scheduled_start_time: string;
  checkin_open_time?: string;
  checkin_close_time?: string;
  student_ids: string[];
  visibility: ReservationVisibility;
  password?: string;
  host_user_id?: string;
}

export interface UpdateReservationParams {
  topic?: string;
  duration?: number;
  description?: string;
  scheduled_start_time?: string;
  checkin_open_time?: string;
  checkin_close_time?: string;
  student_ids?: string[];
  visibility?: ReservationVisibility;
  password?: string;
  host_user_id?: string;
}

export interface TeacherReservationQuery {
  class_id?: string;
  status?: ReservationStatus | 'all';
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export interface TeacherDebateSupportDocument {
  id: string;
  filename: string;
  file_type: string;
  embedding_status: 'pending' | 'processing' | 'completed' | 'failed';
  uploaded_at: string | null;
}

export interface OpenAIConfig {
  api_key: string;
  base_url: string;
  model_name: string;
  temperature: number;
  max_tokens: number;
}

export interface CozeConfig {
  api_key: string;
  base_url: string;
  ai_debater_1_bot_id: string;
  ai_debater_2_bot_id: string;
  ai_debater_3_bot_id: string;
  ai_debater_4_bot_id: string;
  judge_bot_id: string;
  mentor_bot_id: string;
}

export interface ConfigData {
  openai: OpenAIConfig | null;
  coze: CozeConfig | null;
}

class TeacherService {
  static async createClass(params: CreateClassParams): Promise<Class> {
    try {
      return await api.post<Class>('/api/teacher/classes', params);
    } catch (error) {
      console.error('[TeacherService] Create class failed:', error);
      throw error;
    }
  }

  static async getClasses(): Promise<Class[]> {
    try {
      return await api.get<Class[]>('/api/teacher/classes');
    } catch (error) {
      console.error('[TeacherService] Get classes failed:', error);
      throw error;
    }
  }

  static async addStudent(params: AddStudentParams): Promise<Student> {
    try {
      return await api.post<Student>('/api/teacher/students', params);
    } catch (error) {
      console.error('[TeacherService] Add student failed:', error);
      throw error;
    }
  }

  static async getStudents(classId?: string): Promise<Student[]> {
    try {
      return await api.get<Student[]>('/api/teacher/students', {
        params: classId ? { class_id: classId } : undefined,
      });
    } catch (error) {
      console.error('[TeacherService] Get students failed:', error);
      throw error;
    }
  }

  static async createDebate(params: CreateDebateParams): Promise<TeacherDebate> {
    try {
      return await api.post<TeacherDebate>('/api/teacher/debates', params);
    } catch (error) {
      console.error('[TeacherService] Create debate failed:', error);
      throw error;
    }
  }

  static async updateDebate(debateId: string, params: CreateDebateParams): Promise<TeacherDebate> {
    try {
      return await api.put<TeacherDebate>(`/api/teacher/debates/${debateId}`, params);
    } catch (error) {
      console.error('[TeacherService] Update debate failed:', error);
      throw error;
    }
  }

  static async getDebate(debateId: string): Promise<TeacherDebate> {
    try {
      return await api.get<TeacherDebate>(`/api/teacher/debates/${debateId}`);
    } catch (error) {
      console.error('[TeacherService] Get debate failed:', error);
      throw error;
    }
  }

  static async getDebates(classId?: string): Promise<TeacherDebate[]> {
    try {
      return await api.get<TeacherDebate[]>('/api/teacher/debates', {
        params: classId ? { class_id: classId } : undefined,
      });
    } catch (error) {
      console.error('[TeacherService] Get debates failed:', error);
      throw error;
    }
  }

  static async getDashboardStats(): Promise<TeacherDashboardStats> {
    try {
      return await api.get<TeacherDashboardStats>('/api/teacher/dashboard');
    } catch (error) {
      console.error('[TeacherService] Get dashboard stats failed:', error);
      throw error;
    }
  }

  static async createReservationDebate(params: CreateReservationParams): Promise<TeacherReservation> {
    try {
      return await api.post<TeacherReservation>('/api/teacher/reservations', params);
    } catch (error) {
      console.error('[TeacherService] Create reservation debate failed:', error);
      throw error;
    }
  }

  static async updateReservationDebate(
    reservationId: string,
    params: UpdateReservationParams
  ): Promise<TeacherReservation> {
    try {
      return await api.put<TeacherReservation>(`/api/teacher/reservations/${reservationId}`, params);
    } catch (error) {
      console.error('[TeacherService] Update reservation debate failed:', error);
      throw error;
    }
  }

  static async cancelReservationDebate(
    reservationId: string,
    cancelReason?: string
  ): Promise<TeacherReservation> {
    try {
      return await api.post<TeacherReservation>(`/api/teacher/reservations/${reservationId}/cancel`, {
        cancel_reason: cancelReason,
      });
    } catch (error) {
      console.error('[TeacherService] Cancel reservation debate failed:', error);
      throw error;
    }
  }

  static async getReservationDebates(
    params: TeacherReservationQuery = {}
  ): Promise<PaginatedResponse<TeacherReservation>> {
    try {
      const { status, ...rest } = params;
      return await api.get<PaginatedResponse<TeacherReservation>>('/api/teacher/reservations', {
        params: {
          ...rest,
          ...(status && status !== 'all' ? { status } : {}),
        },
      });
    } catch (error) {
      console.error('[TeacherService] Get reservation debates failed:', error);
      throw error;
    }
  }

  static async getReservationDetail(reservationId: string): Promise<TeacherReservation> {
    try {
      return await api.get<TeacherReservation>(`/api/teacher/reservations/${reservationId}`);
    } catch (error) {
      console.error('[TeacherService] Get reservation detail failed:', error);
      throw error;
    }
  }

  static async listDebateSupportDocuments(debateId: string): Promise<TeacherDebateSupportDocument[]> {
    try {
      return await api.get<TeacherDebateSupportDocument[]>(
        `/api/teacher/debates/${debateId}/support-documents`
      );
    } catch (error) {
      console.error('[TeacherService] List debate support documents failed:', error);
      throw error;
    }
  }

  static async uploadDebateSupportDocument(
    debateId: string,
    file: File
  ): Promise<TeacherDebateSupportDocument> {
    try {
      const formData = new FormData();
      formData.append('file', file);
      return await api.post<TeacherDebateSupportDocument>(
        `/api/teacher/debates/${debateId}/support-documents`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );
    } catch (error) {
      console.error('[TeacherService] Upload debate support document failed:', error);
      throw error;
    }
  }

  static async deleteDebateSupportDocument(
    debateId: string,
    documentId: string
  ): Promise<void> {
    try {
      await api.delete<void>(
        `/api/teacher/debates/${debateId}/support-documents/${documentId}`
      );
    } catch (error) {
      console.error('[TeacherService] Delete debate support document failed:', error);
      throw error;
    }
  }
}

export default TeacherService;
