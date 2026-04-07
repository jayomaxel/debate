import React, { useState, useEffect, useRef } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Loader2,
  Send,
  BookOpen,
  AlertCircle,
  FileText,
  TrendingUp,
  TrendingDown
} from 'lucide-react';
import StudentService, { type Conversation, type KBSource } from '@/services/student.service';
import { formatErrorMessage } from '@/lib/error-handler';
import { useToast } from '@/hooks/use-toast';

interface PreparationAssistantProps {
  onClose?: () => void;
}

const PreparationAssistant: React.FC<PreparationAssistantProps> = ({ onClose }) => {
  const { toast } = useToast();
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [question, setQuestion] = useState('');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [error, setError] = useState<string>('');
  const [sessionId] = useState(() => `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);

  useEffect(() => {
    loadConversationHistory();
  }, []);

  useEffect(() => {
    // Auto-scroll to bottom when new messages arrive
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
    }
  }, [conversations]);

  const loadConversationHistory = async () => {
    try {
      setLoadingHistory(true);
      setError('');
      
      const history = await StudentService.getKBConversationHistory(sessionId);
      if (Array.isArray(history)) {
        setConversations(history);
      } else {
        console.error('Invalid history format:', history);
        setConversations([]);
      }
    } catch (err: any) {
      console.error('Failed to load conversation history:', err);
      // Don't show error for empty history
      if (err.response?.status !== 404) {
        setError(formatErrorMessage(err));
      }
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleAskQuestion = async () => {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      toast({
        variant: 'destructive',
        title: '提问失败',
        description: '问题不能为空',
        duration: 3000
      });
      return;
    }

    try {
      setLoading(true);
      setError('');

      // Optimistic update - add question to UI immediately
      const tempConversation: Conversation = {
        id: `temp_${Date.now()}`,
        question: trimmedQuestion,
        answer: '',
        sources: [],
        created_at: new Date().toISOString()
      };
      setConversations(prev => [...prev, tempConversation]);
      setQuestion('');

      // Call API
      const response = await StudentService.askKBQuestion(trimmedQuestion, sessionId);

      // Update with real answer
      setConversations(prev => {
        const updated = [...prev];
        const lastIndex = updated.length - 1;
        updated[lastIndex] = {
          ...updated[lastIndex],
          answer: response.answer,
          sources: response.sources
        };
        return updated;
      });

      // Focus input for next question
      inputRef.current?.focus();
    } catch (err: any) {
      console.error('Failed to ask question:', err);
      
      // Remove optimistic update on error
      setConversations(prev => prev.slice(0, -1));
      setQuestion(trimmedQuestion); // Restore question
      
      toast({
        variant: 'destructive',
        title: '提问失败',
        description: formatErrorMessage(err),
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
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

  const renderSources = (sources: KBSource[], usedKb: boolean) => {
    if (!sources || sources.length === 0) {
      return (
        <div className="mt-3 pt-3 border-t border-slate-200">
          <Badge variant="outline" className="bg-slate-50 text-slate-600">
            <BookOpen className="w-3 h-3 mr-1" />
            基于通用知识
          </Badge>
        </div>
      );
    }

    return (
      <div className="mt-3 pt-3 border-t border-slate-200 space-y-2">
        <div className="flex items-center gap-2 mb-2">
          <Badge className="bg-blue-100 text-blue-700 border-blue-200">
            <FileText className="w-3 h-3 mr-1" />
            基于知识库
          </Badge>
          <span className="text-xs text-slate-500">
            {sources.length} 个相关文档
          </span>
        </div>
        
        {sources.map((source, index) => (
          <div key={index} className="bg-slate-50 rounded-lg p-3 text-sm">
            <div className="flex items-start justify-between mb-1">
              <span className="font-medium text-slate-700 flex items-center">
                <FileText className="w-3 h-3 mr-1" />
                {source.document_name}
              </span>
              <div className="flex items-center gap-1">
                {source.similarity_score >= 0.8 ? (
                  <TrendingUp className="w-3 h-3 text-green-600" />
                ) : (
                  <TrendingDown className="w-3 h-3 text-yellow-600" />
                )}
                <span className="text-xs text-slate-500">
                  {(source.similarity_score * 100).toFixed(0)}%
                </span>
              </div>
            </div>
            <p className="text-slate-600 text-xs line-clamp-2">
              {source.excerpt}
            </p>
          </div>
        ))}
      </div>
    );
  };

  // Check if conversations is an array before using map
  const safeConversations = Array.isArray(conversations) ? conversations : [];

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-6xl h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-blue-600" />
            备战辅助
          </DialogTitle>
        </DialogHeader>

        {/* Error Alert */}
        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Conversation History */}
        <ScrollArea ref={scrollAreaRef} className="flex-1 pr-4">
          {loadingHistory ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
            </div>
          ) : safeConversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <BookOpen className="w-16 h-16 text-slate-300 mb-4" />
              <h3 className="text-lg font-medium text-slate-700 mb-2">
                欢迎使用备战辅助
              </h3>
              <p className="text-sm text-slate-500 max-w-md">
                您可以向知识库提问，获取辩论相关的学习资料和建议。
                <br />
                系统会优先从知识库中检索相关内容为您解答。
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {safeConversations.map((conv) => (
                <div key={conv.id} className="space-y-3">
                  {/* Question */}
                  <div className="flex justify-end">
                    <div className="bg-blue-600 text-white rounded-lg px-4 py-3 max-w-[80%]">
                      <p className="text-sm">{conv.question}</p>
                      <span className="text-xs text-blue-100 mt-1 block">
                        {formatDate(conv.created_at)}
                      </span>
                    </div>
                  </div>

                  {/* Answer */}
                  {conv.answer ? (
                    <div className="flex justify-start">
                      <div className="bg-slate-100 rounded-lg px-4 py-3 max-w-[80%]">
                        <p className="text-sm text-slate-800 whitespace-pre-wrap">
                          {conv.answer}
                        </p>
                        {renderSources(conv.sources, conv.sources.length > 0)}
                      </div>
                    </div>
                  ) : (
                    <div className="flex justify-start">
                      <div className="bg-slate-100 rounded-lg px-4 py-3">
                        <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </ScrollArea>

        {/* Question Input */}
        <div className="flex gap-2 pt-4 border-t">
          <Input
            ref={inputRef}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="输入您的问题..."
            disabled={loading}
            className="flex-1"
          />
          <Button
            onClick={handleAskQuestion}
            disabled={loading || !question.trim()}
            className="bg-blue-600 hover:bg-blue-700"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <Send className="w-4 h-4 mr-2" />
                提问
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default PreparationAssistant;
