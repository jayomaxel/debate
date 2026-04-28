"""
学生知识库API路由
提供学生访问知识库的功能，包括提问和查看对话历史
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Dict, Any, List
import logging
import json
import os
import uuid

from database import get_db
from models.kb_document import KBDocument
from models.user import User
from services.rag_service import RAGService
from services.document_service import DocumentService
from middleware.auth_middleware import require_role
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/student/kb", tags=["学生-知识库"])


# Pydantic模型
class AskQuestionRequest(BaseModel):
    """提问请求模型"""
    question: str = Field(..., min_length=1, description="学生的问题")
    session_id: str = Field(..., min_length=1, description="会话ID")


class SourceCitation(BaseModel):
    """来源引用模型"""
    document_id: str
    document_name: str
    excerpt: str
    similarity_score: float


class AskQuestionResponse(BaseModel):
    """提问响应模型"""
    answer: str
    sources: List[SourceCitation]
    used_kb: bool
    confidence: str


@router.get(
    "/sessions",
    summary="获取会话列表",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["student"]))]
)
async def get_sessions(
    current_user: User = Depends(require_role(["student"])),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    获取学生的所有会话列表。
    """
    try:
        rag_service = RAGService(db)
        sessions = rag_service.get_user_sessions(str(current_user.id))
        
        return {
            "code": 200,
            "message": "获取会话列表成功",
            "data": sessions
        }
    except Exception as e:
        logger.error(f"获取会话列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取会话列表失败: {str(e)}"
        )


@router.post(
    "/ask/stream",
    summary="流式向知识库提问",
    dependencies=[Depends(require_role(["student"]))]
)
async def ask_question_stream(
    request: AskQuestionRequest,
    current_user: User = Depends(require_role(["student"])),
    db: Session = Depends(get_db)
):
    """
    流式向知识库提问（学生专用）。
    返回Server-Sent Events (SSE)流。
    """
    try:
        if not request.question.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="问题不能为空"
            )
            
        rag_service = RAGService(db)
        
        async def event_generator():
            async for chunk in rag_service.ask_question_stream(
                question=request.question,
                user_id=str(current_user.id),
                session_id=request.session_id
            ):
                # 格式化为SSE数据格式
                yield f"data: {chunk}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream"
        )
        
    except Exception as e:
        logger.error(f"流式提问失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"流式提问失败: {str(e)}"
        )


