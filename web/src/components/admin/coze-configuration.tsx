import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import {
  Bot,
  Edit,
  Save,
  X,
  Loader2,
  Eye,
  EyeOff,
  Award,
  MessageSquare
} from 'lucide-react';
import AdminService, { type CozeConfig, type CozeConfigUpdate } from '@/services/admin.service';
import { formatErrorMessage } from '@/lib/error-handler';

const CozeConfiguration: React.FC = () => {
  const { toast } = useToast();
  const [config, setConfig] = useState<CozeConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showApiToken, setShowApiToken] = useState(false);
  
  // 编辑表单数据
  const [formData, setFormData] = useState<CozeConfigUpdate>({
    debater_1_bot_id: '',
    debater_2_bot_id: '',
    debater_3_bot_id: '',
    debater_4_bot_id: '',
    judge_bot_id: '',
    mentor_bot_id: '',
    api_token: '',
    parameters: {}
  });
  
  // 参数JSON字符串（用于编辑）
  const [parametersJson, setParametersJson] = useState('{}');
  const [jsonError, setJsonError] = useState('');

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      
      const data = await AdminService.getCozeConfig();
      setConfig(data);
      setFormData({
        debater_1_bot_id: data.debater_1_bot_id,
        debater_2_bot_id: data.debater_2_bot_id,
        debater_3_bot_id: data.debater_3_bot_id,
        debater_4_bot_id: data.debater_4_bot_id,
        judge_bot_id: data.judge_bot_id,
        mentor_bot_id: data.mentor_bot_id,
        api_token: data.api_token,
        parameters: data.parameters
      });
      setParametersJson(JSON.stringify(data.parameters || {}, null, 2));
    } catch (err: any) {
      console.error('Failed to load Coze config:', err);
      toast({
        variant: 'destructive',
        title: '加载失败',
        description: formatErrorMessage(err),
      });
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = () => {
    setIsEditing(true);
    setJsonError('');
  };

  const handleCancel = () => {
    if (config) {
      setFormData({
        debater_1_bot_id: config.debater_1_bot_id,
        debater_2_bot_id: config.debater_2_bot_id,
        debater_3_bot_id: config.debater_3_bot_id,
        debater_4_bot_id: config.debater_4_bot_id,
        judge_bot_id: config.judge_bot_id,
        mentor_bot_id: config.mentor_bot_id,
        api_token: config.api_token,
        parameters: config.parameters
      });
      setParametersJson(JSON.stringify(config.parameters || {}, null, 2));
    }
    setIsEditing(false);
    setJsonError('');
  };

  const handleParametersChange = (value: string) => {
    setParametersJson(value);
    setJsonError('');
    
    // 尝试解析JSON
    try {
      const parsed = JSON.parse(value);
      setFormData({ ...formData, parameters: parsed });
    } catch (err) {
      setJsonError('JSON 格式错误');
    }
  };

  const handleSave = async () => {
    // 验证 - 至少需要填写 API Token
    if (!formData.api_token) {
      toast({
        variant: 'destructive',
        title: '验证失败',
        description: '请填写 API Token',
      });
      return;
    }

    // 检查是否至少填写了一个 Bot ID
    const hasAnyBotId = formData.debater_1_bot_id || formData.debater_2_bot_id || 
                        formData.debater_3_bot_id || formData.debater_4_bot_id ||
                        formData.judge_bot_id || formData.mentor_bot_id;
    
    if (!hasAnyBotId) {
      toast({
        variant: 'destructive',
        title: '验证失败',
        description: '请至少填写一个 Bot ID',
      });
      return;
    }

    if (jsonError) {
      toast({
        variant: 'destructive',
        title: '验证失败',
        description: '请修正参数的 JSON 格式错误',
      });
      return;
    }

    try {
      setSubmitting(true);
      
      const updatedConfig = await AdminService.updateCozeConfig(formData);
      setConfig(updatedConfig);
      setIsEditing(false);
      toast({
        variant: 'success',
        title: '更新成功',
        description: 'Coze 配置已更新',
      });
    } catch (err: any) {
      console.error('Failed to update Coze config:', err);
      toast({
        variant: 'destructive',
        title: '更新失败',
        description: formatErrorMessage(err),
      });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Bot className="w-5 h-5 text-purple-600" />
                Coze 代理配置
              </CardTitle>
              <CardDescription className="mt-2">
                配置 Coze AI 代理的连接参数和设置
              </CardDescription>
            </div>
            {!isEditing && (
              <Button onClick={handleEdit} variant="outline">
                <Edit className="w-4 h-4 mr-2" />
                编辑配置
              </Button>
            )}
          </div>
        </CardHeader>
        
        <CardContent className="space-y-6">
          {/* AI 辩手配置 */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 mb-4">
              <Bot className="w-5 h-5 text-blue-600" />
              <h3 className="font-semibold text-slate-800">AI 辩手配置</h3>
            </div>
            
            {/* 反方一辩 */}
            <div className="space-y-2">
              <Label htmlFor="debater-1" className="text-slate-700 font-medium">
                反方一辩 Bot ID
              </Label>
              <Input
                id="debater-1"
                value={formData.debater_1_bot_id}
                onChange={(e) => setFormData({ ...formData, debater_1_bot_id: e.target.value })}
                placeholder="例如: 7428xxxxxx"
                disabled={!isEditing || submitting}
                className={!isEditing ? 'bg-slate-50' : ''}
              />
              <p className="text-xs text-slate-500">
                负责立论陈述的 AI 辩手
              </p>
            </div>

            {/* 反方二辩 */}
            <div className="space-y-2">
              <Label htmlFor="debater-2" className="text-slate-700 font-medium">
                反方二辩 Bot ID
              </Label>
              <Input
                id="debater-2"
                value={formData.debater_2_bot_id}
                onChange={(e) => setFormData({ ...formData, debater_2_bot_id: e.target.value })}
                placeholder="例如: 7428xxxxxx"
                disabled={!isEditing || submitting}
                className={!isEditing ? 'bg-slate-50' : ''}
              />
              <p className="text-xs text-slate-500">
                负责盘问质询的 AI 辩手
              </p>
            </div>

            {/* 反方三辩 */}
            <div className="space-y-2">
              <Label htmlFor="debater-3" className="text-slate-700 font-medium">
                反方三辩 Bot ID
              </Label>
              <Input
                id="debater-3"
                value={formData.debater_3_bot_id}
                onChange={(e) => setFormData({ ...formData, debater_3_bot_id: e.target.value })}
                placeholder="例如: 7428xxxxxx"
                disabled={!isEditing || submitting}
                className={!isEditing ? 'bg-slate-50' : ''}
              />
              <p className="text-xs text-slate-500">
                负责高压攻击追问的 AI 辩手
              </p>
            </div>

            {/* 反方四辩 */}
            <div className="space-y-2">
              <Label htmlFor="debater-4" className="text-slate-700 font-medium">
                反方四辩 Bot ID
              </Label>
              <Input
                id="debater-4"
                value={formData.debater_4_bot_id}
                onChange={(e) => setFormData({ ...formData, debater_4_bot_id: e.target.value })}
                placeholder="例如: 7428xxxxxx"
                disabled={!isEditing || submitting}
                className={!isEditing ? 'bg-slate-50' : ''}
              />
              <p className="text-xs text-slate-500">
                负责总结陈词的 AI 辩手
              </p>
            </div>
          </div>

          <Separator />

          {/* 裁判 AI 配置 */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 mb-4">
              <Award className="w-5 h-5 text-purple-600" />
              <h3 className="font-semibold text-slate-800">裁判 AI 配置</h3>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="judge" className="text-slate-700 font-medium">
                裁判 Bot ID
              </Label>
              <Input
                id="judge"
                value={formData.judge_bot_id}
                onChange={(e) => setFormData({ ...formData, judge_bot_id: e.target.value })}
                placeholder="例如: 7428xxxxxx"
                disabled={!isEditing || submitting}
                className={!isEditing ? 'bg-slate-50' : ''}
              />
              <p className="text-xs text-slate-500">
                负责评分和裁决的 AI 裁判
              </p>
            </div>
          </div>

          <Separator />

          {/* 辅助 AI 配置 */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 mb-4">
              <MessageSquare className="w-5 h-5 text-green-600" />
              <h3 className="font-semibold text-slate-800">辅助 AI 配置</h3>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="mentor" className="text-slate-700 font-medium">
                辅助/导师 Bot ID
              </Label>
              <Input
                id="mentor"
                value={formData.mentor_bot_id}
                onChange={(e) => setFormData({ ...formData, mentor_bot_id: e.target.value })}
                placeholder="例如: 7428xxxxxx"
                disabled={!isEditing || submitting}
                className={!isEditing ? 'bg-slate-50' : ''}
              />
              <p className="text-xs text-slate-500">
                提供实时建议和指导的辅助 AI
              </p>
            </div>
          </div>

          <Separator />

          {/* API 令牌 */}
          <div className="space-y-2">
            <Label htmlFor="api-token" className="text-slate-700 font-medium">
              API 令牌 (API Token) *
            </Label>
            <div className="relative">
              <Input
                id="api-token"
                type={showApiToken ? 'text' : 'password'}
                value={formData.api_token}
                onChange={(e) => setFormData({ ...formData, api_token: e.target.value })}
                placeholder="pat_..."
                disabled={!isEditing || submitting}
                className={!isEditing ? 'bg-slate-50 pr-10' : 'pr-10'}
              />
              <button
                type="button"
                onClick={() => setShowApiToken(!showApiToken)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                {showApiToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-xs text-slate-500">
              用于访问 Coze API 的个人访问令牌
            </p>
          </div>

          <Separator />

          {/* 其他参数 */}
          <div className="space-y-2">
            <Label htmlFor="parameters" className="text-slate-700 font-medium">
              其他参数 (JSON 格式)
            </Label>
            <Textarea
              id="parameters"
              value={parametersJson}
              onChange={(e) => handleParametersChange(e.target.value)}
              placeholder='{\n  "timeout": 30,\n  "max_retries": 3\n}'
              disabled={!isEditing || submitting}
              className={`font-mono text-sm min-h-[200px] ${!isEditing ? 'bg-slate-50' : ''}`}
            />
            {jsonError && (
              <p className="text-xs text-red-600">{jsonError}</p>
            )}
            <p className="text-xs text-slate-500">
              以 JSON 格式配置额外的参数，例如超时时间、重试次数等
            </p>
          </div>

          {/* 配置信息 */}
          {config && !isEditing && (
            <>
              <Separator />
              <div className="grid grid-cols-2 gap-4 text-sm text-slate-600">
                <div>
                  <span className="font-medium">创建时间:</span>{' '}
                  {new Date(config.created_at).toLocaleString('zh-CN')}
                </div>
                <div>
                  <span className="font-medium">更新时间:</span>{' '}
                  {new Date(config.updated_at).toLocaleString('zh-CN')}
                </div>
              </div>
            </>
          )}

          {/* 操作按钮 */}
          {isEditing && (
            <div className="flex justify-end gap-3 pt-4">
              <Button
                variant="outline"
                onClick={handleCancel}
                disabled={submitting}
              >
                <X className="w-4 h-4 mr-2" />
                取消
              </Button>
              <Button
                onClick={handleSave}
                disabled={submitting || !!jsonError}
                className="bg-purple-600 hover:bg-purple-700"
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    保存中...
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4 mr-2" />
                    保存配置
                  </>
                )}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 使用说明 */}
      <Card className="bg-blue-50 border-blue-200">
        <CardContent className="p-4">
          <h4 className="font-medium text-blue-900 mb-2">配置说明</h4>
          <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
            <li>需要在 Coze 平台创建 6 个不同的 Bot：4 个 AI 辩手、1 个裁判、1 个辅助 AI</li>
            <li>每个 Bot ID 可以在 Coze 平台的 Bot 详情页面找到</li>
            <li>API Token 需要在 Coze 平台的个人设置中生成</li>
            <li>确保 API Token 具有访问所有 Bot 的权限</li>
            <li>4 个 AI 辩手分别负责：立论、盘问、攻击追问、总结陈词</li>
            <li>裁判 AI 负责实时评分和裁决</li>
            <li>辅助 AI 为学生提供实时建议和指导</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
};

export default CozeConfiguration;
