import React, { useState } from 'react';
import {
  Users,
  Database,
  Bot,
  BookOpen,
  Mic,
  Volume2,
  Layers,
  FileText,
  Mail,
  BrainCircuit,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import ClassManagement from './admin/class-management';
import ModelConfiguration from './admin/model-configuration';
import AsrConfiguration from './admin/asr-configuration';
import TtsConfiguration from './admin/tts-configuration';
import VectorConfiguration from './admin/vector-configuration';
import EmailConfiguration from './admin/email-configuration';
import CozeConfiguration from './admin/coze-configuration';
import UserManagement from './admin/user-management';
import DocumentManagement from './admin/document-management';

interface AdminDashboardProps {
  onLogout: () => void;
}

type TabType =
  | 'classes'
  | 'models'
  | 'asr'
  | 'tts'
  | 'vector'
  | 'email'
  | 'coze'
  | 'users'
  | 'knowledge';

const menuItems = [
  { id: 'classes' as TabType, label: '班级管理', icon: BookOpen },
  { id: 'knowledge' as TabType, label: '知识库管理', icon: FileText },
  { id: 'models' as TabType, label: '模型配置', icon: Database },
  { id: 'asr' as TabType, label: 'ASR 配置', icon: Mic },
  { id: 'tts' as TabType, label: 'TTS 配置', icon: Volume2 },
  { id: 'vector' as TabType, label: '向量配置', icon: Layers },
  { id: 'email' as TabType, label: '邮件配置', icon: Mail },
  { id: 'coze' as TabType, label: 'Coze 配置', icon: Bot },
  { id: 'users' as TabType, label: '成员管理', icon: Users },
];

const renderActivePanel = (activeTab: TabType) => {
  if (activeTab === 'classes') return <ClassManagement />;
  if (activeTab === 'models') return <ModelConfiguration />;
  if (activeTab === 'asr') return <AsrConfiguration />;
  if (activeTab === 'tts') return <TtsConfiguration />;
  if (activeTab === 'vector') return <VectorConfiguration />;
  if (activeTab === 'email') return <EmailConfiguration />;
  if (activeTab === 'knowledge') return <DocumentManagement />;
  if (activeTab === 'coze') return <CozeConfiguration />;
  return <UserManagement />;
};

const AdminDashboard: React.FC<AdminDashboardProps> = ({ onLogout }) => {
  const [activeTab, setActiveTab] = useState<TabType>('classes');
  const activeItem = menuItems.find((item) => item.id === activeTab) || menuItems[0];

  return (
    <div className="student-container py-6 pb-14">
      <section className="student-card px-5 py-6 md:px-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <h1 className="student-section-title text-[1.95rem] md:text-[2.25rem]">
              {activeItem.label}
            </h1>
            <p className="student-section-copy mt-3">
              统一处理平台资源、模型能力、班级和成员配置，保持管理员端和学生端一致的浏览节奏。
            </p>
          </div>

          <Button onClick={onLogout} className="student-light-button h-auto">
            退出登录
          </Button>
        </div>
      </section>

      <div className="student-sidebar-layout mt-5">
        <aside className="student-sidebar-rail space-y-4">
          <section className="student-card h-fit p-3.5">
            <div className="flex items-center gap-3 px-2 pb-3">
              <div className="student-icon-bubble bg-[#151515] text-white">
                <BrainCircuit className="h-5 w-5" />
              </div>
              <div>
                <div className="text-sm font-semibold text-slate-900">管理员导航</div>
                <div className="text-xs uppercase tracking-[0.22em] text-slate-500">
                  Control Panel
                </div>
              </div>
            </div>

            <nav className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
              {menuItems.map((item) => {
                const IconComponent = item.icon;
                const active = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id)}
                    className={`student-nav-pill w-full justify-start gap-3 text-left ${
                      active ? 'student-nav-pill-active' : ''
                    }`}
                  >
                    <IconComponent className="h-5 w-5" />
                    <span className="font-medium">{item.label}</span>
                  </button>
                );
              })}
            </nav>
          </section>
        </aside>

        <section className="student-card min-h-[560px] p-4 md:p-6">
          {renderActivePanel(activeTab)}
        </section>
      </div>
    </div>
  );
};

export default AdminDashboard;
