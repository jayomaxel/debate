import React from 'react';

interface LegalPageProps {
  kind: 'privacy' | 'terms' | 'contact';
}

const content = {
  privacy: {
    title: '隐私政策',
    body: '平台仅处理完成教学、参赛和赛后分析所必需的账号与课堂数据。未经授权，不会将个人信息用于无关用途。教师和管理员应按学校制度管理导出文件与访问权限。',
  },
  terms: {
    title: '服务条款',
    body: '本平台用于教学辅助。AI 生成的辩题、点评和报告应由教师复核，不应作为对学生作出高风险决定的唯一依据。用户不得上传违法、侵权或与教学无关的敏感材料。',
  },
  contact: {
    title: '联系我们',
    body: '如需账号支持、数据更正或安全问题反馈，请联系本平台管理员，并提供班级、账号和问题发生时间。',
  },
};

const LegalPage: React.FC<LegalPageProps> = ({ kind }) => {
  const item = content[kind];
  return (
    <main className='min-h-screen bg-slate-50 px-6 py-16'>
      <article className='mx-auto max-w-3xl rounded-xl border bg-white p-8 shadow-sm'>
        <a href='/' className='text-sm font-medium text-blue-600 hover:underline'>返回首页</a>
        <h1 className='mt-6 text-3xl font-bold text-slate-900'>{item.title}</h1>
        <p className='mt-6 leading-8 text-slate-600'>{item.body}</p>
        <p className='mt-8 text-sm text-slate-400'>更新日期：2026-07-17</p>
      </article>
    </main>
  );
};

export default LegalPage;
