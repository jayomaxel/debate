"""
管理员知识库API路由
提供知识库文档管理功能，包括文档上传、列表、删除等
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from database import get_db
from models.user import User
from services.document_service import DocumentService
from middleware.auth_middleware import require_role
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin/kb", tags=["管理员-知识库"])


@router.post(
    "/documents",
    summary="上传知识库文档",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    上传文档到知识库（管理员专用）
    
    支持的文件格式：
    - PDF (.pdf)
    - DOCX (.docx)
    
    文件大小限制：10MB
    
    上传后文档将异步处理：
    1. 解析文档提取文本
    2. 将文本分块
    3. 生成嵌入向量
    4. 存储到向量数据库
    
    参数:
    - file: 要上传的文档文件
    
    返回:
    - 文档信息，包括ID、文件名、上传状态等
    """
    try:
        # 读取文件数据
        file_data = await file.read()
        
        # 获取文件类型
        content_type = file.content_type
        if not content_type:
            # 如果没有content_type，根据文件扩展名推断
            if file.filename.lower().endswith('.pdf'):
                content_type = "application/pdf"
            elif file.filename.lower().endswith('.docx'):
                content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="不支持的文件类型，仅支持 PDF 和 DOCX 格式"
                )
        
        # 创建文档服务
        doc_service = DocumentService(db)
        
        # 上传文档
        document = await doc_service.upload_document(
            file_data=file_data,
            filename=file.filename,
            file_type=content_type,
            user_id=str(current_user.id)
        )
        
        # 触发异步处理
        background_tasks.add_task(
            doc_service.process_document,
            str(document.id)
        )
        
        logger.info(
            f"文档上传成功: {document.filename} (ID: {document.id}), "
            f"上传者: {current_user.account}, 已触发异步处理"
        )
        
        # 返回文档信息
        return {
            "code": 200,
            "message": "文档上传成功，正在后台处理",
            "data": {
                "id": str(document.id),
                "filename": document.filename,
                "file_type": document.file_type,
                "file_size": document.file_size,
                "upload_status": document.upload_status,
                "uploaded_by": str(document.uploaded_by),
                "uploaded_at": document.uploaded_at.isoformat(),
                "processed_at": document.processed_at.isoformat() if document.processed_at else None,
                "error_message": document.error_message
            }
        }
        
    except ValueError as e:
        # 验证错误（文件类型、大小等）
        logger.warning(f"文档上传验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    except IOError as e:
        # 文件保存失败
        logger.error(f"文档保存失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件保存失败，请稍后重试"
        )
    
    except Exception as e:
        # 其他未预期的错误
        logger.error(f"文档上传失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文档上传失败: {str(e)}"
        )


@router.get(
    "/documents",
    summary="获取知识库文档列表",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def list_documents(
    response: Response,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    获取知识库文档列表（管理员专用）
    
    支持分页查询，按上传时间倒序排列。
    
    参数:
    - page: 页码（从1开始，默认1）
    - page_size: 每页数量（默认20）
    
    返回:
    - documents: 文档列表
    - total: 文档总数
    - page: 当前页码
    - page_size: 每页数量
    - total_pages: 总页数
    """
    try:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        # 验证分页参数
        if page < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="页码必须大于0"
            )
        
        if page_size < 1 or page_size > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="每页数量必须在1-100之间"
            )
        
        # 创建文档服务
        doc_service = DocumentService(db)
        
        # 获取文档列表
        result = doc_service.list_documents(page=page, page_size=page_size)
        
        # 序列化文档列表
        documents_data = []
        for doc in result["documents"]:
            documents_data.append({
                "id": str(doc.id),
                "filename": doc.filename,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "upload_status": doc.upload_status,
                "uploaded_by": str(doc.uploaded_by),
                "uploaded_at": doc.uploaded_at.isoformat(),
                "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
                "error_message": doc.error_message
            })
        
        logger.info(
            f"获取文档列表成功: page={page}, page_size={page_size}, "
            f"total={result['total']}, 请求者: {current_user.account}"
        )
        
        return {
            "code": 200,
            "message": "获取文档列表成功",
            "data": {
                "documents": documents_data,
                "total": result["total"],
                "page": result["page"],
                "page_size": result["page_size"],
                "total_pages": result["total_pages"]
            }
        }
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    
    except Exception as e:
        # 其他未预期的错误
        logger.error(f"获取文档列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档列表失败: {str(e)}"
        )


@router.delete(
    "/documents/{document_id}",
    summary="删除知识库文档",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def delete_document(
    document_id: str,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    删除知识库文档（管理员专用）
    
    删除指定的文档，包括：
    1. 从磁盘删除文件
    2. 从数据库删除文档记录
    3. 级联删除所有相关的文档块和嵌入向量
    
    参数:
    - document_id: 要删除的文档ID
    
    返回:
    - 删除成功的消息
    """
    try:
        # 创建文档服务
        doc_service = DocumentService(db)
        
        # 删除文档
        success = await doc_service.delete_document(document_id)
        
        if success:
            logger.info(
                f"文档删除成功: ID={document_id}, "
                f"操作者: {current_user.account}"
            )
            
            return {
                "code": 200,
                "message": "文档删除成功",
                "data": {
                    "document_id": document_id,
                    "deleted": True
                }
            }
        else:
            # 理论上不应该到达这里，因为delete_document会抛出异常
            logger.warning(f"文档删除返回False: {document_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="文档删除失败"
            )
        
    except ValueError as e:
        # 文档不存在
        logger.warning(f"文档删除失败（文档不存在）: {document_id}, 错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    
    except Exception as e:
        # 其他未预期的错误
        logger.error(f"文档删除失败: {document_id}, 错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文档删除失败: {str(e)}"
        )
