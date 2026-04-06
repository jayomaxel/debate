import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import {
  Loader2,
  Send,
  BookOpen,
  MessageSquare,
  Plus,
  ArrowLeft,
  FileText,
  TrendingUp,
  TrendingDown,
  User,
  Bot
} from 'lucide-react';
import StudentService, { type Conversation, type KBSource, type KBSession } from '@/services/student.service';
import { formatErrorMessage } from '@/lib/error-handler';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/store/auth.context';
import TokenManager from '@/lib/token-manager';

interface PreparationAssistantPageProps {
  onBack: () => void;
}

const PreparationAssistantPage: React.FC<PreparationAssistantPageProps> = ({ onBack }) => {
  const { toast } = useToast();
  const { user } = useAuth();
  
  // State
  const [sessions, setSessions] = useState<KBSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [streamingAnswer, setStreamingAnswer] = useState('');
  const [streamingSources, setStreamingSources] = useState<KBSource[]>([]);

  // Refs
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load sessions on mount
  useEffect(() => {
    loadSessions();
  }, []);

  // Load history when session changes
  useEffect(() => {
    if (currentSessionId) {
      loadConversationHistory(currentSessionId);
    } else {
      setConversations([]);
    }
  }, [currentSessionId]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
    }
  }, [conversations, streamingAnswer]);

  const loadSessions = async () => {
    try {
      const data = await StudentService.getKBSessions();
      setSessions(data);
      if (data.length > 0 && !currentSessionId) {
        // Select first session by default if none selected
        // Or keep it null to show welcome screen
        // setCurrentSessionId(data[0].session_id);
      }
    } catch (err: any) {
      console.error('Failed to load sessions:', err);
    }
  };

  const loadConversationHistory = async (sessionId: string) => {
    try {
      setLoadingHistory(true);
      const history = await StudentService.getKBConversationHistory(sessionId);
      if (Array.isArray(history)) {
        // Reverse history to show oldest first (top) -> newest last (bottom)
        // Backend returns newest first.
        setConversations(history.reverse());
      } else {
        setConversations([]);
      }
    } catch (err: any) {
      console.error('Failed to load history:', err);
      setConversations([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleNewChat = () => {
    setCurrentSessionId(null);
    setConversations([]);
    setQuestion('');
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  const handleSessionSelect = (sessionId: string) => {
    if (sessionId === currentSessionId) return;
    setCurrentSessionId(sessionId);
  };

  const handleAskQuestion = async () => {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) return;

    // If no session, create one ID (will be saved in backend on first message)
    let sessionId = currentSessionId;
    if (!sessionId) {
      sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      setCurrentSessionId(sessionId);
    }

    try {
      setLoading(true);
      setQuestion('');
      setStreamingAnswer('');
      setStreamingSources([]);

      // Optimistic update: Add user question
      const tempUserMsg: Conversation = {
        id: `temp_${Date.now()}`,
        question: trimmedQuestion,
        answer: '',
        sources: [],
        created_at: new Date().toISOString()
      };
      setConversations(prev => [...prev, tempUserMsg]);

      // Prepare for streaming
      const token = TokenManager.getAccessToken();
      const response = await fetch('/api/student/kb/ask/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          question: trimmedQuestion,
          session_id: sessionId
        })
      });

      if (!response.ok) {
        throw new Error(`Error: ${response.statusText}`);
      }

      if (!response.body) return;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let answerAcc = '';
      let sourcesAcc: KBSource[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            try {
              const event = JSON.parse(dataStr);
              if (event.type === 'sources') {
                sourcesAcc = Array.isArray(event.data) ? event.data : [];
                setStreamingSources(sourcesAcc);
              } else if (event.type === 'answer') {
                const content = typeof event.content === 'string' ? event.content : '';
                answerAcc += content;
                setStreamingAnswer(answerAcc);
              } else if (event.type === 'done') {
                setConversations(prev => {
                  const newArr = [...prev];
                  const lastIdx = newArr.length - 1;
                  if (lastIdx >= 0) {
                    newArr[lastIdx] = {
                      ...newArr[lastIdx],
                      id: event.id,
                      answer: answerAcc,
                      sources: sourcesAcc
                    };
                  }
                  return newArr;
                });

                if (!sessions.find(s => s.session_id === sessionId)) {
                  loadSessions();
                }
              } else if (event.type === 'error') {
                toast({
                  variant: 'destructive',
                  title: '生成出错',
                  description: event.message
                });
              }
            } catch (e) {
              console.error('Error parsing SSE:', e);
            }
          }
        }
      }
      setConversations(prev => {
        const newArr = [...prev];
        const lastIdx = newArr.length - 1;
        if (lastIdx >= 0) {
          newArr[lastIdx] = {
            ...newArr[lastIdx],
            answer: answerAcc,
            sources: sourcesAcc
          };
        }
        return newArr;
      });

    } catch (err: any) {
      console.error('Failed to ask question:', err);
      toast({
        variant: 'destructive',
        title: '提问失败',
        description: formatErrorMessage(err),
      });
      // Remove temp message
      setConversations(prev => prev.slice(0, -1));
      setQuestion(trimmedQuestion);
    } finally {
      setLoading(false);
      setStreamingAnswer('');
      setStreamingSources([]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAskQuestion();
    }
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const renderSources = (sources: KBSource[]) => {
    if (!sources || sources.length === 0) return null;

    return (
      <div className="mt-3 pt-3 border-t border-slate-200 space-y-2">
        <div className="flex items-center gap-2 mb-2">
          <Badge className="bg-blue-100 text-blue-700 border-blue-200">
            <FileText className="w-3 h-3 mr-1" />
            参考资料
          </Badge>
          <span className="text-xs text-slate-500">
            {sources.length} 个相关文档
          </span>
        </div>
        
        <div className="grid grid-cols-1 gap-2">
          {sources.map((source, index) => (
            <div key={index} className="bg-slate-50 rounded p-2 text-xs border border-slate-100">
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium text-slate-700 truncate max-w-[200px]" title={source.document_name}>
                  {source.document_name}
                </span>
                <span className="text-slate-400">
                  {(source.similarity_score * 100).toFixed(0)}%
                </span>
              </div>
              <p className="text-slate-500 line-clamp-1" title={source.chunk_content}>
                {source.chunk_content}
              </p>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      {/* Left Sidebar */}
      <div className="w-72 bg-white border-r border-slate-200 flex flex-col">
        <div className="p-4 border-b border-slate-100">
          <Button 
            onClick={onBack} 
            variant="ghost" 
            size="sm" 
            className="mb-4 text-slate-500 hover:text-slate-900 -ml-2"
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            返回控制台
          </Button>
          
          <Button 
            onClick={handleNewChat}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white shadow-sm"
          >
            <Plus className="w-4 h-4 mr-2" />
            开启新对话
          </Button>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-3 space-y-2">
            {sessions.length === 0 ? (
              <div className="text-center py-8 text-slate-400 text-sm">
                暂无历史对话
              </div>
            ) : (
              sessions.map((session) => (
                <div
                  key={session.session_id}
                  onClick={() => handleSessionSelect(session.session_id)}
                  className={`
                    p-3 rounded-lg cursor-pointer transition-colors text-left
                    ${currentSessionId === session.session_id 
                      ? 'bg-blue-50 border-blue-200 border' 
                      : 'hover:bg-slate-50 border border-transparent'}
                  `}
                >
                  <h4 className={`text-sm font-medium mb-1 truncate ${
                    currentSessionId === session.session_id ? 'text-blue-700' : 'text-slate-700'
                  }`}>
                    {session.title}
                  </h4>
                  <div className="flex items-center text-xs text-slate-400">
                    <MessageSquare className="w-3 h-3 mr-1" />
                    {formatDate(session.updated_at)}
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
        
        <div className="p-4 border-t border-slate-100 bg-slate-50">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
              <User className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-slate-900 truncate">{user?.name || 'Student'}</p>
              <p className="text-xs text-slate-500 truncate">Student Account</p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col h-full relative">
        {/* Header */}
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 shadow-sm z-10">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Bot className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900">备战辅助助手</h1>
              <p className="text-xs text-slate-500">基于知识库的智能问答系统</p>
            </div>
          </div>
        </header>

        {/* Chat Area */}
        <ScrollArea ref={scrollAreaRef} className="flex-1 p-6 bg-slate-50/50">
          <div className="max-w-6xl mx-auto space-y-6 pb-4">
            {!currentSessionId && conversations.length === 0 ? (
              <div className="text-center py-20">
                <div className="w-20 h-20 bg-white rounded-2xl shadow-sm border border-slate-100 flex items-center justify-center mx-auto mb-6">
                  <BookOpen className="w-10 h-10 text-blue-500" />
                </div>
                <h2 className="text-2xl font-bold text-slate-900 mb-3">
                  你好，我是你的辩论备战助手 👋
                </h2>
                <p className="text-slate-500 max-w-md mx-auto mb-8">
                  我可以帮你查找辩论资料、分析辩题、提供论据建议。
                  <br />
                  请在下方输入你的问题，我会基于知识库为你解答。
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl mx-auto">
                  {[
                    "什么是稳定币？",
                    "如何反驳'技术中立论'？",
                    "请列举关于监管政策的论据",
                    "辩论中的核心论点怎么构建？"
                  ].map((q, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        setQuestion(q);
                        // Optional: auto send?
                      }}
                      className="p-4 bg-white border border-slate-200 rounded-xl text-left hover:border-blue-300 hover:shadow-sm transition-all text-sm text-slate-700"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              conversations.map((conv, idx) => (
                <React.Fragment key={conv.id || idx}>
                  {/* User Question */}
                  <div className="flex justify-end mb-6">
                    <div className="max-w-[80%]">
                      <div className="bg-blue-600 text-white rounded-2xl rounded-tr-sm px-5 py-4 shadow-sm">
                        <p className="text-sm leading-relaxed">{conv.question}</p>
                      </div>
                      <div className="text-right mt-1 text-xs text-slate-400 mr-1">
                        {formatDate(conv.created_at)}
                      </div>
                    </div>
                  </div>

                  {/* AI Answer */}
                  <div className="flex justify-start mb-6">
                    <div className="flex gap-3 max-w-[85%]">
                      <div className="w-8 h-8 rounded-full bg-white border border-slate-200 flex items-center justify-center flex-shrink-0 mt-1">
                        <Bot className="w-4 h-4 text-blue-600" />
                      </div>
                      <div className="flex-1">
                        <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-sm px-5 py-4 shadow-sm">
                          {!conv.answer && loading && idx === conversations.length - 1 ? (
                            <div className="flex items-center gap-2 text-slate-500 text-sm">
                              {streamingAnswer ? (
                                <p className="whitespace-pre-wrap leading-relaxed">{streamingAnswer}</p>
                              ) : (
                                <>
                                  <Loader2 className="w-4 h-4 animate-spin" />
                                  正在思考中...
                                </>
                              )}
                            </div>
                          ) : (
                            <div className="text-sm text-slate-800">
                              <p className="whitespace-pre-wrap leading-relaxed">
                                {loading && idx === conversations.length - 1 && streamingAnswer 
                                  ? streamingAnswer 
                                  : conv.answer}
                              </p>
                              {/* Show sources if available */}
                              {loading && idx === conversations.length - 1 && streamingSources.length > 0 
                                ? renderSources(streamingSources)
                                : renderSources(conv.sources)}
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

        {/* Input Area */}
        <div className="p-6 bg-white border-t border-slate-200">
          <div className="max-w-6xl mx-auto relative">
            <Textarea
              ref={inputRef}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="在此输入关于辩论的问题..."
              className="min-h-[100px] pr-24 resize-none text-base p-4 rounded-xl border-slate-300 focus:border-blue-500 focus:ring-blue-500"
              disabled={loading}
            />
            <div className="absolute bottom-4 right-4">
              <Button
                onClick={handleAskQuestion}
                disabled={loading || !question.trim()}
                className="bg-blue-600 hover:bg-blue-700 text-white rounded-lg px-4"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    发送 <Send className="w-4 h-4 ml-2" />
                  </>
                )}
              </Button>
            </div>
            <p className="text-xs text-slate-400 mt-2 text-center">
              内容由AI生成，仅供参考。按 Enter 发送，Shift + Enter 换行。
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PreparationAssistantPage;
