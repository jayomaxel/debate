import React from 'react';
import LoginPortal from './login-portal';
import TeacherDashboard from './teacher-dashboard';
import AdminDashboard from './admin-dashboard';
import StudentCommandCenter from './student-command-center';
import StudentCompetitionHub from './student-competition-hub';
import StudentOnboarding from './student-onboarding';
import DebateLobby from './debate-lobby';
import LobbyRoomWaiting from './lobby-room-waiting';
import DebateArena from './debate-arena';
import EnhancedDebateAnalytics from './enhanced-debate-analytics';
import StudentAnalyticsCenter from './student-analytics-center';
import DebateReportPage from './debate-report-page';
import DebateReplayPage from './debate-replay-page';
import PreparationAssistantPage from './student/preparation-assistant-page';
import UserProfile from './user-profile';
import PublicEntry from './public-entry';
import {
  RequireAuth,
  RequireGuest,
  RequireRole,
  RequireStudentAssessment,
} from './auth-guards';
import PublicLayout from './layouts/public-layout';
import StudentLayout from './layouts/student-layout';
import TeacherLayout from './layouts/teacher-layout';
import AdminLayout from './layouts/admin-layout';
import SettingsLayout from './layouts/settings-layout';
import DebateFullscreenLayout from './layouts/debate-fullscreen-layout';
import { useAuth } from '@/store/auth.context';
import { matchPath, useAppRouter } from '@/lib/router';
import {
  getDefaultHomePath,
  getStudentAnalyticsPath,
  getStudentSettingsPath,
  normalizePublicSection,
  normalizeSettingsTab,
  normalizeStudentAnalyticsTab,
} from '@/lib/route-utils';

