import React, { useState } from 'react';
import {
  Users,
  Database,
  Bot,
  BookOpen,
  Shield,
  BrainCircuit,
  LogOut,
  Mic,
  Volume2,
  Layers,
  FileText,
  // Mail
} from 'lucide-react';
import ClassManagement from './admin/class-management';
import ModelConfiguration from './admin/model-configuration';
import AsrConfiguration from './admin/asr-configuration';
import TtsConfiguration from './admin/tts-configuration';
import VectorConfiguration from './admin/vector-configuration';
// import EmailConfiguration from './admin/email-configuration';
import CozeConfiguration from './admin/coze-configuration';
import UserManagement from './admin/user-management';
import DocumentManagement from './admin/document-management';

interface AdminDashboardProps {
  onLogout: () => void;
}

type TabType = 'classes' | 'models' | 'asr' | 'tts' | 'vector' | 'email' | 'coze' | 'users' | 'knowledge';

const AdminDashboard: React.FC<AdminDashboardProps> = ({ onLogout }) => {
  const [activeTab, setActiveTab] = useState<TabType>('classes');

  const menuItems = [
    { id: 'classes' as TabType, label: '班级管理', icon: BookOpen },
    { id: 'knowledge' as TabType, label: '知识库管理', icon: FileText },

    { id: 'models' as TabType, label: '模型配置', icon: Database },
    { id: 'asr' as TabType, label: 'ASR配置', icon: Mic },
    { id: 'tts' as TabType, label: 'TTS配置', icon: Volume2 },
    { id: 'vector' as TabType, label: '向量配置', icon: Layers },
    // { id: 'email' as TabType, label: '邮件配置', icon: Mail },
    { id: 'coze' as TabType, label: 'Coze配置', icon: Bot },
    { id: 'users' as TabType, label: '成员管理', icon: Users },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-slate-50 to-amber-50">
      <div className="flex h-screen">
        {/* 侧边栏 */}
        <div className="w-64 bg-white border-r border-slate-200 shadow-lg relative">
          <div className="p-6 border-b border-slate-200">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-purple-600 to-purple-700 rounded-lg flex items-center justify-center">
                <BrainCircuit className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-slate-900">碳硅之辩</h1>
                <p className="text-xs text-slate-500">人机思辨平台 · 管理员控制台</p>
              </div>
            </div>
          </div>

          <nav className="p-4">
            {menuItems.map((item) => {
              const IconComponent = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 mb-1 ${
                    activeTab === item.id
                      ? 'bg-purple-100 text-purple-700 border-l-4 border-purple-600'
                      : 'hover:bg-slate-100 text-slate-700'
                  }`}
                >
                  <IconComponent className="w-5 h-5" />
                  <span className="font-medium">{item.label}</span>
                </button>
              );
            })}
          </nav>

          {/* 侧边栏底部 - 登出按钮 */}
          <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-slate-200">
            <button
              onClick={onLogout}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 hover:bg-red-50 text-red-600 hover:text-red-700"
            >
              <LogOut className="w-5 h-5" />
              <span className="font-medium">退出登录</span>
            </button>
          </div>
        </div>

        {/* 主内容区 */}
        <div className="flex-1 overflow-auto">
          <div className="p-8">
            {/* 页面标题 */}
            <div className="mb-8">
              <h1 className="text-3xl font-bold text-slate-900 mb-2">
                {menuItems.find(item => item.id === activeTab)?.label}
              </h1>
              <p className="text-slate-600">
                {activeTab === 'classes' && '管理系统中的所有班级'}
                {activeTab === 'models' && '配置AI模型参数'}
                {activeTab === 'asr' && '配置语音识别模型参数'}
                {activeTab === 'tts' && '配置语音合成模型参数'}
                {activeTab === 'vector' && '配置向量嵌入模型参数'}
                {/* {activeTab === 'email' && '配置系统邮件服务'} */}
                {activeTab === 'knowledge' && '管理知识库文档与向量化'}
                {activeTab === 'coze' && '配置Coze代理设置'}
                {activeTab === 'users' && '按教师与学生分类管理系统成员'}
              </p>
            </div>

            {/* 内容区域 */}
            {activeTab === 'classes' && <ClassManagement />}
            {activeTab === 'models' && <ModelConfiguration />}
            {activeTab === 'asr' && <AsrConfiguration />}
            {activeTab === 'tts' && <TtsConfiguration />}
            {activeTab === 'vector' && <VectorConfiguration />}
            {/* {activeTab === 'email' && <EmailConfiguration />} */}
            {activeTab === 'knowledge' && <DocumentManagement />}
            {activeTab === 'coze' && <CozeConfiguration />}
            {activeTab === 'users' && <UserManagement />}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
