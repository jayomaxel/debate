import React, { useState } from 'react';
import LoginPortal from './login-portal';
import TeacherDashboard from './teacher-dashboard';
import AdminDashboard from './admin-dashboard';
import StudentCommandCenter from './student-command-center';
import StudentOnboarding from './student-onboarding';
import DebateMatchResult from './debate-match-result';
import DebateArena from './debate-arena';
import EnhancedDebateAnalytics from './enhanced-debate-analytics';
import StudentAnalyticsCenter from './student-analytics-center';
import { DebateReportDetail } from './debate-report-detail';
import DebateReportPage from './debate-report-page';
import DebateReplayPage from './debate-replay-page';
import PreparationAssistantPage from './student/preparation-assistant-page';
import StudentService from '@/services/student.service';
import type { Debate } from '@/services/student.service';
import { useAuth } from '@/store/auth.context';

// 简单的路由管理组件
const AppRouter: React.FC = () => {
  const { user } = useAuth();
  const [currentPage, setCurrentPage] = useState<'login' | 'teacher' | 'student' | 'command-center' | 'match' | 'debate' | 'analytics' | 'admin' | 'student-analytics' | 'report-detail' | 'debate-report' | 'debate-replay' | 'preparation-assistant'>('login');
  const [userType, setUserType] = useState<'student' | 'teacher' | 'administrator'>('student');
  const [currentDebateId, setCurrentDebateId] = useState<string | undefined>(undefined);
  const [joinedDebate, setJoinedDebate] = useState<Debate | null>(null);
  const [studentNeedsAssessment, setStudentNeedsAssessment] = useState(false);
  const [studentProfileTab, setStudentProfileTab] = useState<'info' | 'password' | 'ability'>('info');
  const [reportDebateId, setReportDebateId] = useState<string | undefined>(undefined);
  const [reportBackPage, setReportBackPage] = useState<'command-center' | 'student-analytics' | 'teacher'>('command-center');
  const [replayDebateId, setReplayDebateId] = useState<string | undefined>(undefined);
  const [replayBackPage, setReplayBackPage] = useState<'command-center' | 'student-analytics' | 'teacher'>('command-center');

  // 在实际项目中，这里会使用 React Router 或其他路由库
  // 现在用简单的状态管理来模拟路由

  const renderPage = () => {
    switch (currentPage) {
      case 'login':
        return <LoginPortal onLogin={async (role) => {
          setUserType(role);
          if (role === 'administrator') {
            setCurrentPage('admin');
            return;
          }
          if (role === 'teacher') {
            setCurrentPage('teacher');
            return;
          }

          let need = false;
          try {
            const assessment = await StudentService.getAssessment();
            need = !assessment || !!assessment.is_default;
          } catch {
            need = true;
          }

          setStudentNeedsAssessment(need);
          setStudentProfileTab(need ? 'ability' : 'info');
          setCurrentPage('command-center');
        }} />;
      case 'teacher':
        return <TeacherDashboard 
          onLogout={() => setCurrentPage('login')} 
          onNavigate={(page, debateId) => {
            console.log(`Navigate to ${page} with debateId ${debateId}`);
            if (page === 'debate-report') {
              setReportBackPage('teacher');
              setReportDebateId(debateId);
              setCurrentPage('debate-report');
              return;
            }
            if (page === 'debate-replay') {
              setReplayBackPage('teacher');
              setReplayDebateId(debateId);
              setCurrentPage('debate-replay');
              return;
            }
            setCurrentDebateId(debateId);
            setCurrentPage(page);
          }}
        />;
      case 'admin':
        return <AdminDashboard onLogout={() => setCurrentPage('login')} />;
      case 'command-center':
        return <StudentCommandCenter
          defaultShowProfile={studentNeedsAssessment}
          defaultProfileTab={studentProfileTab}
          onJoinClass={(debate) => {
            console.log('加入课堂:', debate.invitation_code);
            setJoinedDebate(debate);
            setCurrentDebateId(debate.id);
            setCurrentPage('student');
          }}
          onToWaitingRoom={() => setCurrentPage('student')}
          onViewReport={(matchId) => {
            console.log('查看报告:', matchId);
            setReportBackPage('command-center');
            setReportDebateId(matchId);
            setCurrentPage('debate-report');
          }}
          onViewReplay={(debateId) => {
            setReplayBackPage('command-center');
            setReplayDebateId(debateId);
            setCurrentPage('debate-replay');
          }}
          onNavigateToAnalytics={() => setCurrentPage('student-analytics')}
          onNavigateToPreparation={() => setCurrentPage('preparation-assistant')}
          onLogout={() => {
            setStudentNeedsAssessment(false);
            setStudentProfileTab('info');
            setCurrentPage('login');
          }}
        />;
      case 'student':
        return <StudentOnboarding 
          initialDebate={joinedDebate}
          onBackToLogin={() => setCurrentPage('login')} 
          onMatchFound={() => setCurrentPage('match')} 
        />;
      case 'match':
        return <DebateMatchResult
          initialDebate={joinedDebate}
          onBack={() => setCurrentPage('command-center')}
          onStartDebate={(debateId) => {
            if (debateId) {
              setCurrentDebateId(debateId);
            }
            setCurrentPage('debate');
          }}
          onCountdownEnd={() => console.log('倒计时结束')}
        />;
      case 'debate':
        return <DebateArena 
          roomId={currentDebateId}
          onBack={() => userType === 'teacher' ? setCurrentPage('teacher') : setCurrentPage('match')} 
          onEndDebate={() => setCurrentPage('analytics')} 
        />;
      case 'analytics':
        return <EnhancedDebateAnalytics
          userType={userType === 'teacher' ? 'teacher' : 'student'}
          studentName={user?.name}
          debateId={currentDebateId}
          onBack={() => setCurrentPage(userType === 'teacher' ? 'teacher' : 'command-center')}
        />;
      case 'student-analytics':
        return <StudentAnalyticsCenter
          onBack={() => setCurrentPage('command-center')}
          onViewReport={(debateId) => {
            setReportBackPage('student-analytics');
            setReportDebateId(debateId);
            setCurrentPage('debate-report');
          }}
          onViewReplay={(debateId) => {
            setReplayBackPage('student-analytics');
            setReplayDebateId(debateId);
            setCurrentPage('debate-replay');
          }}
        />;
      case 'debate-report':
        return reportDebateId ? (
          <DebateReportPage
            debateId={reportDebateId}
            studentName={user?.name}
            onBack={() => setCurrentPage(reportBackPage)}
          />
        ) : null;
      case 'debate-replay':
        return replayDebateId ? (
          <DebateReplayPage
            debateId={replayDebateId}
            onBack={() => setCurrentPage(replayBackPage)}
          />
        ) : null;
      case 'preparation-assistant':
        return (
          <PreparationAssistantPage
            onBack={() => setCurrentPage('command-center')}
          />
        );
      case 'report-detail':
        return reportDebateId ? (
          <DebateReportDetail
            debateId={reportDebateId}
            onBack={() => setCurrentPage('student-analytics')}
          />
        ) : null;
      default:
        return <LoginPortal onLogin={async (role) => {
          setUserType(role);
          if (role === 'administrator') {
            setCurrentPage('admin');
            return;
          }
          if (role === 'teacher') {
            setCurrentPage('teacher');
            return;
          }

          let need = false;
          try {
            const assessment = await StudentService.getAssessment();
            need = !assessment || !!assessment.is_default;
          } catch {
            need = true;
          }

          setStudentNeedsAssessment(need);
          setStudentProfileTab(need ? 'ability' : 'info');
          setCurrentPage('command-center');
        }} />;
    }
  };

  return renderPage();
};

export default AppRouter;
