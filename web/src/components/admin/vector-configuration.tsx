import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import { Edit, Eye, EyeOff, Loader2, Save, Database, X } from 'lucide-react';
import AdminService, { type VectorConfig, type VectorConfigUpdate } from '@/services/admin.service';
import { formatErrorMessage } from '@/lib/error-handler';

const VectorConfiguration: React.FC = () => {
  const { toast } = useToast();
  const [config, setConfig] = useState<VectorConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);

  const [formData, setFormData] = useState<VectorConfigUpdate>({
    model_name: '',
    api_endpoint: '',
    api_key: '',
    embedding_dimension: 1536,
  });

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const data = await AdminService.getVectorConfig();
      setConfig(data);
      setFormData({
        model_name: data.model_name,
        api_endpoint: data.api_endpoint,
        api_key: data.api_key,
        embedding_dimension: data.embedding_dimension,
      });
    } catch (err: any) {
      console.error('Failed to load vector config:', err);
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
        embedding_dimension: config.embedding_dimension,
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

    if (!formData.embedding_dimension || formData.embedding_dimension <= 0) {
      toast({
        variant: 'destructive',
        title: '验证失败',
        description: '向量维度必须大于0',
      });
      return;
    }

    try {
      setSubmitting(true);
      const updatedConfig = await AdminService.updateVectorConfig(formData);
      setConfig(updatedConfig);
      setIsEditing(false);
      toast({
        variant: 'success',
        title: '更新成功',
        description: '向量模型配置已更新',
      });
    } catch (err: any) {
      console.error('Failed to update vector config:', err);
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
                向量模型配置
              </CardTitle>
              <CardDescription className="mt-2">
                配置向量嵌入模型参数与API设置，用于知识库文档向量化和语义搜索
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
            <Label htmlFor="vector-model-name" className="text-slate-700 font-medium">
              模型名称 *
            </Label>
            <Input
              id="vector-model-name"
              value={formData.model_name}
              onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
              placeholder="例如: text-embedding-ada-002"
              disabled={!isEditing || submitting}
              className={!isEditing ? 'bg-slate-50' : ''}
            />
            <p className="text-xs text-slate-500">
              常用模型: text-embedding-ada-002, text-embedding-3-small, text-embedding-3-large
            </p>
          </div>

          <Separator />

          <div className="space-y-2">
            <Label htmlFor="vector-api-endpoint" className="text-slate-700 font-medium">
              API 端点 *
            </Label>
            <Input
              id="vector-api-endpoint"
              value={formData.api_endpoint}
              onChange={(e) => setFormData({ ...formData, api_endpoint: e.target.value })}
              placeholder="https://api.openai.com/v1/embeddings"
              disabled={!isEditing || submitting}
              className={!isEditing ? 'bg-slate-50' : ''}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="vector-api-key" className="text-slate-700 font-medium">
              API 密钥 *
            </Label>
            <div className="relative">
              <Input
                id="vector-api-key"
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
            <Label htmlFor="vector-dimension" className="text-slate-700 font-medium">
              向量维度 *
            </Label>
            <Input
              id="vector-dimension"
              type="number"
              min="1"
              value={formData.embedding_dimension}
              onChange={(e) => setFormData({ ...formData, embedding_dimension: Number(e.target.value) })}
              placeholder="1536"
              disabled={!isEditing || submitting}
              className={!isEditing ? 'bg-slate-50' : ''}
            />
            <p className="text-xs text-slate-500">
              text-embedding-ada-002: 1536维 | text-embedding-3-small: 1536维 | text-embedding-3-large: 3072维
            </p>
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

      <Card className="bg-blue-50 border-blue-200">
        <CardHeader>
          <CardTitle className="text-sm text-blue-900">使用说明</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-blue-800 space-y-2">
          <p>• 向量模型用于将文本转换为向量表示，支持知识库文档的语义搜索</p>
          <p>• 系统会在文档上传时自动调用向量模型生成嵌入向量</p>
          <p>• 用户提问时也会使用向量模型生成问题的嵌入向量，用于检索相关文档</p>
          <p>• 修改配置后，新上传的文档将使用新的向量模型，已有文档不受影响</p>
        </CardContent>
      </Card>
    </div>
  );
};

export default VectorConfiguration;
