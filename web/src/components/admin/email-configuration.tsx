import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/hooks/use-toast';
import {
  Mail,
  Edit,
  Save,
  X,
  Loader2,
  Eye,
  EyeOff,
  Send
} from 'lucide-react';
import AdminService, { type EmailConfig, type EmailConfigUpdate } from '@/services/admin.service';
import { formatErrorMessage } from '@/lib/error-handler';

const EmailConfiguration: React.FC = () => {
  const { toast } = useToast();
  const [config, setConfig] = useState<EmailConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [testing, setTesting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  
  const [formData, setFormData] = useState<EmailConfigUpdate>({
    smtp_host: '',
    smtp_port: 587,
    smtp_user: '',
    smtp_password: '',
    from_email: '',
    auto_send_enabled: false
  });

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const data = await AdminService.getEmailConfig();
      setConfig(data);
      setFormData({
        smtp_host: data.smtp_host,
        smtp_port: data.smtp_port,
        smtp_user: data.smtp_user,
        smtp_password: data.smtp_password,
        from_email: data.from_email,
        auto_send_enabled: data.auto_send_enabled
      });
    } catch (err: any) {
      console.error('Failed to load email config:', err);
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
        smtp_host: config.smtp_host,
        smtp_port: config.smtp_port,
        smtp_user: config.smtp_user,
        smtp_password: config.smtp_password,
        from_email: config.from_email,
        auto_send_enabled: config.auto_send_enabled
      });
    }
    setIsEditing(false);
  };

  const handleSave = async () => {
    if (!formData.smtp_host || !formData.smtp_port || !formData.smtp_user || !formData.smtp_password) {
      toast({
        variant: 'destructive',
        title: '验证失败',
        description: '请填写所有必填字段',
      });
      return;
    }

    try {
      setSubmitting(true);
      const updatedConfig = await AdminService.updateEmailConfig(formData);
      setConfig(updatedConfig);
      setIsEditing(false);
      toast({
        variant: 'success',
        title: '更新成功',
        description: '邮件配置已更新',
      });
    } catch (err: any) {
      console.error('Failed to update email config:', err);
      toast({
        variant: 'destructive',
        title: '更新失败',
        description: formatErrorMessage(err),
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleTestConnection = async () => {
    try {
      setTesting(true);
      await AdminService.testEmailConnection();
      toast({
        variant: 'success',
        title: '连接成功',
        description: '邮件服务器连接测试成功',
      });
    } catch (err: any) {
      console.error('Test connection failed:', err);
      toast({
        variant: 'destructive',
        title: '连接失败',
        description: formatErrorMessage(err),
      });
    } finally {
      setTesting(false);
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
                <Mail className="w-5 h-5 text-blue-600" />
                邮件服务配置
              </CardTitle>
              <CardDescription className="mt-2">
                配置系统邮件发送服务（SMTP）
              </CardDescription>
            </div>
            <div className="flex gap-2">
              {!isEditing && (
                <>
                  <Button onClick={handleTestConnection} variant="outline" disabled={testing}>
                    {testing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Send className="w-4 h-4 mr-2" />}
                    测试连接
                  </Button>
                  <Button onClick={handleEdit} variant="outline">
                    <Edit className="w-4 h-4 mr-2" />
                    编辑配置
                  </Button>
                </>
              )}
            </div>
          </div>
        </CardHeader>
        
        <CardContent className="space-y-6">
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label htmlFor="smtp-host">SMTP 服务器 *</Label>
              <Input
                id="smtp-host"
                value={formData.smtp_host}
                onChange={(e) => setFormData({ ...formData, smtp_host: e.target.value })}
                placeholder="smtp.gmail.com"
                disabled={!isEditing || submitting}
                className={!isEditing ? 'bg-slate-50' : ''}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="smtp-port">端口 *</Label>
              <Input
                id="smtp-port"
                type="number"
                value={formData.smtp_port}
                onChange={(e) => setFormData({ ...formData, smtp_port: parseInt(e.target.value) })}
                placeholder="587"
                disabled={!isEditing || submitting}
                className={!isEditing ? 'bg-slate-50' : ''}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="smtp-user">用户名 (邮箱) *</Label>
            <Input
              id="smtp-user"
              value={formData.smtp_user}
              onChange={(e) => setFormData({ ...formData, smtp_user: e.target.value })}
              placeholder="user@example.com"
              disabled={!isEditing || submitting}
              className={!isEditing ? 'bg-slate-50' : ''}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="smtp-password">密码 (授权码) *</Label>
            <div className="relative">
              <Input
                id="smtp-password"
                type={showPassword ? 'text' : 'password'}
                value={formData.smtp_password}
                onChange={(e) => setFormData({ ...formData, smtp_password: e.target.value })}
                placeholder="••••••••"
                disabled={!isEditing || submitting}
                className={!isEditing ? 'bg-slate-50 pr-10' : 'pr-10'}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="from-email">发件人邮箱 (可选)</Label>
            <Input
              id="from-email"
              value={formData.from_email}
              onChange={(e) => setFormData({ ...formData, from_email: e.target.value })}
              placeholder="noreply@example.com"
              disabled={!isEditing || submitting}
              className={!isEditing ? 'bg-slate-50' : ''}
            />
            <p className="text-xs text-slate-500">如果不填，默认使用SMTP用户名</p>
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-base">自动发送报告</Label>
              <p className="text-sm text-slate-500">
                辩论结束后自动将报告发送给参与学生
              </p>
            </div>
            <Switch
              checked={formData.auto_send_enabled}
              onCheckedChange={(checked) => setFormData({ ...formData, auto_send_enabled: checked })}
              disabled={!isEditing || submitting}
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

export default EmailConfiguration;
