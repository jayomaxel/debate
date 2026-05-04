import React from 'react';

interface DebateFullscreenLayoutProps {
  children: React.ReactNode;
}

export default function DebateFullscreenLayout({
  children,
}: DebateFullscreenLayoutProps) {
  return <div className="min-h-screen bg-slate-950">{children}</div>;
}
