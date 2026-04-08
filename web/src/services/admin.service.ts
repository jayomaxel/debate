/**
 * Admin Service
 * 管理员服务 - 处理管理员相关的API调用
 */

import { api } from '../lib/api';

// ==================== 接口定义 ====================

export interface Class {
  id: string;
  name: string;
  code: string;
  teacher_id: string;
  teacher_name: string;
  student_count: number;
  created_at: string;
}

export interface ClassCreate {
  name: string;
  teacher_id: string;
}

export interface ClassUpdate {
  name?: string;
  teacher_id?: string;
}

export interface ModelConfig {
  id: string;
  model_name: string;
  api_endpoint: string;
  api_key: string;
  temperature: number;
  max_tokens: number;
  parameters: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface ModelConfigUpdate {
  model_name?: string;
  api_endpoint?: string;
  api_key?: string;
  temperature?: number;
  max_tokens?: number;
  parameters?: Record<string, any>;
}

export interface AsrConfig {
  id: string;
  model_name: string;
  api_endpoint: string;
  api_key: string;
  parameters: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface AsrConfigUpdate {
  model_name?: string;
  api_endpoint?: string;
  api_key?: string;
  parameters?: Record<string, any>;
}

export interface TtsConfig {
  id: string;
  model_name: string;
  api_endpoint: string;
  api_key: string;
  parameters: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface TtsConfigUpdate {
  model_name?: string;
  api_endpoint?: string;
  api_key?: string;
  parameters?: Record<string, any>;
}

export interface VectorConfig {
  id: string;
  model_name: string;
  api_endpoint: string;
  api_key: string;
  embedding_dimension: number;
  parameters: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface VectorConfigUpdate {
  model_name?: string;
  api_endpoint?: string;
  api_key?: string;
  embedding_dimension?: number;
  parameters?: Record<string, any>;
}

export interface CozeConfig {
  id: string;
  debater_1_bot_id: string;
  debater_2_bot_id: string;
  debater_3_bot_id: string;
  debater_4_bot_id: string;
  judge_bot_id: string;
  mentor_bot_id: string;
  api_token: string;
  parameters: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface CozeConfigUpdate {
  debater_1_bot_id?: string;
  debater_2_bot_id?: string;
  debater_3_bot_id?: string;
  debater_4_bot_id?: string;
  judge_bot_id?: string;
  mentor_bot_id?: string;
  api_token?: string;
  parameters?: Record<string, any>;
}

export interface EmailConfig {
  id: string;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_password: string;
  from_email: string;
  auto_send_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmailConfigUpdate {
  smtp_host?: string;
  smtp_port?: number;
  smtp_user?: string;
  smtp_password?: string;
  from_email?: string;
  auto_send_enabled?: boolean;
}

export interface User {
  id: string;
  account: string;
  name: string;
  email: string;
  phone?: string;
  user_type: string;
  student_id?: string;
  class_id?: string;
  class_name?: string; // 班级名称
  created_at: string;
}

export interface UserUpdate {
  account?: string;
  name?: string;
  email?: string;
  phone?: string | null;
  student_id?: string | null;
  class_id?: string | null;
}

export interface PasswordChangeParams {
  current_password: string;
  new_password: string;
}

export interface KBDocument {
  id: string;
  filename: string;
  file_path: string;
  file_type: string;
  file_size: number;
  upload_status: 'pending' | 'processing' | 'completed' | 'failed';
  error_message?: string;
  uploaded_by: string;
  uploaded_at: string;
  processed_at?: string;
}

export interface KBDocumentListResponse {
  documents: KBDocument[];
  total: number;
  page: number;
  page_size: number;
}

// ==================== Admin Service ====================

class AdminService {
  private static configCache = new Map<string, unknown>();

  private static cloneConfig<T>(value: T): T {
    if (value === null || value === undefined) {
      return value;
    }
    return JSON.parse(JSON.stringify(value)) as T;
  }

  private static getConfigCache<T>(key: string): T | null {
    if (!this.configCache.has(key)) {
      return null;
    }
    return this.cloneConfig(this.configCache.get(key) as T);
  }

