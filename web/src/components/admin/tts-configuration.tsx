import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import { Edit, Eye, EyeOff, Loader2, Save, Volume2, X } from 'lucide-react';
import AdminService, { type TtsConfig, type TtsConfigUpdate } from '@/services/admin.service';
import { formatErrorMessage } from '@/lib/error-handler';

type TtsFormData = TtsConfigUpdate & {
  voice: string;
  speed: number;
};

const TtsConfiguration: React.FC = () => {
  const { toast } = useToast();
  const [config, setConfig] = useState<TtsConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);

  const [formData, setFormData] = useState<TtsFormData>({
    model_name: '',
    api_endpoint: '',
    api_key: '',
    voice: 'Cherry',
    speed: 0,
  });

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const data = await AdminService.getTtsConfig();
      setConfig(data);
      setFormData({
        model_name: data.model_name,
        api_endpoint: data.api_endpoint,
        api_key: data.api_key,
        voice: data.parameters?.voice ?? 'Cherry',
        speed: typeof data.parameters?.speed === 'number' ? data.parameters.speed : 0,
      });
    } catch (err: any) {
      console.error('Failed to load TTS config:', err);
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
        voice: config.parameters?.voice ?? 'Cherry',
        speed: typeof config.parameters?.speed === 'number' ? config.parameters.speed : 0,
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

    if (!formData.voice?.trim()) {
      toast({
        variant: 'destructive',
        title: '验证失败',
        description: '语音ID不能为空',
      });
      return;
    }

    if (Number.isNaN(formData.speed) || formData.speed < 0.25 || formData.speed > 4.0) {
      toast({
        variant: 'destructive',
        title: '验证失败',
        description: '语速必须在 0.25 到 4.0 之间',
      });
      return;
    }

    try {
      setSubmitting(true);
      const payload: TtsConfigUpdate = {
        model_name: formData.model_name,
        api_endpoint: formData.api_endpoint,
        api_key: formData.api_key,
        parameters: {
          ...(config?.parameters ?? {}),
          voice: formData.voice.trim(),
          speed: formData.speed,
          response_format: 'mp3',
        },
      };
      const updatedConfig = await AdminService.updateTtsConfig(payload);
      setConfig(updatedConfig);
      setIsEditing(false);
      toast({
        variant: 'success',
        title: '更新成功',
        description: 'TTS 配置已更新',
      });
    } catch (err: any) {
      console.error('Failed to update TTS config:', err);
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
                <Volume2 className="w-5 h-5 text-blue-600" />
                TTS 模型配置
              </CardTitle>
              <CardDescription className="mt-2">
                配置语音合成模型参数与API设置
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
            <Label htmlFor="tts-model-name" className="text-slate-700 font-medium">
              模型名称 *
            </Label>
            <Input
              id="tts-model-name"
              value={formData.model_name}
              onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
              placeholder="例如: tts-1"
              disabled={!isEditing || submitting}
              className={!isEditing ? 'bg-slate-50' : ''}
            />
          </div>

          <Separator />

          <div className="space-y-2">
            <Label htmlFor="tts-api-endpoint" className="text-slate-700 font-medium">
              API 端点 *
            </Label>
            <Input
              id="tts-api-endpoint"
              value={formData.api_endpoint}
              onChange={(e) => setFormData({ ...formData, api_endpoint: e.target.value })}
              placeholder="https://api.openai.com/v1/audio/speech"
              disabled={!isEditing || submitting}
              className={!isEditing ? 'bg-slate-50' : ''}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="tts-api-key" className="text-slate-700 font-medium">
              API 密钥 *
            </Label>
            <div className="relative">
              <Input
                id="tts-api-key"
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

          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label htmlFor="tts-voice" className="text-slate-700 font-medium">
                默认语音ID
              </Label>
              <Input
                id="tts-voice"
                value={formData.voice}
                onChange={(e) => setFormData({ ...formData, voice: e.target.value })}
                placeholder="alloy / nova / ..."
                disabled={!isEditing || submitting}
                className={!isEditing ? 'bg-slate-50' : ''}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="tts-speed" className="text-slate-700 font-medium">
                默认语速
              </Label>
              <Input
                id="tts-speed"
                type="number"
                min="0.25"
                max="4"
                step="0.05"
                value={formData.speed}
                onChange={(e) => setFormData({ ...formData, speed: Number(e.target.value) })}
                disabled={!isEditing || submitting}
                className={!isEditing ? 'bg-slate-50' : ''}
              />
            </div>
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

export default TtsConfiguration;
