import React from 'react';
import { Button } from '@/components/ui/button';

interface NotFoundPageProps {
  onHome: () => void;
}

const NotFoundPage: React.FC<NotFoundPageProps> = ({ onHome }) => (
  <main className='flex min-h-screen items-center justify-center bg-slate-50 p-6'>
    <div className='max-w-lg text-center'>
      <div className='text-sm font-semibold tracking-widest text-blue-600'>404</div>
      <h1 className='mt-3 text-3xl font-bold text-slate-900'>页面不存在</h1>
      <p className='mt-3 text-slate-600'>链接可能已失效，或你没有访问该页面的入口。</p>
      <Button className='mt-6' onClick={onHome}>返回首页</Button>
    </div>
  </main>
);

export default NotFoundPage;
