import React from 'react';

interface DebateFullscreenLayoutProps {
  children: React.ReactNode;
}

export default function DebateFullscreenLayout({
  children,
}: DebateFullscreenLayoutProps) {
  return (
    <div className="student-theme">
      <div className="student-shell">{children}</div>
    </div>
  );
}
