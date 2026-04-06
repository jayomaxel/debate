import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import {
  Database,
  Edit,
  Save,
  X,
  Loader2,
  Eye,
  EyeOff
} from 'lucide-react';
import AdminService, { type ModelConfig, type ModelConfigUpdate } from '@/services/admin.service';
import { formatErrorMessage } from '@/lib/error-handler';

const ModelConfiguration: React.FC = () => {
  const { toast } = useToast();
  const [config, setConfig] = useState<ModelConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  
  // 编辑表单数据
  const [formData, setFormData] = useState<ModelConfigUpdate>({
    model_name: '',
    api_endpoint: '',
    api_key: '',
    temperature: 0.7,
    max_tokens: 2000
  });

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      
      const data = await AdminService.getModelConfig();
      setConfig(data);
      setFormData({
        model_name: data.model_name,
        api_endpoint: data.api_endpoint,
        api_key: data.api_key,
        temperature: data.temperature,
        max_tokens: data.max_tokens
      });
    } catch (err: any) {
      console.error('Failed to load model config:', err);
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
        temperature: config.temperature,
        max_tokens: config.max_tokens
      });
    }
    setIsEditing(false);
  };

  const handleSave = async () => {
    // 验证
    if (!formData.model_name || !formData.api_endpoint || !formData.api_key) {
      toast({
        variant: 'destructive',
        title: '验证失败',
        description: '请填写所有必填字段',
      });
      return;
    }

    if (formData.temperature !== undefined && (formData.temperature < 0 || formData.temperature > 2)) {
      toast({
        variant: 'destructive',
        title: '验证失败',
        description: '温度参数必须在 0.0 到 2.0 之间',
      });
      return;
    }

    if (formData.max_tokens !== undefined && formData.max_tokens < 1) {
      toast({
        variant: 'destructive',
        title: '验证失败',
        description: '最大令牌数必须大于 0',
      });
      return;
    }

    try {
      setSubmitting(true);
      
      const updatedConfig = await AdminService.updateModelConfig(formData);
      setConfig(updatedConfig);
      setIsEditing(false);
      toast({
        variant: 'success',
        title: '更新成功',
        description: '模型配置已更新',
      });
    } catch (err: any) {
      console.error('Failed to update model config:', err);
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
                <Database className="w-5 h-5 text-blue-600" />
                AI 模型配置
              </CardTitle>
              <CardDescription className="mt-2">
                配置系统使用的AI模型参数和API设置
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
          {/* 模型名称 */}
          <div className="space-y-2">
            <Label htmlFor="model-name" className="text-slate-700 font-medium">
              模型名称 *
            </Label>
            <Input
              id="model-name"
              value={formData.model_name}
              onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
              placeholder="例如: gpt-4, claude-3-opus"
              disabled={!isEditing || submitting}
              className={!isEditing ? 'bg-slate-50' : ''}
            />
          </div>

          <Separator />

          {/* API 端点 */}
          <div className="space-y-2">
            <Label htmlFor="api-endpoint" className="text-slate-700 font-medium">
              API 端点 *
            </Label>
            <Input
              id="api-endpoint"
              value={formData.api_endpoint}
              onChange={(e) => setFormData({ ...formData, api_endpoint: e.target.value })}
              placeholder="https://api.example.com/v1"
              disabled={!isEditing || submitting}
              className={!isEditing ? 'bg-slate-50' : ''}
            />
          </div>

          {/* API 密钥 */}
          <div className="space-y-2">
            <Label htmlFor="api-key" className="text-slate-700 font-medium">
              API 密钥 *
            </Label>
            <div className="relative">
              <Input
                id="api-key"
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

          {/* 模型参数 */}
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label htmlFor="temperature" className="text-slate-700 font-medium">
                温度参数 (Temperature)
              </Label>
              <Input
                id="temperature"
                type="number"
                step="0.1"
                min="0"
                max="2"
                value={formData.temperature}
                onChange={(e) => setFormData({ ...formData, temperature: parseFloat(e.target.value) })}
                disabled={!isEditing || submitting}
                className={!isEditing ? 'bg-slate-50' : ''}
              />
              <p className="text-xs text-slate-500">
                范围: 0.0 - 2.0，值越高输出越随机
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="max-tokens" className="text-slate-700 font-medium">
                最大令牌数 (Max Tokens)
              </Label>
              <Input
                id="max-tokens"
                type="number"
                min="1"
                value={formData.max_tokens}
                onChange={(e) => setFormData({ ...formData, max_tokens: parseInt(e.target.value) })}
                disabled={!isEditing || submitting}
                className={!isEditing ? 'bg-slate-50' : ''}
              />
              <p className="text-xs text-slate-500">
                生成文本的最大长度
              </p>
            </div>
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

export default ModelConfiguration;
