import React from 'react';
import { Button } from '@/components/ui/button';

interface ErrorBoundaryState {
  hasError: boolean;
}

class ErrorBoundary extends React.Component<React.PropsWithChildren, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className='flex min-h-screen items-center justify-center bg-slate-50 p-6'>
          <div className='max-w-lg rounded-xl border bg-white p-8 text-center shadow-sm'>
            <h1 className='text-2xl font-semibold text-slate-900'>页面暂时无法显示</h1>
            <p className='mt-3 text-slate-600'>应用遇到了异常，请刷新页面；如果问题持续，请联系平台管理员。</p>
            <Button className='mt-6' onClick={() => window.location.reload()}>刷新页面</Button>
          </div>
        </main>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