  private static setConfigCache<T>(key: string, value: T): T {
    const clonedValue = this.cloneConfig(value);
    this.configCache.set(key, clonedValue);
    return this.cloneConfig(clonedValue);
  }
  /**
   * 获取所有班级
   */
  static async getAllClasses(): Promise<Class[]> {
    try {
      const response = await api.get<Class[]>('/api/admin/classes');
      return response;
    } catch (error) {
      console.error('[AdminService] Get all classes failed:', error);
      throw error;
    }
  }

  /**
   * 创建班级
   */
  static async createClass(classData: ClassCreate): Promise<Class> {
    try {
      const response = await api.post<Class>('/api/admin/classes', classData);
      return response;
    } catch (error) {
      console.error('[AdminService] Create class failed:', error);
      throw error;
    }
  }

  /**
   * 更新班级
   */
  static async updateClass(classId: string, classData: ClassUpdate): Promise<Class> {
    try {
      const response = await api.put<Class>(`/api/admin/classes/${classId}`, classData);
      return response;
    } catch (error) {
      console.error('[AdminService] Update class failed:', error);
      throw error;
    }
  }

  /**
   * 删除班级
   */
  static async deleteClass(classId: string): Promise<void> {
    try {
      await api.delete(`/api/admin/classes/${classId}`);
    } catch (error) {
      console.error('[AdminService] Delete class failed:', error);
      throw error;
    }
  }

  /**
   * 获取模型配置
   */
  static async getModelConfig(): Promise<ModelConfig> {
    try {
      const cachedConfig = this.getConfigCache<ModelConfig>('model_config');
      if (cachedConfig) {
        return cachedConfig;
      }
      const response = await api.get<ModelConfig>('/api/admin/config/models');
      return this.setConfigCache('model_config', response);
    } catch (error) {
      console.error('[AdminService] Get model config failed:', error);
      throw error;
    }
  }

  /**
   * 更新模型配置
   */
  static async updateModelConfig(config: ModelConfigUpdate): Promise<ModelConfig> {
    try {
      const response = await api.post<ModelConfig>('/api/admin/config/models', config);
      return this.setConfigCache('model_config', response);
    } catch (error) {
      console.error('[AdminService] Update model config failed:', error);
      throw error;
    }
  }

  static async getAsrConfig(): Promise<AsrConfig> {
    try {
      const cachedConfig = this.getConfigCache<AsrConfig>('asr_config');
      if (cachedConfig) {
        return cachedConfig;
      }
      const response = await api.get<AsrConfig>('/api/admin/config/asr');
      return this.setConfigCache('asr_config', response);
    } catch (error) {
      console.error('[AdminService] Get ASR config failed:', error);
      throw error;
    }
  }

  static async updateAsrConfig(config: AsrConfigUpdate): Promise<AsrConfig> {
    try {
      const response = await api.post<AsrConfig>('/api/admin/config/asr', config);
      return this.setConfigCache('asr_config', response);
    } catch (error) {
      console.error('[AdminService] Update ASR config failed:', error);
      throw error;
    }
  }

  static async getTtsConfig(): Promise<TtsConfig> {
    try {
      const cachedConfig = this.getConfigCache<TtsConfig>('tts_config');
      if (cachedConfig) {
        return cachedConfig;
      }
      const response = await api.get<TtsConfig>('/api/admin/config/tts');
      return this.setConfigCache('tts_config', response);
    } catch (error) {
      console.error('[AdminService] Get TTS config failed:', error);
      throw error;
    }
  }

  static async updateTtsConfig(config: TtsConfigUpdate): Promise<TtsConfig> {
    try {
      const response = await api.post<TtsConfig>('/api/admin/config/tts', config);
      return this.setConfigCache('tts_config', response);
    } catch (error) {
      console.error('[AdminService] Update TTS config failed:', error);
      throw error;
    }
  }

  /**
   * 获取向量配置
   */
  static async getVectorConfig(): Promise<VectorConfig> {
    try {
      const cachedConfig = this.getConfigCache<VectorConfig>('vector_config');
      if (cachedConfig) {
        return cachedConfig;
      }
      const response = await api.get<VectorConfig>('/api/admin/config/vector');
      return this.setConfigCache('vector_config', response);
    } catch (error) {
      console.error('[AdminService] Get Vector config failed:', error);
      throw error;
    }
  }

  /**
   * 更新向量配置
   */
  static async updateVectorConfig(config: VectorConfigUpdate): Promise<VectorConfig> {
    try {
      const response = await api.post<VectorConfig>('/api/admin/config/vector', config);
      return this.setConfigCache('vector_config', response);
    } catch (error) {
      console.error('[AdminService] Update Vector config failed:', error);
      throw error;
    }
  }

