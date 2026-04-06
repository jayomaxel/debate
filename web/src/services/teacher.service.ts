/**
 * Teacher Service
 * 教师端服务 - 处理教师相关的所有API调用
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

// ==================== 接口定义 ====================

// 班级管理
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

// 学生管理
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

// 辩论管理
export interface CreateDebateParams {
  class_id: string;
  topic: string;
  duration: number;
  description?: string;
  student_ids?: string[];
}

// 配置管理
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

// ==================== Teacher Service ====================

class TeacherService {
  // ==================== 班级管理 ====================

  /**
   * 创建班级
   */
  static async createClass(params: CreateClassParams): Promise<Class> {
    try {
      return await api.post<Class>('/api/teacher/classes', params);
    } catch (error) {
      console.error('[TeacherService] Create class failed:', error);
      throw error;
    }
  }

  /**
   * 获取班级列表
   */
  static async getClasses(): Promise<Class[]> {
    try {
      return await api.get<Class[]>('/api/teacher/classes');
    } catch (error) {
      console.error('[TeacherService] Get classes failed:', error);
      throw error;
    }
  }

  // ==================== 学生管理 ====================

  /**
   * 添加学生
   */
  static async addStudent(params: AddStudentParams): Promise<Student> {
    try {
      return await api.post<Student>('/api/teacher/students', params);
    } catch (error) {
      console.error('[TeacherService] Add student failed:', error);
      throw error;
    }
  }

  /**
   * 获取学生列表
   */
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

  // ==================== 辩论管理 ====================

  /**
   * 创建辩论
   */
  static async createDebate(params: CreateDebateParams): Promise<TeacherDebate> {
    try {
      return await api.post<TeacherDebate>('/api/teacher/debates', params);
    } catch (error) {
      console.error('[TeacherService] Create debate failed:', error);
      throw error;
    }
  }

  /**
   * 更新辩论
   */
  static async updateDebate(debateId: string, params: CreateDebateParams): Promise<TeacherDebate> {
    try {
      return await api.put<TeacherDebate>(`/api/teacher/debates/${debateId}`, params);
    } catch (error) {
      console.error('[TeacherService] Update debate failed:', error);
      throw error;
    }
  }

  /**
   * 获取单个辩论详情
   */
  static async getDebate(debateId: string): Promise<TeacherDebate> {
    try {
      return await api.get<TeacherDebate>(`/api/teacher/debates/${debateId}`);
    } catch (error) {
      console.error('[TeacherService] Get debate failed:', error);
      throw error;
    }
  }

  /**
   * 获取辩论列表
   */
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

  // ==================== 配置管理已迁移至管理员端 ====================
  // 配置管理功能已移至 AdminService
  // 使用 /api/admin/config 路由
}

export default TeacherService;
