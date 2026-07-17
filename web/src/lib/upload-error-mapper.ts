import type { UploadGuardErrorContract } from './frontend-contracts';

const messages: Record<string, string> = {
  file_too_large: '文件超过大小限制，请压缩后重试。',
  unsupported_file_type: '文件格式不支持，请上传 PDF 或 DOCX。',
  unsafe_filename: '文件名不符合安全要求，请重命名后重试。',
  malware_detected: '文件未通过安全检查，无法上传。',
};

export const mapUploadError = (error: unknown): string => {
  const response = (error as { response?: { data?: UploadGuardErrorContract } })?.response?.data;
  const detail = response?.detail;
  const code = typeof detail === 'object' ? detail?.code : response?.code;
  const message = typeof detail === 'object' ? detail?.message : detail || response?.message;
  return (code && messages[code]) || message || '上传失败，请检查文件后重试。';
};
