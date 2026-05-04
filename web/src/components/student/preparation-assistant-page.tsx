import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArrowLeft,
  BookOpen,
  Bot,
  Download,
  FileText,
  Loader2,
  MessageSquare,
  RefreshCw,
  Plus,
  Search,
  Send,
  User,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import StudentService, {
  type Conversation,
  type KBDocument,
  type KBSession,
  type KBSource,
} from '@/services/student.service';
import { formatErrorMessage } from '@/lib/error-handler';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/store/auth.context';
import { usePageActivityRefresh } from '@/hooks/use-page-activity-refresh';
import TokenManager from '@/lib/token-manager';

interface PreparationAssistantPageProps {
  onBack: () => void;
}

const PreparationAssistantPage: React.FC<PreparationAssistantPageProps> = ({
  onBack,
}) => {
  const { toast } = useToast();
  const { user } = useAuth();
  const [sessions, setSessions] = useState<KBSession[]>([]);
  const [documents, setDocuments] = useState<KBDocument[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingDocuments, setLoadingDocuments] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [documentSearch, setDocumentSearch] = useState('');
  const [downloadingDocumentId, setDownloadingDocumentId] = useState<string | null>(
    null
  );
  const [streamingAnswer, setStreamingAnswer] = useState('');
  const [streamingSources, setStreamingSources] = useState<KBSource[]>([]);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const pendingSessionIdRef = useRef<string | null>(null);

  const scrollToBottom = () => {
    if (!scrollAreaRef.current) {
      return;
    }

    const viewport = scrollAreaRef.current.querySelector(
      '[data-radix-scroll-area-viewport]'
    );

    if (viewport) {
      (viewport as HTMLDivElement).scrollTop =
        (viewport as HTMLDivElement).scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversations, streamingAnswer]);

  const loadConversationHistory = useCallback(async (sessionId: string) => {
    try {
      setLoadingHistory(true);
      const history = await StudentService.getKBConversationHistory(sessionId);
      setConversations(Array.isArray(history) ? history.reverse() : []);
    } catch (error) {
      console.error('[PreparationAssistantPage] Failed to load history:', error);
      setConversations([]);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  const loadSessions = useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent === true;

    try {
      if (silent) {
        setRefreshing(true);
      } else {
        setLoadingSessions(true);
      }

      const data = await StudentService.getKBSessions();
      setSessions(data);
      setCurrentSessionId((previous) => previous || data[0]?.session_id || null);
    } catch (error) {
      console.error('[PreparationAssistantPage] Failed to load sessions:', error);
    } finally {
      setLoadingSessions(false);
      setRefreshing(false);
    }
  }, []);

  const loadDocuments = useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent === true;

    try {
      if (!silent) {
        setLoadingDocuments(true);
      }

      const data = await StudentService.getKBDocuments(1, 50);
      setDocuments(Array.isArray(data.documents) ? data.documents : []);
    } catch (error) {
      console.error('[PreparationAssistantPage] Failed to load documents:', error);
    } finally {
      setLoadingDocuments(false);
    }
  }, []);

  useEffect(() => {
    void loadSessions();
    void loadDocuments();
  }, [loadDocuments, loadSessions]);

  useEffect(() => {
    if (currentSessionId) {
      if (pendingSessionIdRef.current === currentSessionId) {
        return;
      }

      void loadConversationHistory(currentSessionId);
      return;
    }

    setConversations([]);
  }, [currentSessionId, loadConversationHistory]);

  usePageActivityRefresh(
    async () => {
      await loadSessions({ silent: true });
      await loadDocuments({ silent: true });
      if (currentSessionId && pendingSessionIdRef.current !== currentSessionId) {
        await loadConversationHistory(currentSessionId);
      }
    },
    {
      enabled: !loadingSessions,
      intervalMs: 20000,
    }
  );

  const handleNewChat = () => {
    pendingSessionIdRef.current = null;
    setCurrentSessionId(null);
    setConversations([]);
    setQuestion('');
    inputRef.current?.focus();
  };

  const handleSessionSelect = (sessionId: string) => {
    if (sessionId === currentSessionId) {
      return;
    }

    setCurrentSessionId(sessionId);
  };

  const handleAskQuestion = async () => {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      return;
    }

    let sessionId = currentSessionId;
    let createdNewSession = false;

    if (!sessionId) {
      createdNewSession = true;
      sessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
      pendingSessionIdRef.current = sessionId;
      setCurrentSessionId(sessionId);
    }

    try {
      setLoading(true);
      setQuestion('');
      setStreamingAnswer('');
      setStreamingSources([]);

      const tempMessage: Conversation = {
        id: `temp_${Date.now()}`,
        question: trimmedQuestion,
        answer: '',
        sources: [],
        created_at: new Date().toISOString(),
      };

      setConversations((previous) => [...previous, tempMessage]);

      const token = TokenManager.getAccessToken();
      const response = await fetch('/api/student/kb/ask/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          question: trimmedQuestion,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error(`Error: ${response.statusText}`);
      }

      if (!response.body) {
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let answerAccumulator = '';
      let sourcesAccumulator: KBSource[] = [];
      let reading = true;

      while (reading) {
        const { done, value } = await reader.read();
        if (done) {
          reading = false;
          continue;
        }

        buffer += decoder.decode(value, { stream: true });
        const segments = buffer.split('\n\n');
        buffer = segments.pop() || '';

        for (const segment of segments) {
          if (!segment.startsWith('data: ')) {
            continue;
          }

          const payload = segment.slice(6);

          try {
            const event = JSON.parse(payload);

            if (event.type === 'sources') {
              sourcesAccumulator = Array.isArray(event.data) ? event.data : [];
              setStreamingSources(sourcesAccumulator);
              continue;
            }

            if (event.type === 'answer') {
              const content =
                typeof event.content === 'string' ? event.content : '';
              answerAccumulator += content;
              setStreamingAnswer(answerAccumulator);
              continue;
            }

            if (event.type === 'done') {
              pendingSessionIdRef.current = null;
              setConversations((previous) => {
                const next = [...previous];
                const lastIndex = next.length - 1;
                if (lastIndex >= 0) {
                  next[lastIndex] = {
                    ...next[lastIndex],
                    id: event.id,
                    answer: answerAccumulator,
                    sources: sourcesAccumulator,
                  };
                }
                return next;
              });

              if (!sessions.find((item) => item.session_id === sessionId)) {
                void loadSessions({ silent: true });
              }
              continue;
            }

            if (event.type === 'error') {
              toast({
                variant: 'destructive',
                title: '生成出错',
                description: event.message,
              });
            }
          } catch (parseError) {
            console.error('[PreparationAssistantPage] Error parsing SSE:', parseError);
          }
        }
      }

      setConversations((previous) => {
        const next = [...previous];
        const lastIndex = next.length - 1;
        if (lastIndex >= 0) {
          next[lastIndex] = {
            ...next[lastIndex],
            answer: answerAccumulator,
            sources: sourcesAccumulator,
          };
        }
        return next;
      });
    } catch (error: any) {
      console.error('[PreparationAssistantPage] Failed to ask question:', error);
      if (createdNewSession) {
        pendingSessionIdRef.current = null;
        setCurrentSessionId(null);
      }
      toast({
        variant: 'destructive',
        title: '提问失败',
        description: formatErrorMessage(error),
      });
      setConversations((previous) => previous.slice(0, -1));
      setQuestion(trimmedQuestion);
    } finally {
      setLoading(false);
      setStreamingAnswer('');
      setStreamingSources([]);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void handleAskQuestion();
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes || bytes <= 0) {
      return '未知大小';
    }

    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(0)} KB`;
    }

    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const filteredDocuments = documents.filter((document) => {
    const keyword = documentSearch.trim().toLowerCase();
    if (!keyword) {
      return true;
    }

    return (
      document.filename.toLowerCase().includes(keyword) ||
      document.file_type.toLowerCase().includes(keyword)
    );
  });

  const handleDownloadDocument = async (document: KBDocument) => {
    try {
      setDownloadingDocumentId(document.id);
      await StudentService.downloadKBDocument(document);
    } catch (error) {
      toast({
        variant: 'destructive',
        title: '下载失败',
        description: formatErrorMessage(error),
      });
    } finally {
      setDownloadingDocumentId(null);
    }
  };

  const renderSources = (sources: KBSource[]) => {
    if (!sources || sources.length === 0) {
      return null;
    }

    return (
      <div className="mt-4 space-y-3 border-t border-black/5 pt-4">
        <div className="flex items-center gap-2">
          <Badge className="student-pill">
            <FileText className="mr-1 h-3 w-3" />
            参考资料
          </Badge>
          <span className="text-xs text-slate-500">{sources.length} 份相关文档</span>
        </div>

        <div className="grid grid-cols-1 gap-2">
          {sources.map((source, index) => (
            <div
              key={`${source.document_id}-${index}`}
              className="rounded-[14px] border border-black/5 bg-white/75 p-3 text-xs shadow-[0_10px_25px_rgba(15,23,42,0.04)]"
            >
              <div className="mb-1 flex items-center justify-between gap-3">
                <span
                  className="max-w-[220px] truncate font-medium text-slate-800"
                  title={source.document_name}
                >
                  {source.document_name}
                </span>
                <span className="text-slate-400">
                  {(source.similarity_score * 100).toFixed(0)}%
                </span>
              </div>
              <p className="line-clamp-2 text-slate-500" title={source.excerpt}>
                {source.excerpt}
              </p>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="student-container py-6 pb-12">
      <div className="grid gap-5 xl:grid-cols-[320px,1fr]">
        <aside className="student-card flex min-h-[calc(100vh-11rem)] flex-col overflow-hidden">
          <div className="border-b border-black/5 p-4">
            <Button
              onClick={onBack}
              variant="ghost"
              size="sm"
              className="student-light-button mb-4 h-auto px-4 py-2"
            >
              <ArrowLeft className="mr-1 h-4 w-4" />
              返回学生首页
            </Button>

            <div className="student-card-soft-lavender p-3.5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
                    AI 备赛助手
                  </div>
                  <div className="mt-1.5 text-lg font-semibold tracking-[-0.03em] text-slate-900">
                    开启新对话
                  </div>
                </div>
                <div className="student-icon-bubble h-11 w-11 bg-white text-slate-900">
                  <Bot className="h-5 w-5" />
                </div>
              </div>

              <div className="mt-4 space-y-3">
                <Button onClick={handleNewChat} className="student-dark-button h-auto w-full justify-center">
                  <Plus className="mr-2 h-4 w-4" />
                  开启新对话
                </Button>

                <Button
                  variant="outline"
                  className="student-light-button h-auto w-full justify-center"
                  onClick={async () => {
                    await loadSessions({ silent: true });
                    await loadDocuments({ silent: true });
                  }}
                  disabled={refreshing}
                >
                  {refreshing ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <MessageSquare className="mr-2 h-4 w-4" />
                  )}
                  刷新会话
                </Button>
              </div>
            </div>
          </div>

          <div className="border-b border-black/5 px-4 py-4">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold text-slate-900">资料库</div>
                <div className="text-xs text-slate-500">
                  浏览备赛材料并下载原文件
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void loadDocuments({ silent: true })}
                disabled={loadingDocuments}
                className="student-light-button h-auto rounded-[10px] px-3 py-2"
              >
                {loadingDocuments ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
              </Button>
            </div>

            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                value={documentSearch}
                onChange={(event) => setDocumentSearch(event.target.value)}
                placeholder="搜索资料标题"
                className="w-full rounded-[14px] border border-black/10 bg-white/75 py-3 pl-10 pr-3 text-sm outline-none transition focus:border-black/20"
              />
            </div>

            <div className="mt-3 max-h-64 space-y-2 overflow-y-auto pr-1">
              {loadingDocuments ? (
                <div className="student-card-muted px-3 py-6 text-center text-sm text-slate-500">
                  正在加载资料库...
                </div>
              ) : filteredDocuments.length === 0 ? (
                <div className="student-card-muted px-3 py-6 text-center text-sm text-slate-500">
                  暂无匹配资料
                </div>
              ) : (
                filteredDocuments.map((document) => (
                  <div key={document.id} className="student-card-muted p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium text-slate-900">
                          {document.filename}
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          {document.file_type.toUpperCase()} ·{' '}
                          {formatFileSize(document.file_size)}
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        className="student-light-button h-auto px-3 py-2"
                        onClick={() => void handleDownloadDocument(document)}
                        disabled={downloadingDocumentId === document.id}
                      >
                        {downloadingDocumentId === document.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Download className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <ScrollArea className="flex-1">
            <div className="space-y-2 p-3.5">
              {loadingSessions ? (
                <div className="py-8 text-center text-sm text-slate-400">
                  正在加载备赛会话...
                </div>
              ) : sessions.length === 0 ? (
                <div className="py-8 text-center text-sm text-slate-400">
                  暂无历史会话
                </div>
              ) : (
                sessions.map((session, index) => (
                  <div
                    key={session.session_id}
                    onClick={() => handleSessionSelect(session.session_id)}
                    className={`cursor-pointer rounded-[12px] border p-3.5 text-left transition-colors duration-150 ${
                      currentSessionId === session.session_id
                        ? 'student-card-soft-blue'
                        : index % 2 === 0
                        ? 'student-card-muted'
                        : 'student-card-soft-peach'
                    }`}
                  >
                    <h4 className="mb-1 truncate text-sm font-medium text-slate-800">
                      {session.title}
                    </h4>
                    <div className="flex items-center text-xs text-slate-400">
                      <MessageSquare className="mr-1 h-3 w-3" />
                      {formatDate(session.updated_at)}
                    </div>
                  </div>
                ))
              )}
            </div>
          </ScrollArea>

          <div className="border-t border-black/5 bg-white/40 p-4">
            <div className="student-card-muted flex items-center gap-3 p-4">
              <div className="student-icon-bubble h-10 w-10 bg-white">
                <User className="h-4 w-4 text-slate-700" />
              </div>
              <div className="min-w-0 flex-1">
                {user?.name ? (
                  <p className="truncate text-sm font-medium text-slate-900">
                    {user.name}
                  </p>
                ) : null}
                <p className="truncate text-xs text-slate-500">备赛区账户</p>
              </div>
            </div>
          </div>
        </aside>

        <section className="student-card flex min-h-[calc(100vh-11rem)] flex-col overflow-hidden">
          <header className="border-b border-black/5 px-5 py-4">
            <div className="flex items-start gap-4">
              <div className="student-icon-bubble h-14 w-14 bg-[#151515] text-white">
                <Bot className="h-6 w-6" />
              </div>
              <div>
                <div className="student-kicker">备赛助手</div>
                <h1 className="mt-3 text-[1.95rem] font-semibold tracking-[-0.05em] text-slate-900">
                  备赛区 AI 助手
                </h1>
                <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-600">
                  基于知识库的辩题资料检索、论点梳理和提问辅助，适合在开赛前快速完成结构化准备。
                </p>
              </div>
            </div>
          </header>

          <ScrollArea ref={scrollAreaRef} className="flex-1 px-5 py-5">
            <div className="mx-auto max-w-5xl space-y-5 pb-4">
              {!currentSessionId && conversations.length === 0 ? (
                <div className="py-10">
                  <div className="student-card-soft-blue mx-auto max-w-3xl p-6 text-center">
                    <div className="student-icon-bubble mx-auto h-16 w-16 bg-white text-slate-900">
                      <BookOpen className="h-9 w-9" />
                    </div>
                    <h2 className="mt-5 text-[1.55rem] font-semibold tracking-[-0.04em] text-slate-900">
                      还没有备赛会话
                    </h2>
                    <p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-slate-600">
                      {documents.length > 0
                        ? '可以先查看左侧资料库，或直接在下方输入问题开始真实会话。'
                        : '当前还没有可展示的备赛内容，输入问题后会生成真实会话记录。'}
                    </p>
                  </div>
                </div>
              ) : loadingHistory ? (
                <div className="flex items-center justify-center py-20 text-slate-500">
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  正在加载会话记录...
                </div>
              ) : conversations.length === 0 ? (
                <div className="py-20 text-center text-slate-500">
                  当前会话还没有消息，试着从下方开始提问。
                </div>
              ) : (
                conversations.map((conversation, index) => (
                  <React.Fragment key={conversation.id || index}>
                    <div className="mb-6 flex justify-end">
                      <div className="max-w-[82%]">
                        <div className="rounded-[14px] rounded-tr-[8px] bg-[#171717] px-4 py-3 text-white shadow-[0_12px_24px_rgba(15,23,42,0.16)]">
                          <p className="text-sm leading-8">{conversation.question}</p>
                        </div>
                        <div className="mr-2 mt-2 text-right text-xs text-slate-400">
                          {formatDate(conversation.created_at)}
                        </div>
                      </div>
                    </div>

                    <div className="mb-6 flex justify-start">
                      <div className="flex max-w-[88%] gap-3">
                        <div className="student-icon-bubble mt-1 h-9 w-9 bg-white text-slate-900">
                          <Bot className="h-4 w-4" />
                        </div>
                        <div className="flex-1">
                          <div className="rounded-[14px] rounded-tl-[8px] border border-black/5 bg-white/85 px-4 py-3 shadow-[0_12px_24px_rgba(15,23,42,0.05)]">
                            {!conversation.answer && loading && index === conversations.length - 1 ? (
                              <div className="text-sm text-slate-500">
                                {streamingAnswer ? (
                                  <p className="whitespace-pre-wrap leading-8">
                                    {streamingAnswer}
                                  </p>
                                ) : (
                                  <div className="flex items-center gap-2">
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    正在整理回答...
                                  </div>
                                )}
                              </div>
                            ) : (
                              <div className="text-sm text-slate-800">
                                <p className="whitespace-pre-wrap leading-8">
                                  {loading &&
                                  index === conversations.length - 1 &&
                                  streamingAnswer
                                    ? streamingAnswer
                                    : conversation.answer}
                                </p>
                                {loading &&
                                index === conversations.length - 1 &&
                                streamingSources.length > 0
                                  ? renderSources(streamingSources)
                                  : renderSources(conversation.sources)}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </React.Fragment>
                ))
              )}
            </div>
          </ScrollArea>

          <div className="border-t border-black/5 bg-white/45 p-5">
            <div className="relative mx-auto max-w-5xl">
              <Textarea
                ref={inputRef}
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="在这里输入关于本场辩论的备赛问题..."
                className="min-h-[112px] resize-none rounded-[14px] border-black/10 bg-white/85 p-4 pr-24 text-[15px] leading-7 focus:border-black/20 focus:ring-black/10"
                disabled={loading}
              />
              <div className="absolute bottom-4 right-4">
                <Button
                  onClick={() => void handleAskQuestion()}
                  disabled={loading || !question.trim()}
                  className="student-dark-button h-auto px-5 py-3"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <>
                      发送
                      <Send className="ml-2 h-4 w-4" />
                    </>
                  )}
                </Button>
              </div>
              <p className="mt-3 text-center text-xs text-slate-400">
                内容由 AI 生成，仅供备赛参考。按 Enter 发送，Shift + Enter 换行。
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

export default PreparationAssistantPage;