  /**
   * 获取Coze配置
   */
  static async getCozeConfig(): Promise<CozeConfig> {
    try {
      const cachedConfig = this.getConfigCache<CozeConfig>('coze_config');
      if (cachedConfig) {
        return cachedConfig;
      }
      const response = await api.get<CozeConfig>('/api/admin/config/coze');
      return this.setConfigCache('coze_config', response);
    } catch (error) {
      console.error('[AdminService] Get Coze config failed:', error);
      throw error;
    }
  }

  /**
   * 更新Coze配置
   */
  static async updateCozeConfig(config: CozeConfigUpdate): Promise<CozeConfig> {
    try {
      const response = await api.post<CozeConfig>('/api/admin/config/coze', config);
      return this.setConfigCache('coze_config', response);
    } catch (error) {
      console.error('[AdminService] Update Coze config failed:', error);
      throw error;
    }
  }

  static async getEmailConfig(): Promise<EmailConfig> {
    try {
      const cachedConfig = this.getConfigCache<EmailConfig>('email_config');
      if (cachedConfig) {
        return cachedConfig;
      }
      const response = await api.get<EmailConfig>('/api/admin/config/email');
      return this.setConfigCache('email_config', response);
    } catch (error) {
      console.error('[AdminService] Get Email config failed:', error);
      throw error;
    }
  }

  static async updateEmailConfig(config: EmailConfigUpdate): Promise<EmailConfig> {
    try {
      const response = await api.post<EmailConfig>('/api/admin/config/email', config);
      return this.setConfigCache('email_config', response);
    } catch (error) {
      console.error('[AdminService] Update Email config failed:', error);
      throw error;
    }
  }

  static async testEmailConnection(): Promise<void> {
    try {
      await api.post('/api/admin/config/email/test');
    } catch (error) {
      console.error('[AdminService] Test Email connection failed:', error);
      throw error;
    }
  }

  /**
   * 获取用户列表
   */
  static async getUsers(role?: 'teacher' | 'student'): Promise<User[]> {
    try {
      const params = role ? { role } : {};
      const response = await api.get<User[]>('/api/admin/users', { params });
      return response;
    } catch (error) {
      console.error('[AdminService] Get users failed:', error);
      throw error;
    }
  }

  /**
   * 获取用户详情
   */
  static async getUserById(userId: string): Promise<User> {
    try {
      const response = await api.get<User>(`/api/admin/users/${userId}`);
      return response;
    } catch (error) {
      console.error('[AdminService] Get user by ID failed:', error);
      throw error;
    }
  }

  static async updateUser(userId: string, userData: UserUpdate): Promise<User> {
    try {
      return await api.put<User>(`/api/admin/users/${userId}`, userData);
    } catch (error) {
      console.error('[AdminService] Update user failed:', error);
      throw error;
    }
  }

  /**
   * 修改管理员密码
   */
  static async changePassword(params: PasswordChangeParams): Promise<void> {
    try {
      await api.put('/api/admin/password', params);
    } catch (error) {
      console.error('[AdminService] Change password failed:', error);
      throw error;
    }
  }

  /**
   * 获取知识库文档列表（分页）
   */
  static async listKBDocuments(page: number = 1, pageSize: number = 20): Promise<KBDocumentListResponse> {
    try {
      const response = await api.get<KBDocumentListResponse>('/api/admin/kb/documents', {
        params: { page, page_size: pageSize }
      });
      return response;
    } catch (error) {
      console.error('[AdminService] List KB documents failed:', error);
      throw error;
    }
  }

  /**
   * 上传知识库文档
   */
  static async uploadKBDocument(file: File): Promise<KBDocument> {
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await api.post<KBDocument>('/api/admin/kb/documents', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      return response;
    } catch (error) {
      console.error('[AdminService] Upload KB document failed:', error);
      throw error;
    }
  }

  /**
   * 删除知识库文档
   */
  static async deleteKBDocument(documentId: string): Promise<void> {
    try {
      await api.delete(`/api/admin/kb/documents/${documentId}`);
    } catch (error) {
      console.error('[AdminService] Delete KB document failed:', error);
      throw error;
    }
  }
}

export default AdminService;
