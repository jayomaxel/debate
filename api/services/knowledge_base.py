"""
知识库管理服务
处理文档上传、文本提取、向量生成和检索
"""
import os
from logging_config import get_logger
from typing import List, Optional, Dict, Any
from datetime import datetime
import PyPDF2
import docx
from sqlalchemy.orm import Session
from sqlalchemy import text
import httpx

from models.document import Document
from services.config_service import ConfigService

logger = get_logger(__name__)


class KnowledgeBase:
    """知识库管理类"""
    
    def __init__(self, db: Session):
        """
        初始化知识库
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.upload_dir = os.getenv("UPLOAD_DIR", "uploads/documents")
        os.makedirs(self.upload_dir, exist_ok=True)
    
    async def upload_document(
        self,
        file_data: bytes,
        filename: str,
        file_type: str,
        debate_id: str
    ) -> Document:
        """
        上传文档
        
        Args:
            file_data: 文件数据
            filename: 文件名
            file_type: 文件类型（application/pdf 或 application/vnd.openxmlformats-officedocument.wordprocessingml.document）
            debate_id: 辩论ID
            
        Returns:
            Document对象
        """
        try:
            # 验证文件类型
            allowed_types = [
                "application/pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ]
            if file_type not in allowed_types:
                raise ValueError(f"不支持的文件类型: {file_type}")
            
            # 验证文件大小（最大10MB）
            max_size = 10 * 1024 * 1024
            if len(file_data) > max_size:
                raise ValueError(f"文件大小超过限制（最大10MB）")
            
            # 生成文件路径
            timestamp = datetime.utcnow().timestamp()
            safe_filename = f"{debate_id}_{timestamp}_{filename}"
            file_path = os.path.join(self.upload_dir, safe_filename)
            
            # 保存文件
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            logger.info(f"Document saved: {file_path}")
            
            # 提取文本内容
            content = await self.extract_text(file_path, file_type)
            
            # 创建文档记录
            document = Document(
                debate_id=debate_id,
                filename=filename,
                file_path=file_path,
                file_type=file_type,
                content=content,
                embedding_status="pending"
            )
            
            self.db.add(document)
            self.db.commit()
            self.db.refresh(document)
            
            # 异步生成向量（标记为processing）
            document.embedding_status = "processing"
            self.db.commit()
            
            # 生成并存储向量
            try:
                await self.generate_and_store_embeddings(document)
                document.embedding_status = "completed"
            except Exception as e:
                logger.error(f"Failed to generate embeddings: {e}", exc_info=True)
                document.embedding_status = "failed"
            
            self.db.commit()
            
            return document
            
        except Exception as e:
            logger.error(f"Failed to upload document: {e}", exc_info=True)
            raise
    
    async def extract_text(self, file_path: str, file_type: str) -> str:
        """
        从文件中提取文本内容
        
        Args:
            file_path: 文件路径
            file_type: 文件类型
            
        Returns:
            提取的文本内容
        """
        try:
            if file_type == "application/pdf":
                return await self._extract_text_from_pdf(file_path)
            elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                return await self._extract_text_from_docx(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
        except Exception as e:
            logger.error(f"Failed to extract text: {e}", exc_info=True)
            raise
    
    async def _extract_text_from_pdf(self, file_path: str) -> str:
        """从PDF文件提取文本"""
        try:
            text_content = []
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
            
            full_text = "\n\n".join(text_content)
            logger.info(f"Extracted {len(full_text)} characters from PDF")
            
            return full_text
            
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}", exc_info=True)
            raise
    
    async def _extract_text_from_docx(self, file_path: str) -> str:
        """从Word文档提取文本"""
        try:
            doc = docx.Document(file_path)
            
            text_content = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text)
            
            full_text = "\n\n".join(text_content)
            logger.info(f"Extracted {len(full_text)} characters from DOCX")
            
            return full_text
            
        except Exception as e:
            logger.error(f"Failed to extract text from DOCX: {e}", exc_info=True)
            raise
    
    async def generate_embeddings(self, text: str) -> List[float]:
        """
        生成文本的语义向量
        
        Args:
            text: 文本内容
            
        Returns:
            向量列表
        """
        try:
            # 获取OpenAI配置
            config_service = ConfigService(self.db)
            model_config = await config_service.get_model_config()
            
            if not model_config or not model_config.api_key:
                raise ValueError("OpenAI API key not configured")
            
            # 分块处理长文本（OpenAI embeddings API限制8191 tokens）
            chunks = self._split_text_into_chunks(text, max_length=8000)
            
            all_embeddings = []
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                for chunk in chunks:
                    response = await client.post(
                        f"{model_config.api_endpoint.rsplit('/', 1)[0]}/embeddings",
                        headers={
                            "Authorization": f"Bearer {model_config.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "text-embedding-ada-002",
                            "input": chunk
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        embedding = data["data"][0]["embedding"]
                        all_embeddings.append(embedding)
                    else:
                        error_msg = f"Embeddings API error: {response.status_code} - {response.text}"
                        logger.error(error_msg)
                        raise Exception(error_msg)
            
            # 如果有多个chunk，返回第一个（或可以计算平均值）
            return all_embeddings[0] if all_embeddings else []
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}", exc_info=True)
            raise
    
    def _split_text_into_chunks(self, text: str, max_length: int = 8000) -> List[str]:
        """
        将长文本分割成多个块
        
        Args:
            text: 文本内容
            max_length: 每块的最大长度
            
        Returns:
            文本块列表
        """
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        current_chunk = ""
        
        # 按段落分割
        paragraphs = text.split("\n\n")
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) + 2 <= max_length:
                current_chunk += paragraph + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    async def generate_and_store_embeddings(self, document: Document) -> None:
        """
        生成并存储文档的向量到数据库
        
        Args:
            document: 文档对象
        """
        try:
            if not document.content:
                logger.warning(f"Document {document.id} has no content")
                return
            
            # 生成向量
            embeddings = await self.generate_embeddings(document.content)
            
            if not embeddings:
                logger.warning(f"No embeddings generated for document {document.id}")
                return
            
            # 存储到pgvector（需要先创建向量扩展和表）
            # 这里使用简单的方式存储，实际应该使用pgvector扩展
            # 由于当前数据库模型中没有向量字段，这里先记录日志
            logger.info(f"Generated embeddings for document {document.id}, vector length: {len(embeddings)}")
            
            # TODO: 实际存储到pgvector表
            # 需要执行类似以下的SQL：
            # INSERT INTO document_embeddings (document_id, embedding) VALUES (%s, %s)
            
        except Exception as e:
            logger.error(f"Failed to generate and store embeddings: {e}", exc_info=True)
            raise
    
    async def search_relevant_content(
        self,
        query: str,
        debate_id: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        搜索相关内容
        
        Args:
            query: 查询文本
            debate_id: 辩论ID（可选，用于限制搜索范围）
            top_k: 返回结果数量
            
        Returns:
            相关文档列表
        """
        try:
            # 生成查询向量
            query_embedding = await self.generate_embeddings(query)
            
            if not query_embedding:
                logger.warning("Failed to generate query embedding")
                return []
            
            # 使用pgvector进行相似度搜索
            # 这里使用简单的文本匹配作为fallback
            query_filter = self.db.query(Document).filter(
                Document.embedding_status == "completed"
            )
            
            if debate_id:
                query_filter = query_filter.filter(Document.debate_id == debate_id)
            
            documents = query_filter.all()
            
            # 简单的关键词匹配（实际应该使用向量相似度）
            results = []
            for doc in documents:
                if doc.content and query.lower() in doc.content.lower():
                    # 提取相关段落
                    paragraphs = doc.content.split("\n\n")
                    relevant_paragraphs = [
                        p for p in paragraphs 
                        if query.lower() in p.lower()
                    ]
                    
                    if relevant_paragraphs:
                        results.append({
                            "document_id": str(doc.id),
                            "filename": doc.filename,
                            "content": "\n\n".join(relevant_paragraphs[:3]),  # 最多3个段落
                            "relevance_score": 0.8  # 模拟相似度分数
                        })
            
            # 返回top_k结果
            return results[:top_k]
            
        except Exception as e:
            logger.error(f"Failed to search relevant content: {e}", exc_info=True)
            return []
    
    async def delete_document(self, document_id: str) -> bool:
        """
        删除文档
        
        Args:
            document_id: 文档ID
            
        Returns:
            是否删除成功
        """
        try:
            document = self.db.query(Document).filter(Document.id == document_id).first()
            
            if not document:
                logger.warning(f"Document {document_id} not found")
                return False
            
            # 删除文件
            if os.path.exists(document.file_path):
                os.remove(document.file_path)
                logger.info(f"Deleted file: {document.file_path}")
            
            # 删除数据库记录
            self.db.delete(document)
            self.db.commit()
            
            # TODO: 删除向量数据
            
            logger.info(f"Deleted document: {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document: {e}", exc_info=True)
            self.db.rollback()
            return False
    
    def get_documents(self, debate_id: str) -> List[Document]:
        """
        获取辩论的所有文档
        
        Args:
            debate_id: 辩论ID
            
        Returns:
            文档列表
        """
        try:
            documents = self.db.query(Document).filter(
                Document.debate_id == debate_id
            ).order_by(Document.uploaded_at.desc()).all()
            
            return documents
            
        except Exception as e:
            logger.error(f"Failed to get documents: {e}", exc_info=True)
            return []
    
    def get_document_by_id(self, document_id: str) -> Optional[Document]:
        """
        根据ID获取文档
        
        Args:
            document_id: 文档ID
            
        Returns:
            文档对象
        """
        try:
            document = self.db.query(Document).filter(Document.id == document_id).first()
            return document
        except Exception as e:
            logger.error(f"Failed to get document: {e}", exc_info=True)
            return None
