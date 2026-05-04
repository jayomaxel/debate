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
  Shield,
} from 'lucide-react';
import { useAuth } from '@/store/auth.context';
import ClassManagement from './admin/class-management';
import ModelConfiguration from './admin/model-configuration';
import AsrConfiguration from './admin/asr-configuration';
import TtsConfiguration from './admin/tts-configuration';
import VectorConfiguration from './admin/vector-configuration';
import EmailConfiguration from './admin/email-configuration';
import CozeConfiguration from './admin/coze-configuration';
import UserManagement from './admin/user-management';
import DocumentManagement from './admin/document-management';
import UserProfile from './user-profile';

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
  | 'knowledge'
  | 'profile';

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
  { id: 'profile' as TabType, label: '个人中心', icon: Shield },
];

const renderActivePanel = (activeTab: TabType, user: ReturnType<typeof useAuth>['user']) => {
  if (activeTab === 'classes') return <ClassManagement />;
  if (activeTab === 'models') return <ModelConfiguration />;
  if (activeTab === 'asr') return <AsrConfiguration />;
  if (activeTab === 'tts') return <TtsConfiguration />;
  if (activeTab === 'vector') return <VectorConfiguration />;
  if (activeTab === 'email') return <EmailConfiguration />;
  if (activeTab === 'knowledge') return <DocumentManagement />;
  if (activeTab === 'coze') return <CozeConfiguration />;
  if (activeTab === 'profile') return user ? <UserProfile user={user} /> : null;
  return <UserManagement />;
};

const AdminDashboard: React.FC<AdminDashboardProps> = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<TabType>('classes');

  return (
    <div className="student-shell flex h-screen">
      <aside className="student-card m-4 w-64 shrink-0 overflow-hidden">
        <nav className="p-4">
          {menuItems.map((item) => {
            const IconComponent = item.icon;
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`student-nav-pill mb-1 inline-flex w-full items-center justify-start gap-3 text-left ${
                  active ? 'student-nav-pill-active' : ''
                }`}
              >
                <IconComponent className="h-5 w-5" />
                <span className="font-medium">{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="flex-1 overflow-auto">
        <div className="student-container py-6 pb-14">
          <section className="student-card min-h-[560px] p-4 md:p-6">
            {renderActivePanel(activeTab, user)}
          </section>
        </div>
      </main>
    </div>
  );
};

export default AdminDashboard;