const AppRouter: React.FC = () => {
  const { location, navigate, back } = useAppRouter();
  const { logout, user, updateUser } = useAuth();
  const pathname = location.pathname;
  const searchParams = new URLSearchParams(location.search);

  const handleLogout = () => {
    logout();
    navigate('/', { replace: true });
  };

  const renderPublicPage = (sectionKey?: string | null) => {
    const section = normalizePublicSection(sectionKey);

    return (
      <PublicLayout activeSection={section}>
        <PublicEntry section={section} />
      </PublicLayout>
    );
  };

  const renderStudentPage = (children: React.ReactNode) => (
    <RequireAuth>
      <RequireRole role="student">
        <StudentLayout>{children}</StudentLayout>
      </RequireRole>
    </RequireAuth>
  );

  const renderStudentCompetitionPage = (children: React.ReactNode) => (
    <RequireAuth>
      <RequireRole role="student">
        <RequireStudentAssessment>
          <StudentLayout>{children}</StudentLayout>
        </RequireStudentAssessment>
      </RequireRole>
    </RequireAuth>
  );

  const renderTeacherPage = (children: React.ReactNode) => (
    <RequireAuth>
      <RequireRole role="teacher">
        <TeacherLayout>{children}</TeacherLayout>
      </RequireRole>
    </RequireAuth>
  );

  const renderAdminPage = (children: React.ReactNode) => (
    <RequireAuth>
      <RequireRole role="administrator">
        <AdminLayout>{children}</AdminLayout>
      </RequireRole>
    </RequireAuth>
  );

  const loginMatch = matchPath('/login', pathname);
  if (loginMatch) {
    return (
      <RequireGuest>
        <LoginPortal
          onLogin={async (role) => {
            navigate(getDefaultHomePath(role), { replace: true });
          }}
        />
      </RequireGuest>
    );
  }

  const studentArenaMatch = matchPath('/student/debates/:debateId/arena', pathname);
  if (studentArenaMatch) {
    const debateId = studentArenaMatch.params.debateId;

    return (
      <RequireAuth>
        <RequireRole role="student">
          <RequireStudentAssessment>
            <DebateFullscreenLayout>
              <DebateArena
                roomId={debateId}
                onEndDebate={() =>
                  navigate(`/student/debates/${debateId}/analytics`, {
                    replace: true,
                  })
                }
              />
            </DebateFullscreenLayout>
          </RequireStudentAssessment>
        </RequireRole>
      </RequireAuth>
    );
  }

  const teacherArenaMatch = matchPath('/teacher/debates/:debateId/arena', pathname);
  if (teacherArenaMatch) {
    const debateId = teacherArenaMatch.params.debateId;

    return renderTeacherPage(
      <DebateFullscreenLayout>
        <DebateArena
          roomId={debateId}
          onEndDebate={() =>
            navigate(`/teacher/debates/${debateId}/analytics`, {
              replace: true,
            })
          }
        />
      </DebateFullscreenLayout>
    );
  }

  const studentAnalyticsReportMatch = matchPath(
    '/student/debates/:debateId/analytics',
    pathname
  );
  if (studentAnalyticsReportMatch) {
    const debateId = studentAnalyticsReportMatch.params.debateId;

    return renderStudentPage(
      <EnhancedDebateAnalytics
        debateId={debateId}
        studentName={user?.name}
        userType="student"
        onBack={() => navigate('/student')}
      />
    );
  }

  const teacherAnalyticsReportMatch = matchPath(
    '/teacher/debates/:debateId/analytics',
    pathname
  );
  if (teacherAnalyticsReportMatch) {
    const debateId = teacherAnalyticsReportMatch.params.debateId;

    return renderTeacherPage(
      <EnhancedDebateAnalytics
        debateId={debateId}
        userType="teacher"
        onBack={() => navigate('/teacher')}
      />
    );
  }

  const studentReportMatch = matchPath('/student/reports/:debateId', pathname);
  if (studentReportMatch) {
    return renderStudentPage(
      <DebateReportPage
        debateId={studentReportMatch.params.debateId}
        studentName={user?.name}
        studentMode
        onBack={() => back('/student')}
      />
    );
  }

  const teacherReportMatch = matchPath('/teacher/reports/:debateId', pathname);
  if (teacherReportMatch) {
    return renderTeacherPage(
      <DebateReportPage
        debateId={teacherReportMatch.params.debateId}
        onBack={() => back('/teacher')}
      />
    );
  }

  const studentReplayMatch = matchPath('/student/replays/:debateId', pathname);
  if (studentReplayMatch) {
    return renderStudentPage(
      <DebateReplayPage
        debateId={studentReplayMatch.params.debateId}
        onBack={() => back('/student')}
      />
    );
  }

  const teacherReplayMatch = matchPath('/teacher/replays/:debateId', pathname);
  if (teacherReplayMatch) {
    return renderTeacherPage(
      <DebateReplayPage
        debateId={teacherReplayMatch.params.debateId}
        onBack={() => back('/teacher')}
      />
    );
  }

  const studentAnalyticsMatch = matchPath('/student/analytics/:tab', pathname);
  if (studentAnalyticsMatch) {
    const tab = normalizeStudentAnalyticsTab(studentAnalyticsMatch.params.tab);

    return renderStudentPage(
      <StudentAnalyticsCenter
        defaultTab={tab}
        onBack={() => navigate('/student')}
        onViewReport={(debateId) => navigate(`/student/reports/${debateId}`)}
        onViewReplay={(debateId) => navigate(`/student/replays/${debateId}`)}
      />
    );
  }

  const studentAnalyticsHomeMatch = matchPath('/student/analytics', pathname);
  if (studentAnalyticsHomeMatch) {
    return renderStudentPage(
      <StudentAnalyticsCenter
        defaultTab="history"
        onBack={() => navigate('/student')}
        onViewReport={(debateId) => navigate(`/student/reports/${debateId}`)}
        onViewReplay={(debateId) => navigate(`/student/replays/${debateId}`)}
      />
    );
  }

  const studentPreparationMatch = matchPath('/student/preparation', pathname);
  if (studentPreparationMatch) {
    return renderStudentPage(
      <PreparationAssistantPage onBack={() => navigate('/student')} />
    );
  }

  const studentLobbyRoomMatch = matchPath('/student/lobby/rooms/:roomId', pathname);
  if (studentLobbyRoomMatch) {
    const roomId = studentLobbyRoomMatch.params.roomId;

    return renderStudentPage(
      <LobbyRoomWaiting
        roomId={roomId}
        onBack={() => navigate('/student/lobby')}
        onEnterDebate={(targetRoomId) =>
          navigate(`/student/debates/${targetRoomId}/arena`)
        }
      />
    );
  }

  const studentLobbyMatch = matchPath('/student/lobby', pathname);
  if (studentLobbyMatch) {
    return renderStudentPage(
      <DebateLobby
        onBack={() => navigate('/student')}
        onEnterRoom={(roomId) => navigate(`/student/lobby/rooms/${roomId}`)}
      />
    );
  }

  const studentCompetitionMatch = matchPath('/student/competition', pathname);
  if (studentCompetitionMatch) {
    return renderStudentPage(
      <StudentCompetitionHub
        onNavigateToWaiting={() => navigate('/student/waiting')}
        onNavigateToPostMatch={(debateId) =>
          navigate(`/student/debates/${debateId}/analytics`)
        }
        onNavigateToSettings={(tab = 'ability') =>
          navigate(getStudentSettingsPath(tab))
        }
      />
    );
  }

  const studentSettingsMatch = matchPath('/student/settings', pathname);
  if (studentSettingsMatch) {
    const initialTab = normalizeSettingsTab(searchParams.get('tab'));

    return (
      <RequireAuth>
        <RequireRole role="student">
          <SettingsLayout onBack={() => navigate('/student')}>
            {user ? (
              <UserProfile
                user={user}
                initialTab={initialTab}
                onUpdate={(nextUser) => {
                  if (nextUser) {
                    updateUser(nextUser);
                  }
                }}
              />
            ) : null}
          </SettingsLayout>
        </RequireRole>
      </RequireAuth>
    );
  }

  const studentWaitingMatch = matchPath('/student/waiting', pathname);
  if (studentWaitingMatch) {
    return renderStudentCompetitionPage(
      <StudentOnboarding
        onBackToLogin={() => navigate('/student')}
        onDebateStart={(debateId) => {
          if (!debateId) {
            return;
          }

          navigate(`/student/debates/${debateId}/arena`);
        }}
        onNavigateToAnalytics={(tab) =>
          navigate(getStudentAnalyticsPath(tab === 'growth' ? 'growth' : 'history'))
        }
      />
    );
  }

  const studentHomeMatch = matchPath('/student', pathname);
  if (studentHomeMatch) {
    return renderStudentPage(
      <StudentCommandCenter
        onViewReport={(debateId) => navigate(`/student/reports/${debateId}`)}
        onViewReplay={(debateId) => navigate(`/student/replays/${debateId}`)}
        onNavigateToAnalytics={(tab = 'history') =>
          navigate(getStudentAnalyticsPath(tab))
        }
        onNavigateToPreparation={() => navigate('/student/preparation')}
        onNavigateToLobby={() => navigate('/student/lobby')}
        onEnterLobbyRoom={(roomId) => navigate(`/student/lobby/rooms/${roomId}`)}
        onNavigateToSettings={(tab = 'info') =>
          navigate(getStudentSettingsPath(tab))
        }
      />
    );
  }

  const teacherHomeMatch = matchPath('/teacher', pathname);
  if (teacherHomeMatch) {
    return renderTeacherPage(
      <TeacherDashboard
        onLogout={handleLogout}
        onNavigate={(page, debateId) => {
          if (page === 'debate' && debateId) {
            navigate(`/teacher/debates/${debateId}/arena`);
            return;
          }

          if (page === 'analytics' && debateId) {
            navigate(`/teacher/debates/${debateId}/analytics`);
            return;
          }

          if (page === 'debate-report' && debateId) {
            navigate(`/teacher/reports/${debateId}`);
            return;
          }

          if (page === 'debate-replay' && debateId) {
            navigate(`/teacher/replays/${debateId}`);
          }
        }}
      />
    );
  }

  const adminMatch = matchPath('/admin', pathname);
  if (adminMatch) {
    return renderAdminPage(<AdminDashboard onLogout={handleLogout} />);
  }

  const exploreMatch = matchPath('/explore/:section', pathname);
  if (exploreMatch) {
    return renderPublicPage(exploreMatch.params.section);
  }

  const homeMatch = matchPath('/', pathname);
  if (homeMatch) {
    return renderPublicPage('home');
  }

  return renderPublicPage('home');
};

export default AppRouter;
