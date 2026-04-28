import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import { Edit, Eye, EyeOff, Loader2, Mic, Save, X } from 'lucide-react';
import AdminService, { type AsrConfig, type AsrConfigUpdate } from '@/services/admin.service';
import { formatErrorMessage } from '@/lib/error-handler';

type AsrFormData = AsrConfigUpdate & {
  language: string;
  file_url_prefix: string;
};

const AsrConfiguration: React.FC = () => {
  const { toast } = useToast();
  const [config, setConfig] = useState<AsrConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);

  const [formData, setFormData] = useState<AsrFormData>({
    model_name: '',
    api_endpoint: '',
    api_key: '',
    language: 'zh',
    file_url_prefix: '',
  });

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const data = await AdminService.getAsrConfig();
      setConfig(data);
      setFormData({
        model_name: data.model_name,
        api_endpoint: data.api_endpoint,
        api_key: data.api_key,
        language: data.parameters?.language ?? 'zh',
        file_url_prefix:
          data.parameters?.file_url_prefix ?? data.parameters?.fileUrlPrefix ?? '',
      });
    } catch (err: any) {
      console.error('Failed to load ASR config:', err);
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
  };

  const handleCancel = () => {
    if (config) {
      setFormData({
        model_name: config.model_name,
        api_endpoint: config.api_endpoint,
        api_key: config.api_key,
        language: config.parameters?.language ?? 'zh',
        file_url_prefix:
          config.parameters?.file_url_prefix ?? config.parameters?.fileUrlPrefix ?? '',
      });
    }
    setIsEditing(false);
  };

  const handleSave = async () => {
    if (!formData.model_name || !formData.api_endpoint || !formData.api_key) {
      toast({
        variant: 'destructive',
        title: '验证失败',
        description: '请填写所有必填字段',
      });
      return;
    }

    if (!formData.language?.trim()) {
      toast({
        variant: 'destructive',
        title: '验证失败',
        description: '语言不能为空',
      });
      return;
    }

    const modelName = formData.model_name.trim();
    const apiEndpoint = formData.api_endpoint.trim();
    const isDashscopeFileTrans =
      (modelName.startsWith('qwen') || modelName.includes('filetrans')) &&
      apiEndpoint.includes('dashscope');
    if (isDashscopeFileTrans && !formData.file_url_prefix.trim()) {
      toast({
        variant: 'destructive',
        title: '验证失败',
        description: '当前ASR为DashScope文件转写模式，请填写音频文件URL前缀',
      });
      return;
    }

    try {
      setSubmitting(true);
      const payload: AsrConfigUpdate = {
        model_name: formData.model_name,
        api_endpoint: formData.api_endpoint,
        api_key: formData.api_key,
        parameters: {
          ...(config?.parameters ?? {}),
          language: formData.language.trim(),
          response_format: 'verbose_json',
          file_url_prefix: formData.file_url_prefix.trim(),
        },
      };
      const updatedConfig = await AdminService.updateAsrConfig(payload);
      setConfig(updatedConfig);
      setIsEditing(false);
      toast({
        variant: 'success',
        title: '更新成功',
        description: 'ASR 配置已更新',
      });
    } catch (err: any) {
      console.error('Failed to update ASR config:', err);
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
                <Mic className="w-5 h-5 text-blue-600" />
                ASR 模型配置
              </CardTitle>
              <CardDescription className="mt-2">
                配置语音识别模型参数与API设置
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
          <div className="space-y-2">
            <Label htmlFor="asr-model-name" className="text-slate-700 font-medium">
              模型名称 *
            </Label>
            <Input
              id="asr-model-name"
              value={formData.model_name}
              onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
              placeholder="例如: whisper-1"
              disabled={!isEditing || submitting}
              className={!isEditing ? 'bg-slate-50' : ''}
            />
          </div>

          <Separator />

          <div className="space-y-2">
            <Label htmlFor="asr-api-endpoint" className="text-slate-700 font-medium">
              API 端点 *
            </Label>
            <Input
              id="asr-api-endpoint"
              value={formData.api_endpoint}
              onChange={(e) => setFormData({ ...formData, api_endpoint: e.target.value })}
              placeholder="https://api.openai.com/v1/audio/transcriptions"
              disabled={!isEditing || submitting}
              className={!isEditing ? 'bg-slate-50' : ''}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="asr-api-key" className="text-slate-700 font-medium">
              API 密钥 *
            </Label>
            <div className="relative">
              <Input
                id="asr-api-key"
                type={showApiKey ? 'text' : 'password'}
                value={formData.api_key}
                onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                placeholder="sk-..."
                disabled={!isEditing || submitting}
                className={!isEditing ? 'bg-slate-50 pr-10' : 'pr-10'}
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <Separator />

          <div className="space-y-2">
            <Label htmlFor="asr-language" className="text-slate-700 font-medium">
              默认语言
            </Label>
            <Input
              id="asr-language"
              value={formData.language}
              onChange={(e) => setFormData({ ...formData, language: e.target.value })}
              placeholder="zh / en / ..."
              disabled={!isEditing || submitting}
              className={!isEditing ? 'bg-slate-50' : ''}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="asr-file-url-prefix" className="text-slate-700 font-medium">
              音频文件URL前缀（DashScope FileTrans需要）
            </Label>
            <Input
              id="asr-file-url-prefix"
              value={formData.file_url_prefix}
              onChange={(e) =>
                setFormData({ ...formData, file_url_prefix: e.target.value })
              }
              placeholder="https://your-domain.com/uploads/asr"
              disabled={!isEditing || submitting}
              className={!isEditing ? 'bg-slate-50' : ''}
            />
          </div>

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
                disabled={submitting}
                className="bg-blue-600 hover:bg-blue-700"
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
    </div>
  );
};

export default AsrConfiguration;
