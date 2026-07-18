"""
管理员知识库API路由
提供知识库文档管理功能，包括文档上传、列表、删除等
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from database import get_db
from models.user import User
from models.kb_document import KBDocument
from services.document_service import DocumentService
from services.audit_service import AuditService
from services.background_job_service import BackgroundJobService
from services.config_service import ConfigService
from services.kb_vector_rebuild_service import KBVectorRebuildService
from services.kb_vector_schema_service import (
    KBVectorSchemaService,
    VectorAlignmentUnavailable,
)
from services.file_access_service import FileAccessService, PrivateFileNotFound
from schemas.operations import OperationalErrorCode
from utils.operational_response import operational_error_response
from middleware.auth_middleware import require_role
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin/kb", tags=["管理员-知识库"])


class PublicationRequest(BaseModel):
    published: bool


@router.post(
    "/documents",
    summary="上传知识库文档",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def upload_document(
    background_tasks: BackgroundTasks,
    request: Request,
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
        KBVectorSchemaService.require_rag_available(db)
    except VectorAlignmentUnavailable:
        return operational_error_response(
            request,
            code=OperationalErrorCode.VECTOR_DIMENSION_MISMATCH,
            message="知识库向量正在校验或重建，暂时不能上传文档",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            retryable=True,
            details=KBVectorSchemaService.runtime_snapshot(),
        )
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
                "is_published": bool(document.is_published),
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
    "/vector/alignment",
    summary="检查知识库向量对齐状态",
    dependencies=[Depends(require_role(["administrator"]))],
)
async def inspect_vector_alignment(
    probe_model: bool = False,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    snapshot = await KBVectorSchemaService.inspect_alignment_with_probe(
        db,
        probe_model=probe_model,
    )
    return {"code": 200, "message": "检查完成", "data": snapshot}


@router.post(
    "/vector/rebuild",
    summary="创建知识库向量重建任务",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_role(["administrator"]))],
)
async def rebuild_vectors(
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    vector_config = await ConfigService(db).get_vector_config()
    try:
        job, created = KBVectorRebuildService.enqueue(
            db,
            target_model=str(vector_config.model_name),
            target_dimension=int(vector_config.embedding_dimension or 0),
            requested_by=str(current_user.id),
            reason="administrator_request",
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    AuditService.record_event(
        event_type="vector_rebuild",
        actor_id=str(current_user.id),
        actor_role=str(current_user.user_type),
        target_type="background_job",
        target_id=str(job.id),
        result="success",
        metadata={"action": "enqueue", "created": created},
    )
    return {
        "code": 202,
        "message": "向量重建任务已入队" if created else "复用正在执行的向量重建任务",
        "data": KBVectorRebuildService.serialize_job(job),
    }


@router.get(
    "/vector/rebuild/job",
    summary="查询知识库向量重建任务",
    dependencies=[Depends(require_role(["administrator"]))],
)
async def get_vector_rebuild_job(
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    job = KBVectorRebuildService.get_latest_job(db)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="向量重建任务不存在")
    return {"code": 200, "message": "获取成功", "data": KBVectorRebuildService.serialize_job(job)}


@router.post(
    "/vector/rebuild/job/retry",
    summary="重试知识库向量重建任务",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_role(["administrator"]))],
)
async def retry_vector_rebuild_job(
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    job = KBVectorRebuildService.get_latest_job(db)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="向量重建任务不存在")
    previous_status = str(job.status)
    if not BackgroundJobService.retry(
        db,
        job_id=job.id,
        reset_attempts=job.status == "dead_letter",
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前任务状态不可重试")
    db.refresh(job)
    KBVectorSchemaService.set_runtime_snapshot(
        {
            "status": "rebuilding",
            "error_code": None,
            "job_id": str(job.id),
            "phase": (job.result or {}).get("phase") or "queued",
            "configured_dimension": (job.payload or {}).get("target_dimension"),
            "target_model": (job.payload or {}).get("target_model"),
        }
    )
    AuditService.record_event(
        event_type="vector_rebuild",
        actor_id=str(current_user.id),
        actor_role=str(current_user.user_type),
        target_type="background_job",
        target_id=str(job.id),
        result="success",
        metadata={"action": "retry", "previous_status": previous_status},
    )
    return {"code": 202, "message": "向量重建任务已重新入队", "data": KBVectorRebuildService.serialize_job(job)}


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
                "is_published": bool(doc.is_published),
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


@router.get("/documents/{document_id}/download", summary="下载知识库原始文档")
async def download_document(
    document_id: str,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db),
):
    try:
        private_file = FileAccessService(db).knowledge_document(current_user, document_id)
    except PrivateFileNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    return FileResponse(
        path=private_file.path,
        media_type=private_file.media_type,
        filename=private_file.filename,
        headers=FileAccessService.private_headers(),
    )


@router.put("/documents/{document_id}/publication", summary="发布或撤回知识库文档")
async def update_document_publication(
    document_id: str,
    payload: PublicationRequest,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        import uuid

        document_key = uuid.UUID(str(document_id))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    document = db.query(KBDocument).filter(KBDocument.id == document_key).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    if payload.published and document.upload_status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="文档处理完成后才能发布",
        )
    document.is_published = payload.published
    db.commit()
    AuditService.record_event(
        event_type="knowledge_document_publication",
        actor_id=str(current_user.id),
        actor_role=str(current_user.user_type),
        target_type="kb_document",
        target_id=str(document.id),
        result="success",
        metadata={"published": bool(document.is_published)},
    )
    return {
        "code": 200,
        "message": "发布状态已更新",
        "data": {"document_id": str(document.id), "is_published": bool(document.is_published)},
    }


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
