import React from 'react';
import EnhancedDebateAnalytics from './enhanced-debate-analytics';

interface DebateAnalyticsProps {
  userType?: 'student' | 'teacher';
  studentName?: string;
  debateId?: string;
  onBack?: () => void;
}

const DebateAnalytics: React.FC<DebateAnalyticsProps> = ({
  userType = 'student',
  studentName,
  debateId,
  onBack
}) => {
  return (
    <EnhancedDebateAnalytics
      userType={userType}
      studentName={studentName}
      debateId={debateId}
      onBack={onBack}
    />
  );
};

export default DebateAnalytics;
