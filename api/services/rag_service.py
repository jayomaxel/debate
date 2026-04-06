"""
RAG服务
负责检索增强生成（Retrieval Augmented Generation）功能。
包括向量相似度搜索、答案生成、来源引用等。
"""
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, text, func, distinct
import json
import asyncio
import logging
from openai import OpenAI

from models.kb_document import KBDocument, KBDocumentChunk
from models.kb_conversation import KBConversation
from services.config_service import ConfigService

logger = logging.getLogger(__name__)


class RAGService:
    """
    RAG服务类。
    提供基于知识库的问答功能，包括向量搜索、答案生成和对话历史管理。
    """
    
    def __init__(self, db: Session):
        """
        初始化RAG服务。
        
        Args:
            db: 数据库会话。
        """
        self.db = db
        self.top_k = int(os.getenv("KB_TOP_K", "5"))  # 默认检索5个最相关的块
        self.similarity_threshold = float(os.getenv("KB_SIMILARITY_THRESHOLD", "0.7"))  # 默认相似度阈值0.7
        
        # OpenAI客户端将在需要时初始化（使用向量配置）
        self.openai_client = None
        self.embedding_model = None
        self._embedding_column_is_vector: Optional[bool] = None

    def _detect_embedding_column_is_vector(self) -> bool:
        try:
            result = self.db.execute(
                text(
                    """
                    SELECT pg_typeof(embedding)::text AS t
                    FROM kb_document_chunks
                    WHERE embedding IS NOT NULL
                    LIMIT 1
                    """
                )
            ).fetchone()

            if not result or not result.t:
                return True

            t = str(result.t)
            return t.startswith("vector")
        except Exception:
            return True
    
    async def _get_openai_client(self) -> OpenAI:
        """
        获取OpenAI客户端（使用向量配置）。
        
        Returns:
            OpenAI: OpenAI客户端实例
            
        Raises:
            RuntimeError: 配置不可用或初始化失败
        """
        if self.openai_client is not None:
            return self.openai_client
        
        try:
            # 从数据库获取向量配置
            config_service = ConfigService(self.db)
            vector_config = await config_service.get_vector_config()
            
            if not vector_config.api_key:
                raise RuntimeError("向量模型API密钥未配置")
            
            # 初始化OpenAI客户端
            # 从api_endpoint提取base_url（去掉/embeddings后缀）
            base_url = vector_config.api_endpoint
            if base_url.endswith('/embeddings'):
                base_url = base_url[:-len('/embeddings')]
            
            self.openai_client = OpenAI(
                api_key=vector_config.api_key,
                base_url=base_url
            )
            self.embedding_model = vector_config.model_name
            
            logger.info(
                f"OpenAI客户端初始化成功: model={self.embedding_model}, "
                f"base_url={base_url}"
            )
            
            return self.openai_client
            
        except Exception as e:
            logger.error(f"初始化OpenAI客户端失败: {e}", exc_info=True)
            raise RuntimeError(f"初始化向量模型客户端失败: {str(e)}")
    
    async def search_similar_chunks(
        self,
        query_embedding: List[float],
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        使用向量相似度搜索最相关的文档块。
        
        使用pgvector的余弦相似度（cosine similarity）进行向量搜索。
        返回与查询向量最相似的top_k个文档块，并过滤掉相似度低于阈值的结果。
        
        Args:
            query_embedding: 查询的嵌入向量（1536维）
            top_k: 返回的最相似块数量（默认使用配置的值，通常为5）
            similarity_threshold: 最小相似度阈值（默认使用配置的值，通常为0.7，范围0到1）
            
        Returns:
            List[Dict[str, Any]]: 相似文档块列表，每个包含：
                - chunk_id: 块ID
                - document_id: 文档ID
                - document_name: 文档名称
                - content: 块内容
                - chunk_index: 块索引
                - token_count: token数量
                - similarity_score: 相似度分数（1 - cosine_distance，范围0到1）
                
        Raises:
            ValueError: 输入验证失败
            RuntimeError: 数据库查询失败
        """
        try:
            # 使用默认值如果未提供
            if top_k is None:
                top_k = self.top_k
            if similarity_threshold is None:
                similarity_threshold = self.similarity_threshold
            
            # 验证输入
            if not query_embedding:
                raise ValueError("查询嵌入向量为空")
            
            # if len(query_embedding) != 1536:
            #     raise ValueError(
            #         f"查询嵌入向量维度错误: 期望1536，实际{len(query_embedding)}"
            #     )
            
            if top_k <= 0:
                raise ValueError(f"top_k必须大于0，实际值: {top_k}")
            
            if not (0 <= similarity_threshold <= 1):
                raise ValueError(
                    f"similarity_threshold必须在0到1之间，实际值: {similarity_threshold}"
                )
            
            # 将Python列表转换为PostgreSQL数组格式
            # pgvector使用 <=> 操作符计算余弦距离（cosine distance）
            # 余弦距离 = 1 - 余弦相似度
            # 因此相似度 = 1 - 距离
            
            # 格式化向量为PostgreSQL数组字符串
            vector_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
            
            if self._embedding_column_is_vector is None:
                self._embedding_column_is_vector = self._detect_embedding_column_is_vector()

            # 使用 <=> 操作符计算余弦距离
            # ORDER BY embedding <=> query_vector 会按距离升序排列（最相似的在前）
            if self._embedding_column_is_vector:
                query = text("""
                    SELECT 
                        c.id as chunk_id,
                        c.document_id,
                        c.content,
                        c.chunk_index,
                        c.token_count,
                        d.filename as document_name,
                        1 - (c.embedding <=> CAST(:query_vector AS vector)) as similarity_score
                    FROM kb_document_chunks c
                    JOIN kb_documents d ON c.document_id = d.id
                    WHERE d.upload_status = 'completed'
                        AND c.embedding IS NOT NULL
                        AND 1 - (c.embedding <=> CAST(:query_vector AS vector)) >= :threshold
                    ORDER BY c.embedding <=> CAST(:query_vector AS vector)
                    LIMIT :limit
                """)
            else:
                query = text("""
                    SELECT 
                        c.id as chunk_id,
                        c.document_id,
                        c.content,
                        c.chunk_index,
                        c.token_count,
                        d.filename as document_name,
                        1 - (CAST(c.embedding AS vector) <=> CAST(:query_vector AS vector)) as similarity_score
                    FROM kb_document_chunks c
                    JOIN kb_documents d ON c.document_id = d.id
                    WHERE d.upload_status = 'completed'
                        AND c.embedding IS NOT NULL
                        AND 1 - (CAST(c.embedding AS vector) <=> CAST(:query_vector AS vector)) >= :threshold
                    ORDER BY CAST(c.embedding AS vector) <=> CAST(:query_vector AS vector)
                    LIMIT :limit
                """)
            
            # 执行查询
            result = self.db.execute(
                query,
                {
                    "query_vector": vector_str,
                    "threshold": similarity_threshold,
                    "limit": top_k
                }
            )
            
            # 处理结果
            similar_chunks = []
            for row in result:
                similar_chunks.append({
                    "chunk_id": str(row.chunk_id),
                    "document_id": str(row.document_id),
                    "document_name": row.document_name,
                    "content": row.content,
                    "chunk_index": row.chunk_index,
                    "token_count": row.token_count,
                    "similarity_score": float(row.similarity_score)
                })
            
            logger.info(
                f"向量相似度搜索完成: 找到 {len(similar_chunks)} 个相似块, "
                f"top_k={top_k}, threshold={similarity_threshold}"
            )
            
            # 如果找到结果，记录最高和最低相似度
            if similar_chunks:
                max_score = similar_chunks[0]["similarity_score"]
                min_score = similar_chunks[-1]["similarity_score"]
                logger.info(
                    f"相似度范围: {min_score:.4f} - {max_score:.4f}"
                )
            else:
                logger.info(
                    f"未找到满足阈值 {similarity_threshold} 的相似块"
                )
            
            return similar_chunks
            
        except ValueError:
            # 重新抛出验证错误
            raise
        except Exception as e:
            logger.error(
                f"向量相似度搜索失败: {e}",
                exc_info=True
            )
            raise RuntimeError(f"向量相似度搜索失败: {str(e)}")
    
    async def generate_answer(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]]
    ) -> str:
        """
        使用LLM生成答案。
        
        根据问题和检索到的上下文块，构建提示词并调用LLM生成答案。
        提示词会指示LLM优先使用知识库信息，并在答案中引用来源。
        
        Args:
            question: 用户的问题
            context_chunks: 检索到的相关文档块列表，每个包含：
                - content: 块内容
                - document_name: 文档名称
                - similarity_score: 相似度分数
                
        Returns:
            str: LLM生成的答案
            
        Raises:
            ValueError: 输入验证失败
            RuntimeError: LLM调用失败
        """
        try:
            # 验证输入
            if not question or not question.strip():
                raise ValueError("问题不能为空")
            
            if not isinstance(context_chunks, list):
                raise ValueError("context_chunks必须是列表")
            
            # 获取LLM配置
            config_service = ConfigService(self.db)
            model_config = await config_service.get_model_config()
            
            # 构建上下文
            context_text = ""
            if context_chunks:
                context_text = "\n\n".join([
                    f"【来源：{chunk['document_name']}】\n{chunk['content']}"
                    for chunk in context_chunks
                ])
            
            # 构建提示词
            if context_chunks:
                # 有知识库上下文时，指示LLM优先使用知识库信息
                system_prompt = """你是一个专业的备战辅助专家，负责帮助学生准备辩论。
你的任务是根据提供的知识库内容回答学生的问题。

重要规则：
1. 优先使用知识库中的信息来回答问题
2. 如果知识库中有相关信息，必须基于这些信息回答
3. 在回答中自然地提及信息来源（例如："根据XXX文档..."）
4. 如果知识库信息不足以完整回答问题，可以补充一般性知识，但要明确区分
5. 保持回答简洁、准确、有条理
6. 使用中文回答"""
                
                user_prompt = f"""知识库内容：
{context_text}

学生问题：{question}

请基于上述知识库内容回答学生的问题。"""
            else:
                # 没有知识库上下文时，使用一般知识回答
                system_prompt = """你是一个专业的辩论助手，负责帮助学生准备辩论。
你的任务是回答学生关于辩论的问题。

重要规则：
1. 提供准确、有用的辩论相关建议
2. 保持回答简洁、有条理
3. 使用中文回答
4. 如果问题超出你的知识范围，诚实地说明"""
                
                user_prompt = f"""学生问题：{question}

请回答学生的问题。注意：当前知识库中没有找到相关内容，请基于你的一般知识回答。"""
            
            # 调用LLM
            logger.info(
                f"调用LLM生成答案: model={model_config.model_name}, "
                f"temperature={model_config.temperature}, "
                f"max_tokens={model_config.max_tokens}, "
                f"has_context={bool(context_chunks)}"
            )
            
            try:
                # 使用OpenAI客户端调用LLM（使用模型配置的客户端，不是向量配置的）
                # 为LLM创建单独的客户端
                llm_base_url = model_config.api_endpoint
                if llm_base_url.endswith('/chat/completions'):
                    llm_base_url = llm_base_url[:-len('/chat/completions')]
                
                llm_client = OpenAI(
                    api_key=model_config.api_key,
                    base_url=llm_base_url
                )
                
                response = llm_client.chat.completions.create(
                    model=model_config.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=model_config.temperature,
                    max_tokens=model_config.max_tokens
                )
                
                # 提取答案
                answer = response.choices[0].message.content.strip()
                
                if not answer:
                    raise RuntimeError("LLM返回了空答案")
                
                logger.info(
                    f"LLM答案生成成功: 长度={len(answer)}字符, "
                    f"使用tokens={response.usage.total_tokens if response.usage else 'unknown'}"
                )
                
                return answer
                
            except Exception as e:
                logger.error(
                    f"LLM API调用失败: {e}",
                    exc_info=True
                )
                raise RuntimeError(f"答案生成失败: {str(e)}")
                
        except ValueError:
            # 重新抛出验证错误
            raise
        except RuntimeError:
            # 重新抛出运行时错误
            raise
        except Exception as e:
            logger.error(
                f"生成答案时发生未预期的错误: {e}",
                exc_info=True
            )
            raise RuntimeError(f"生成答案失败: {str(e)}")
    
    def format_source_citations(
        self,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        格式化来源引用。
        
        将检索到的文档块格式化为结构化的来源引用，包含文档名称、
        相关摘录和相似度分数。这些引用将随答案一起返回给用户。
        
        Args:
            retrieved_chunks: 检索到的文档块列表，每个包含：
                - chunk_id: 块ID
                - document_id: 文档ID
                - document_name: 文档名称
                - content: 块内容
                - chunk_index: 块索引
                - similarity_score: 相似度分数
                
        Returns:
            List[Dict[str, Any]]: 格式化的来源引用列表，每个包含：
                - document_id: 文档ID
                - document_name: 文档名称
                - excerpt: 相关摘录（截取的块内容）
                - similarity_score: 相似度分数
                
        Raises:
            ValueError: 输入验证失败
        """
        try:
            # 验证输入
            if not isinstance(retrieved_chunks, list):
                raise ValueError("retrieved_chunks必须是列表")
            
            # 如果没有检索到块，返回空列表
            if not retrieved_chunks:
                logger.info("没有检索到文档块，返回空的来源引用列表")
                return []
            
            # 格式化每个来源
            sources = []
            max_excerpt_length = 200  # 摘录最大长度（字符数）
            
            for chunk in retrieved_chunks:
                # 验证必需字段
                required_fields = [
                    "document_id", "document_name", "content", "similarity_score"
                ]
                missing_fields = [
                    field for field in required_fields 
                    if field not in chunk
                ]
                if missing_fields:
                    logger.warning(
                        f"文档块缺少必需字段: {missing_fields}，跳过此块"
                    )
                    continue
                
                # 提取内容并截取为摘录
                content = chunk["content"]
                if len(content) > max_excerpt_length:
                    # 截取前max_excerpt_length个字符，并添加省略号
                    excerpt = content[:max_excerpt_length] + "..."
                else:
                    excerpt = content
                
                # 构建来源引用
                source = {
                    "document_id": chunk["document_id"],
                    "document_name": chunk["document_name"],
                    "excerpt": excerpt,
                    "similarity_score": round(chunk["similarity_score"], 4)
                }
                
                sources.append(source)
            
            logger.info(
                f"格式化了 {len(sources)} 个来源引用, "
                f"原始块数: {len(retrieved_chunks)}"
            )
            
            # 如果所有块都因缺少字段而被跳过，记录警告
            if retrieved_chunks and not sources:
                logger.warning(
                    "所有检索到的块都因缺少必需字段而被跳过"
                )
            
            return sources
            
        except ValueError:
            # 重新抛出验证错误
            raise
        except Exception as e:
            logger.error(
                f"格式化来源引用时发生错误: {e}",
                exc_info=True
            )
            # 返回空列表而不是抛出异常，以便答案生成可以继续
            return []
    
    async def ask_question(
        self,
        question: str,
        user_id: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        回答问题（完整的RAG流程）。
        
        执行完整的RAG流程：
        1. 生成问题的嵌入向量
        2. 搜索相似的文档块
        3. 使用LLM生成答案
        4. 格式化来源引用
        5. 保存对话历史
        
        Args:
            question: 用户的问题
            user_id: 用户ID
            session_id: 会话ID
            
        Returns:
            Dict[str, Any]: 包含以下字段：
                - answer: 生成的答案
                - sources: 来源引用列表
                - used_kb: 是否使用了知识库（布尔值）
                - confidence: 置信度指标（"high", "low", "none"）
                    - "high": 找到高相似度的知识库内容（>= 0.75）
                    - "low": 找到知识库内容但相似度较低（< 0.75）
                    - "none": 未找到知识库内容，使用一般知识回答
                
        Raises:
            ValueError: 输入验证失败
            RuntimeError: RAG流程执行失败
        """
        try:
            # 验证输入
            if not question or not question.strip():
                raise ValueError("问题不能为空")
            
            if not user_id:
                raise ValueError("用户ID不能为空")
            
            if not session_id:
                raise ValueError("会话ID不能为空")
            
            logger.info(
                f"开始处理问题: user_id={user_id}, "
                f"session_id={session_id}, "
                f"question_length={len(question)}"
            )
            
            # 步骤1: 生成问题的嵌入向量
            try:
                logger.info("生成问题嵌入向量...")
                # 获取OpenAI客户端（使用向量配置）
                openai_client = await self._get_openai_client()
                
                response = openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=question
                )
                query_embedding = response.data[0].embedding
                logger.info(
                    f"问题嵌入向量生成成功: 维度={len(query_embedding)}"
                )
            except Exception as e:
                logger.error(
                    f"生成问题嵌入向量失败: {e}",
                    exc_info=True
                )
                raise RuntimeError(f"生成问题嵌入向量失败: {str(e)}")
            
            # 步骤2: 搜索相似的文档块
            try:
                logger.info(
                    f"搜索相似文档块: top_k={self.top_k}, "
                    f"threshold={self.similarity_threshold}"
                )
                similar_chunks = await self.search_similar_chunks(
                    query_embedding=query_embedding,
                    top_k=self.top_k,
                    similarity_threshold=self.similarity_threshold
                )
                logger.info(f"找到 {len(similar_chunks)} 个相似文档块")
            except Exception as e:
                logger.error(
                    f"搜索相似文档块失败: {e}",
                    exc_info=True
                )
                # 搜索失败时，继续使用空上下文生成答案
                similar_chunks = []
                logger.warning("搜索失败，将使用一般知识回答")
            
            # 步骤3: 使用LLM生成答案
            try:
                logger.info("生成答案...")
                answer = await self.generate_answer(
                    question=question,
                    context_chunks=similar_chunks
                )
                logger.info(f"答案生成成功: 长度={len(answer)}字符")
            except Exception as e:
                logger.error(
                    f"生成答案失败: {e}",
                    exc_info=True
                )
                raise RuntimeError(f"生成答案失败: {str(e)}")
            
            # 步骤4: 格式化来源引用
            sources = self.format_source_citations(similar_chunks)
            used_kb = len(sources) > 0
            
            # 计算置信度指标
            # 如果有检索到的块，检查最高相似度分数
            confidence = "high"  # 默认高置信度
            max_similarity = 0.0
            
            if similar_chunks:
                max_similarity = max(
                    chunk.get("similarity_score", 0.0) 
                    for chunk in similar_chunks
                )
                
                # 根据最高相似度分数设置置信度
                # 低置信度阈值：0.75（略高于搜索阈值0.7）
                low_confidence_threshold = 0.75
                
                if max_similarity < low_confidence_threshold:
                    confidence = "low"
                    logger.info(
                        f"检测到低置信度结果: max_similarity={max_similarity:.4f} "
                        f"< threshold={low_confidence_threshold}"
                    )
            elif used_kb:
                # 理论上不应该发生（有sources但没有chunks）
                # 但为了安全起见，设置为低置信度
                confidence = "low"
                logger.warning(
                    "异常情况: used_kb=True但similar_chunks为空"
                )
            else:
                # 没有使用知识库，使用一般知识回答
                # 这种情况下置信度取决于是否找到了任何块
                confidence = "none"
                logger.info(
                    "未使用知识库，基于一般知识回答"
                )
            
            logger.info(
                f"来源引用格式化完成: 来源数={len(sources)}, "
                f"used_kb={used_kb}, confidence={confidence}, "
                f"max_similarity={max_similarity:.4f}"
            )
            
            # 步骤5: 保存对话历史
            try:
                conversation = KBConversation(
                    id=uuid.uuid4(),
                    user_id=uuid.UUID(user_id),
                    session_id=session_id,
                    question=question,
                    answer=answer,
                    sources=sources,  # JSONB字段
                    created_at=datetime.utcnow()
                )
                self.db.add(conversation)
                self.db.commit()
                logger.info(
                    f"对话历史已保存: conversation_id={conversation.id}"
                )
            except Exception as e:
                logger.error(
                    f"保存对话历史失败: {e}",
                    exc_info=True
                )
                # 保存失败不影响返回结果
                self.db.rollback()
            
            # 返回结果
            result = {
                "answer": answer,
                "sources": sources,
                "used_kb": used_kb,
                "confidence": confidence
            }
            
            logger.info(
                f"问题处理完成: used_kb={used_kb}, "
                f"sources_count={len(sources)}, confidence={confidence}"
            )
            
            return result
            
        except ValueError:
            # 重新抛出验证错误
            raise
        except RuntimeError:
            # 重新抛出运行时错误
            raise
        except Exception as e:
            logger.error(
                f"处理问题时发生未预期的错误: {e}",
                exc_info=True
            )
            raise RuntimeError(f"处理问题失败: {str(e)}")
    
    def get_conversation_history(
        self,
        user_id: str,
        session_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取对话历史。
        
        检索指定用户和会话的对话历史，按时间倒序排列。
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            limit: 返回的最大对话数量（默认20）
            
        Returns:
            List[Dict[str, Any]]: 对话历史列表，每个包含：
                - id: 对话ID
                - question: 问题
                - answer: 答案
                - sources: 来源引用列表
                - created_at: 创建时间
                
        Raises:
            ValueError: 输入验证失败
            RuntimeError: 数据库查询失败
        """
        try:
            # 验证输入
            if not user_id:
                raise ValueError("用户ID不能为空")
            
            if not session_id:
                raise ValueError("会话ID不能为空")
            
            if limit <= 0:
                raise ValueError(f"limit必须大于0，实际值: {limit}")
            
            logger.info(
                f"获取对话历史: user_id={user_id}, "
                f"session_id={session_id}, limit={limit}"
            )
            
            # 查询对话历史
            conversations = (
                self.db.query(KBConversation)
                .filter(
                    KBConversation.user_id == uuid.UUID(user_id),
                    KBConversation.session_id == session_id
                )
                .order_by(KBConversation.created_at.desc())
                .limit(limit)
                .all()
            )
            
            # 格式化结果
            history = []
            for conv in conversations:
                history.append({
                    "id": str(conv.id),
                    "question": conv.question,
                    "answer": conv.answer,
                    "sources": conv.sources or [],  # JSONB字段可能为None
                    "created_at": conv.created_at.isoformat()
                })
            
            logger.info(
                f"对话历史获取成功: 返回 {len(history)} 条对话"
            )
            
            return history
            
        except ValueError:
            # 重新抛出验证错误
            raise
        except Exception as e:
            logger.error(
                f"获取对话历史失败: {e}",
                exc_info=True
            )
            raise RuntimeError(f"获取对话历史失败: {str(e)}")

    def get_user_sessions(
        self,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        获取用户的所有会话列表。
        
        Args:
            user_id: 用户ID
            
        Returns:
            List[Dict[str, Any]]: 会话列表，每个包含：
                - session_id: 会话ID
                - title: 会话标题（第一条问题的预览）
                - updated_at: 最后更新时间
        """
        try:
            # 验证输入
            if not user_id:
                raise ValueError("用户ID不能为空")
            
            # 使用SQL查询获取会话列表
            # 按session_id分组，获取最新的updated_at
            # 对于标题，我们获取该会话的第一条问题（按created_at升序）
            
            # 这里使用一个子查询来找出每个会话的第一条记录作为标题
            # 注意：这可能不是最高效的方法，但对于合理的会话数量是可以的
            
            # 1. 获取所有唯一的session_id和最后更新时间
            subquery = (
                self.db.query(
                    KBConversation.session_id,
                    func.max(KBConversation.created_at).label("last_update")
                )
                .filter(KBConversation.user_id == uuid.UUID(user_id))
                .group_by(KBConversation.session_id)
                .subquery()
            )
            
            # 2. 查询并排序
            results = (
                self.db.query(subquery.c.session_id, subquery.c.last_update)
                .order_by(subquery.c.last_update.desc())
                .all()
            )
            
            sessions = []
            for row in results:
                # 获取该会话的第一条记录作为标题
                first_msg = (
                    self.db.query(KBConversation.question)
                    .filter(
                        KBConversation.session_id == row.session_id,
                        KBConversation.user_id == uuid.UUID(user_id)
                    )
                    .order_by(KBConversation.created_at.asc())
                    .first()
                )
                
                title = first_msg.question if first_msg else "新对话"
                if len(title) > 20:
                    title = title[:20] + "..."
                    
                sessions.append({
                    "session_id": row.session_id,
                    "title": title,
                    "updated_at": row.last_update.isoformat()
                })
                
            return sessions
            
        except Exception as e:
            logger.error(f"获取用户会话列表失败: {e}", exc_info=True)
            raise RuntimeError(f"获取用户会话列表失败: {str(e)}")

    async def ask_question_stream(
        self,
        question: str,
        user_id: str,
        session_id: str
    ):
        """
        流式回答问题。
        
        生成器函数，yield JSON格式的事件数据：
        - {"type": "sources", "data": [...]}
        - {"type": "answer", "content": "..."}
        - {"type": "done", "id": "..."}
        - {"type": "error", "message": "..."}
        
        Args:
            question: 用户的问题
            user_id: 用户ID
            session_id: 会话ID
        """
        try:
            # 验证输入
            if not question or not question.strip():
                yield json.dumps({"type": "error", "message": "问题不能为空"}, ensure_ascii=False)
                return
            
            # 步骤1: 生成问题的嵌入向量
            openai_client = await self._get_openai_client()
            response = openai_client.embeddings.create(
                model=self.embedding_model,
                input=question
            )
            query_embedding = response.data[0].embedding
            
            # 步骤2: 搜索相似的文档块
            similar_chunks = await self.search_similar_chunks(
                query_embedding=query_embedding,
                top_k=self.top_k,
                similarity_threshold=self.similarity_threshold
            )
            
            # 步骤3: 格式化来源引用并发送
            sources = self.format_source_citations(similar_chunks)
            yield json.dumps({"type": "sources", "data": sources}, ensure_ascii=False)
            
            # 步骤4: 准备LLM调用
            config_service = ConfigService(self.db)
            model_config = await config_service.get_model_config()
            
            context_text = ""
            if similar_chunks:
                context_text = "\n\n".join([
                    f"【来源：{chunk['document_name']}】\n{chunk['content']}"
                    for chunk in similar_chunks
                ])
                
                system_prompt = """你是一个专业的辩论助手，负责帮助学生准备辩论。
你的任务是根据提供的知识库内容回答学生的问题。

重要规则：
1. 优先使用知识库中的信息来回答问题
2. 如果知识库中有相关信息，必须基于这些信息回答
3. 在回答中自然地提及信息来源（例如："根据XXX文档..."）
4. 如果知识库信息不足以完整回答问题，可以补充一般性知识，但要明确区分
5. 保持回答简洁、准确、有条理
6. 使用中文回答"""
                
                user_prompt = f"""知识库内容：
{context_text}

学生问题：{question}

请基于上述知识库内容回答学生的问题。"""
            else:
                system_prompt = """你是一个专业的辩论助手，负责帮助学生准备辩论。
你的任务是回答学生关于辩论的问题。

重要规则：
1. 提供准确、有用的辩论相关建议
2. 保持回答简洁、有条理
3. 使用中文回答
4. 如果问题超出你的知识范围，诚实地说明"""
                
                user_prompt = f"""学生问题：{question}

请回答学生的问题。注意：当前知识库中没有找到相关内容，请基于你的一般知识回答。"""

            # 步骤5: 流式调用LLM
            llm_base_url = model_config.api_endpoint
            if llm_base_url.endswith('/chat/completions'):
                llm_base_url = llm_base_url[:-len('/chat/completions')]
            
            llm_client = OpenAI(
                api_key=model_config.api_key,
                base_url=llm_base_url
            )
            
            stream = llm_client.chat.completions.create(
                model=model_config.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=model_config.temperature,
                max_tokens=model_config.max_tokens,
                stream=True
            )
            
            full_answer = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_answer += content
                    yield json.dumps({"type": "answer", "content": content}, ensure_ascii=False)
            
            # 步骤6: 保存对话历史
            if full_answer:
                try:
                    conversation = KBConversation(
                        id=uuid.uuid4(),
                        user_id=uuid.UUID(user_id),
                        session_id=session_id,
                        question=question,
                        answer=full_answer,
                        sources=sources,
                        created_at=datetime.utcnow()
                    )
                    self.db.add(conversation)
                    self.db.commit()
                    yield json.dumps({"type": "done", "id": str(conversation.id)}, ensure_ascii=False)
                except Exception as e:
                    logger.error(f"保存对话历史失败: {e}")
                    self.db.rollback()
            
        except Exception as e:
            logger.error(f"流式回答失败: {e}", exc_info=True)
            yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
