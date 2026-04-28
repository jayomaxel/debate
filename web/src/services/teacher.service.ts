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