@router.post(
    "/ask",
    summary="向知识库提问",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["student"]))]
)
async def ask_question(
    request: AskQuestionRequest,
    current_user: User = Depends(require_role(["student"])),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    向知识库提问（学生专用）
    
    使用RAG（检索增强生成）技术回答学生的问题：
    1. 在知识库中搜索相关文档
    2. 使用LLM生成答案
    3. 提供来源引用
    4. 保存对话历史
    
    参数:
    - question: 学生的问题（必填，不能为空）
    - session_id: 会话ID（必填，用于关联对话历史）
    
    返回:
    - answer: 生成的答案
    - sources: 来源引用列表（包含文档名称、摘录、相似度分数）
    - used_kb: 是否使用了知识库（true表示答案基于知识库，false表示基于一般知识）
    - confidence: 置信度指标
        - "high": 找到高相似度的知识库内容
        - "low": 找到知识库内容但相似度较低
        - "none": 未找到知识库内容，使用一般知识回答
    """
    try:
        # 验证问题不为空（Pydantic已经验证了min_length，但再次确认）
        if not request.question.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="问题不能为空"
            )
        
        # 创建RAG服务
        rag_service = RAGService(db)
        
        # 调用RAG服务回答问题
        result = await rag_service.ask_question(
            question=request.question,
            user_id=str(current_user.id),
            session_id=request.session_id
        )
        
        logger.info(
            f"问题回答成功: user={current_user.account}, "
            f"session={request.session_id}, "
            f"used_kb={result['used_kb']}, "
            f"confidence={result['confidence']}, "
            f"sources_count={len(result['sources'])}"
        )
        
        # 返回结果
        return {
            "code": 200,
            "message": "回答生成成功",
            "data": {
                "answer": result["answer"],
                "sources": result["sources"],
                "used_kb": result["used_kb"],
                "confidence": result["confidence"]
            }
        }
        
    except ValueError as e:
        # 验证错误（空问题等）
        logger.warning(f"问题验证失败: {e}, user={current_user.account}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    except RuntimeError as e:
        # RAG服务运行时错误（LLM调用失败、向量搜索失败等）
        logger.error(
            f"回答生成失败: {e}, user={current_user.account}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"回答生成失败，请稍后重试: {str(e)}"
        )
    
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    
    except Exception as e:
        # 其他未预期的错误
        logger.error(
            f"处理问题时发生未预期的错误: {e}, user={current_user.account}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理问题失败: {str(e)}"
        )


@router.get(
    "/conversations/{session_id}",
    summary="获取对话历史",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["student"]))]
)
async def get_conversation_history(
    session_id: str,
    limit: int = 20,
    current_user: User = Depends(require_role(["student"])),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    获取对话历史（学生专用）
    
    检索指定会话的对话历史，用于在前端显示历史问答记录。
    
    参数:
    - session_id: 会话ID（路径参数，必填）
    - limit: 返回的最大对话数量（查询参数，默认20）
    
    返回:
    - conversations: 对话历史列表，按时间倒序排列
        - id: 对话ID
        - question: 问题
        - answer: 答案
        - sources: 来源引用列表
        - created_at: 创建时间（ISO格式）
    """
    try:
        # 验证limit参数
        if limit <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="limit参数必须大于0"
            )
        
        # 创建RAG服务
        rag_service = RAGService(db)
        
        # 调用RAG服务获取对话历史
        conversations = rag_service.get_conversation_history(
            user_id=str(current_user.id),
            session_id=session_id,
            limit=limit
        )
        
        logger.info(
            f"对话历史获取成功: user={current_user.account}, "
            f"session={session_id}, "
            f"count={len(conversations)}"
        )
        
        # 返回结果
        return {
            "code": 200,
            "message": "对话历史获取成功",
            "data": {
                "conversations": conversations,
                "count": len(conversations)
            }
        }
        
    except ValueError as e:
        # 验证错误
        logger.warning(f"参数验证失败: {e}, user={current_user.account}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    except RuntimeError as e:
        # RAG服务运行时错误（数据库查询失败等）
        logger.error(
            f"获取对话历史失败: {e}, user={current_user.account}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取对话历史失败，请稍后重试: {str(e)}"
        )
    
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    
    except Exception as e:
        # 其他未预期的错误
        logger.error(
            f"获取对话历史时发生未预期的错误: {e}, user={current_user.account}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取对话历史失败: {str(e)}"
        )

@router.get(
    "/documents",
    summary="获取知识库文档列表",
    dependencies=[Depends(require_role(["student"]))]
)
async def list_documents(
    response: Response,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_role(["student"])),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    获取知识库文档列表（学生端）
    
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
                "processed_at": doc.processed_at.isoformat() if doc.processed_at else None
            })
        
        logger.info(
            f"学生获取文档列表成功: page={page}, page_size={page_size}, "
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


@router.get(
    "/documents/{document_id}/download",
    summary="下载知识库文档",
    dependencies=[Depends(require_role(["student"]))],
)
async def download_document(
    document_id: str,
    current_user: User = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    """下载学生可见的全局知识库文档。"""
    try:
        try:
            document_uuid = uuid.UUID(str(document_id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文档ID格式错误",
            )

        document = db.query(KBDocument).filter(KBDocument.id == document_uuid).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在",
            )

        if not document.file_path or not os.path.exists(document.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档文件不存在",
            )

        logger.info(
            "学生下载知识库文档: document=%s, user=%s",
            document_id,
            current_user.account,
        )
        return FileResponse(
            path=document.file_path,
            media_type=document.file_type or "application/octet-stream",
            filename=document.filename,
            headers={"Cache-Control": "no-store"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载知识库文档失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="下载知识库文档失败",
        )
