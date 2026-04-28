import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  FileText,
  Loader2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  FileType,
  Calendar,
  HardDrive,
  Upload,
  Trash2,
  Info
} from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import AdminService, { type KBDocument } from '@/services/admin.service';
import { formatErrorMessage } from '@/lib/error-handler';
import { useToast } from '@/hooks/use-toast';

const DocumentManagement: React.FC = () => {
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [documents, setDocuments] = useState<KBDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [isPollingDocuments, setIsPollingDocuments] = useState(false);
  const pollTimerRef = useRef<number | null>(null);
  
  // Upload state
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  
  // Delete state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<KBDocument | null>(null);
  const [deleting, setDeleting] = useState(false);
  
  // Upload Dialog state
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);

  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  // Constants for validation
  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
  const ALLOWED_TYPES = [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ];
  const ALLOWED_EXTENSIONS = ['.pdf', '.docx'];

  useEffect(() => {
    loadDocuments();
  }, [page]);

  useEffect(() => {
    if (pollTimerRef.current) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }

    const hasProcessingDocuments = documents.some((doc) =>
      ['pending', 'processing'].includes(String(doc.upload_status || '').toLowerCase())
    );
    setIsPollingDocuments(hasProcessingDocuments);

    if (!hasProcessingDocuments) {
      return;
    }

    pollTimerRef.current = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        void loadDocuments({ silent: true });
      }
    }, 5000);

    return () => {
      if (pollTimerRef.current) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [documents, page]);

  const loadDocuments = async (options?: { silent?: boolean }) => {
    try {
      if (!options?.silent) setLoading(true);
      setError('');
      
      const response = await AdminService.listKBDocuments(page, pageSize);
      setDocuments(response.documents);
      setTotal(response.total);
      setTotalPages(Math.ceil(response.total / pageSize));
    } catch (err: any) {
      console.error('Failed to load documents:', err);
      setError(formatErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const validateFile = (file: File): string | null => {
    // Check file type
    if (!ALLOWED_TYPES.includes(file.type)) {
      const extension = '.' + file.name.split('.').pop()?.toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(extension)) {
        return '不支持的文件类型，仅支持 PDF 和 DOCX 格式';
      }
    }
    
    // Check file size
    if (file.size > MAX_FILE_SIZE) {
      return `文件大小超过限制（最大 ${(MAX_FILE_SIZE / (1024 * 1024)).toFixed(0)}MB）`;
    }
    
    return null;
  };

  const handleFileUpload = async (file: File) => {
    // Validate file
    const validationError = validateFile(file);
    if (validationError) {
      toast({
        variant: 'destructive',
        title: '上传失败',
        description: validationError,
        duration: 3000
      });
      return;
    }

    try {
      setUploading(true);
      
      // Upload file
      await AdminService.uploadKBDocument(file);
      
      // Show success toast
      toast({
        title: '上传成功',
        description: `文件 "${file.name}" 已成功上传，正在处理中...`,
        duration: 3000
      });
      
      // Refresh document list
      await loadDocuments();
      
      // Close upload dialog
      setUploadDialogOpen(false);
    } catch (err: any) {
      console.error('Failed to upload document:', err);
      toast({
        variant: 'destructive',
        title: '上传失败',
        description: formatErrorMessage(err),
        duration: 3000
      });
    } finally {
      setUploading(false);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileUpload(files[0]);
    }
    // Reset input value to allow uploading the same file again
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleDeleteClick = (doc: KBDocument) => {
    setDocumentToDelete(doc);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!documentToDelete) return;

    try {
      setDeleting(true);
      
      // Call delete API
      await AdminService.deleteKBDocument(documentToDelete.id);
      
      // Show success toast
      toast({
        title: '删除成功',
        description: `文档 "${documentToDelete.filename}" 已成功删除`,
        duration: 3000
      });
      
      // Close dialog
      setDeleteDialogOpen(false);
      setDocumentToDelete(null);
      
      // Refresh document list
      await loadDocuments();
    } catch (err: any) {
      console.error('Failed to delete document:', err);
      toast({
        variant: 'destructive',
        title: '删除失败',
        description: formatErrorMessage(err),
        duration: 3000
      });
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setDocumentToDelete(null);
  };

  const getStatusBadge = (doc: KBDocument) => {
    switch (doc.upload_status) {
      case 'completed':
        return (
          <Badge className="bg-green-100 text-green-700 border-green-200">
            已完成
          </Badge>
        );
      case 'processing':
        return (
          <Badge className="bg-blue-100 text-blue-700 border-blue-200">
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
            处理中
          </Badge>
        );
      case 'pending':
        return (
          <Badge className="bg-yellow-100 text-yellow-700 border-yellow-200">
            等待中
          </Badge>
        );
      case 'failed':
        return (
          <div className="flex items-center gap-2">
            <Badge className="bg-red-100 text-red-700 border-red-200">
              失败
            </Badge>
            {doc.error_message && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="w-4 h-4 text-red-500 cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="max-w-xs break-words">{doc.error_message}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>
        );
      default:
        return <Badge variant="outline">{doc.upload_status}</Badge>;
    }
  };

  const getFileTypeDisplay = (fileType: string) => {
    if (fileType === 'application/pdf') {
      return 'PDF';
    } else if (fileType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
      return 'DOCX';
    }
    return fileType;
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const handlePreviousPage = () => {
    if (page > 1) {
      setPage(page - 1);
    }
  };

  const handleNextPage = () => {
    if (page < totalPages) {
      setPage(page + 1);
    }
  };

  const handlePageClick = (pageNum: number) => {
    setPage(pageNum);
  };

  // Generate page numbers to display
  const getPageNumbers = () => {
    const pages: (number | string)[] = [];
    const maxPagesToShow = 5;
    
    if (totalPages <= maxPagesToShow) {
      // Show all pages if total is small
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // Always show first page
      pages.push(1);
      
      // Calculate range around current page
      let start = Math.max(2, page - 1);
      let end = Math.min(totalPages - 1, page + 1);
      
      // Add ellipsis after first page if needed
      if (start > 2) {
        pages.push('...');
      }
      
      // Add pages around current page
      for (let i = start; i <= end; i++) {
        pages.push(i);
      }
      
      // Add ellipsis before last page if needed
      if (end < totalPages - 1) {
        pages.push('...');
      }
      
      // Always show last page
      if (totalPages > 1) {
        pages.push(totalPages);
      }
    }
    
    return pages;
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
      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">知识库文档</h3>
          <p className="text-sm text-slate-600">共 {total} 个文档</p>
        </div>
        
        <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Upload className="w-4 h-4 mr-2" />
              上传文档
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-xl">
            <DialogHeader>
              <DialogTitle>上传文档</DialogTitle>
            </DialogHeader>
            <div
              className={`
                relative border-2 border-dashed rounded-lg p-8 text-center transition-colors mt-4
                ${dragActive ? 'border-blue-500 bg-blue-50' : 'border-slate-300 hover:border-slate-400'}
                ${uploading ? 'opacity-50 pointer-events-none' : 'cursor-pointer'}
              `}
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onClick={handleUploadClick}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx"
                onChange={handleFileInputChange}
                className="hidden"
                disabled={uploading}
              />
              
              {uploading ? (
                <div className="flex flex-col items-center">
                  <Loader2 className="w-12 h-12 text-blue-600 animate-spin mb-4" />
                  <p className="text-sm font-medium text-slate-700">正在上传...</p>
                  <p className="text-xs text-slate-500 mt-1">请稍候，文件正在处理中</p>
                </div>
              ) : (
                <div className="flex flex-col items-center">
                  <Upload className="w-12 h-12 text-slate-400 mb-4" />
                  <p className="text-sm font-medium text-slate-700 mb-1">
                    点击或拖拽文件到此处上传
                  </p>
                  <p className="text-xs text-slate-500">
                    支持 PDF 和 DOCX 格式，最大 10MB
                  </p>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Document List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>文档列表</span>
            {isPollingDocuments && (
              <Badge className="bg-blue-100 text-blue-700 border-blue-200">
                <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                自动刷新处理中
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {documents.length === 0 ? (
            <div className="py-12 text-center">
              <FileText className="w-16 h-16 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-500">暂无文档数据</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">
                      文件名
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">
                      文件类型
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">
                      文件大小
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">
                      上传状态
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">
                      上传时间
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">
                      操作
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-200">
                  {documents.map((doc) => (
                    <tr key={doc.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4">
                        <div className="flex items-center">
                          <FileText className="w-5 h-5 text-blue-600 mr-3 flex-shrink-0" />
                          <span className="text-sm font-medium text-slate-900 truncate max-w-xs">
                            {doc.filename}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center text-sm text-slate-600">
                          <FileType className="w-4 h-4 mr-2" />
                          {getFileTypeDisplay(doc.file_type)}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center text-sm text-slate-600">
                          <HardDrive className="w-4 h-4 mr-2" />
                          {formatFileSize(doc.file_size)}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {getStatusBadge(doc)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center text-sm text-slate-600">
                          <Calendar className="w-4 h-4 mr-2" />
                          {formatDate(doc.uploaded_at)}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteClick(doc)}
                          className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        >
                          <Trash2 className="w-4 h-4 mr-1" />
                          删除
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-slate-600">
            显示第 {(page - 1) * pageSize + 1} - {Math.min(page * pageSize, total)} 条，共 {total} 条
          </div>
          
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePreviousPage}
              disabled={page === 1}
            >
              <ChevronLeft className="w-4 h-4 mr-1" />
              上一页
            </Button>
            
            <div className="flex gap-1">
              {getPageNumbers().map((pageNum, index) => (
                <React.Fragment key={index}>
                  {pageNum === '...' ? (
                    <span className="px-3 py-1 text-slate-400">...</span>
                  ) : (
                    <Button
                      variant={page === pageNum ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => handlePageClick(pageNum as number)}
                      className={page === pageNum ? 'bg-blue-600 hover:bg-blue-700' : ''}
                    >
                      {pageNum}
                    </Button>
                  )}
                </React.Fragment>
              ))}
            </div>
            
            <Button
              variant="outline"
              size="sm"
              onClick={handleNextPage}
              disabled={page === totalPages}
            >
              下一页
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除文档</AlertDialogTitle>
            <AlertDialogDescription>
              您确定要删除文档 <span className="font-semibold text-slate-900">"{documentToDelete?.filename}"</span> 吗？
              <br />
              <br />
              此操作将永久删除该文档及其所有相关数据，且无法恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={handleDeleteCancel} disabled={deleting}>
              取消
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              disabled={deleting}
              className="bg-red-600 hover:bg-red-700 focus:ring-red-600"
            >
              {deleting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  删除中...
                </>
              ) : (
                '确认删除'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default DocumentManagement;
