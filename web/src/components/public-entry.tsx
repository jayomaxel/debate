import React from 'react';
import { ArrowRight, Bot, Compass, Trophy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAppRouter } from '@/lib/router';
import {
  getStudentAnalyticsPath,
  type PublicSection,
} from '@/lib/route-utils';
import { useProtectedAction } from './auth-guards';

interface PublicEntryProps {
  section: PublicSection;
}

const sectionContent: Record<
  PublicSection,
  {
    eyebrow: string;
    title: string;
    description: string;
    primaryLabel: string;
    accentClass: string;
  }
> = {
  home: {
    eyebrow: '公开入口',
    title: '浏览入口',
    description: '查看比赛、备赛和成长入口。',
    primaryLabel: '查看比赛入口',
    accentClass: 'student-card-soft-blue',
  },
  competition: {
    eyebrow: '比赛区',
    title: '比赛区',
    description: '输入邀请码进入辩论流程。',
    primaryLabel: '加入本场辩论',
    accentClass: 'student-card-soft-peach',
  },
  preparation: {
    eyebrow: '备赛区',
    title: '备赛区',
    description: '整理论点、证据和提问方向。',
    primaryLabel: '进入备赛区',
    accentClass: 'student-card-soft-lavender',
  },
  growth: {
    eyebrow: '成长区',
    title: '成长区',
    description: '查看历史、趋势和成就。',
    primaryLabel: '查看成长页',
    accentClass: 'student-card-soft-blue',
  },
};

const previewCards = [
  {
    key: 'competition' as PublicSection,
    icon: Trophy,
    title: '比赛',
    description: '加入单场辩论，进入等待、准备和正式对局。',
    tone: 'student-card-soft-peach',
  },
  {
    key: 'preparation' as PublicSection,
    icon: Bot,
    title: '备赛',
    description: '整理资料、论点、证据和提问方向。',
    tone: 'student-card-soft-blue',
  },
  {
    key: 'growth' as PublicSection,
    icon: Compass,
    title: '成长',
    description: '回看历史记录、趋势、对比和成就。',
    tone: 'student-card-soft-lavender',
  },
];

export default function PublicEntry({ section }: PublicEntryProps) {
  const { navigate } = useAppRouter();
  const { runProtectedAction } = useProtectedAction();
  const content = sectionContent[section];

  return (
    <div className="student-container py-6 pb-14 sm:py-8 sm:pb-16">
      <section className="relative overflow-hidden rounded-[16px] border border-[#d7ccbf] bg-white/68 px-5 py-7 shadow-[0_18px_46px_rgba(58,42,28,0.08)] backdrop-blur md:px-8 md:py-9">
        <div className="relative z-10 grid gap-6 xl:grid-cols-[minmax(0,1.18fr),minmax(320px,0.82fr)]">
          <div className="space-y-6">
            <div className="student-card px-6 py-6 md:px-8">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="max-w-2xl space-y-4">
                  <div className="student-pill">{content.eyebrow}</div>
                  <div className="space-y-3">
                    <h1 className="text-[2rem] font-semibold leading-[1.08] tracking-[-0.05em] text-slate-900 md:text-[2.3rem]">
                      {content.title}
                    </h1>
                    <p className="text-[15px] leading-7 text-slate-600 md:text-base">
                      {content.description}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <Button
                      size="lg"
                      className="student-dark-button h-auto"
                      onClick={() =>
                        void runProtectedAction(() => {
                          if (section === 'growth') {
                            navigate(getStudentAnalyticsPath('history'));
                            return;
                          }

                          if (section === 'preparation') {
                            navigate('/student/preparation');
                            return;
                          }

                          if (section === 'competition') {
                            navigate('/student/competition');
                            return;
                          }

                          navigate('/student');
                        })
                      }
                    >
                      {content.primaryLabel}
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                    <Button
                      size="lg"
                      variant="outline"
                      className="student-light-button h-auto"
                      onClick={() => navigate('/login')}
                    >
                      登录后继续
                    </Button>
                  </div>
                </div>

                <div className={`${content.accentClass} min-w-[220px] p-4`}>
                  <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
                    当前板块
                  </div>
                  <div className="mt-2 text-[1.45rem] font-semibold tracking-[-0.04em] text-slate-900">
                    {content.eyebrow}
                  </div>
                </div>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              {previewCards.map((card) => {
                const Icon = card.icon;
                const active = section === card.key;

                return (
                  <button
                    key={card.key}
                    type="button"
                    onClick={() => navigate(`/explore/${card.key}`)}
                    className={`${
                      active ? card.tone : 'student-card-muted'
                    } relative overflow-hidden p-4 text-left transition-transform duration-150 hover:-translate-y-0.5 hover:border-[#bda98f] hover:bg-white/84`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="space-y-3">
                        <div className="student-icon-bubble text-slate-900">
                          <Icon className="h-5 w-5" />
                        </div>
                        <div>
                          <h3 className="text-base font-semibold text-slate-900">
                            {card.title}
                          </h3>
                          <p className="mt-1.5 text-sm leading-6 text-slate-600">
                            {card.description}
                          </p>
                        </div>
                      </div>
                      <ArrowRight className="h-4 w-4 text-slate-500" />
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="student-page-aside space-y-5">
            <section className="student-card px-5 py-6">
              <div className="space-y-4">
                <div>
                  <h2 className="text-[1.5rem] font-semibold tracking-[-0.04em] text-slate-900">
                    入口说明
                  </h2>
                </div>
                <div className="space-y-3">
                  <div className="student-card-soft-peach p-4">
                    <div className="text-sm font-semibold text-slate-900">比赛区</div>
                    <div className="mt-1 text-sm leading-6 text-slate-600">
                      加入对局、等待开赛、进入正式辩论。
                    </div>
                  </div>
                  <div className="student-card-soft-blue p-4">
                    <div className="text-sm font-semibold text-slate-900">备赛区</div>
                    <div className="mt-1 text-sm leading-6 text-slate-600">
                      查看资料、整理论点、准备证据。
                    </div>
                  </div>
                  <div className="student-card-soft-lavender p-4">
                    <div className="text-sm font-semibold text-slate-900">成长区</div>
                    <div className="mt-1 text-sm leading-6 text-slate-600">
                      查看历史记录、趋势变化和成就进展。
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section className="student-card px-5 py-6">
              <div className="grid gap-3">
                <div className="student-card-muted p-4">
                  <div className="text-xs uppercase tracking-[0.18em] text-slate-500">浏览顺序</div>
                  <div className="mt-2 text-[1.35rem] font-semibold tracking-[-0.04em] text-slate-900">
                    选择入口
                  </div>
                </div>
                <div className="student-card-muted p-4">
                  <div className="text-xs uppercase tracking-[0.18em] text-slate-500">登录后</div>
                  <div className="mt-2 text-[1.35rem] font-semibold tracking-[-0.04em] text-slate-900">
                    布局和学生端保持一致
                  </div>
                </div>
              </div>
            </section>
          </div>
        </div>
      </section>
    </div>
  );
}
