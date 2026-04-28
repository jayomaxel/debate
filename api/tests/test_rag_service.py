"""
RAG服务测试
测试向量相似度搜索、答案生成等功能。

注意：由于SQLite不支持pgvector扩展，向量相似度搜索的测试需要在PostgreSQL环境中运行。
这里主要测试输入验证和错误处理逻辑。
"""
import pytest
import uuid
import json
import asyncio
from datetime import datetime
from typing import List
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

from services.rag_service import RAGService
from models.kb_document import KBDocument, KBDocumentChunk


class TestRAGService:
    """RAG服务测试类"""
    
    @pytest.fixture
    def rag_service(self, db_session: Session):
        """创建RAG服务实例"""
        return RAGService(db_session)
    
    @pytest.mark.asyncio
    async def test_search_similar_chunks_invalid_embedding_dimension(
        self,
        rag_service: RAGService
    ):
        """测试无效的嵌入向量维度"""
        # 使用错误维度的向量
        query_embedding = [0.5] * 100  # 应该是1536维
        
        # 应该抛出ValueError
        with pytest.raises(ValueError, match="查询嵌入向量维度错误"):
            await rag_service.search_similar_chunks(
                query_embedding=query_embedding,
                top_k=5
            )
    
    @pytest.mark.asyncio
    async def test_search_similar_chunks_empty_embedding(
        self,
        rag_service: RAGService
    ):
        """测试空的嵌入向量"""
        query_embedding = []
        
        # 应该抛出ValueError
        with pytest.raises(ValueError, match="查询嵌入向量为空"):
            await rag_service.search_similar_chunks(
                query_embedding=query_embedding,
                top_k=5
            )
    
    @pytest.mark.asyncio
    async def test_search_similar_chunks_invalid_top_k(
        self,
        rag_service: RAGService
    ):
        """测试无效的top_k值"""
        query_embedding = [0.5] * 1536
        
        # top_k为0
        with pytest.raises(ValueError, match="top_k必须大于0"):
            await rag_service.search_similar_chunks(
                query_embedding=query_embedding,
                top_k=0
            )
        
        # top_k为负数
        with pytest.raises(ValueError, match="top_k必须大于0"):
            await rag_service.search_similar_chunks(
                query_embedding=query_embedding,
                top_k=-1
            )
    
    @pytest.mark.asyncio
    async def test_search_similar_chunks_invalid_threshold(
        self,
        rag_service: RAGService
    ):
        """测试无效的相似度阈值"""
        query_embedding = [0.5] * 1536
        
        # 阈值大于1
        with pytest.raises(ValueError, match="similarity_threshold必须在0到1之间"):
            await rag_service.search_similar_chunks(
                query_embedding=query_embedding,
                top_k=5,
                similarity_threshold=1.5
            )
        
        # 阈值小于0
        with pytest.raises(ValueError, match="similarity_threshold必须在0到1之间"):
            await rag_service.search_similar_chunks(
                query_embedding=query_embedding,
                top_k=5,
                similarity_threshold=-0.1
            )
    
    @pytest.mark.asyncio
    async def test_search_similar_chunks_with_mock_database(
        self,
        rag_service: RAGService
    ):
        """测试向量搜索（使用模拟数据库）"""
        query_embedding = [0.9] + [0.0] * 1535
        
        # 模拟数据库查询结果
        mock_row = MagicMock()
        mock_row.chunk_id = uuid.uuid4()
        mock_row.document_id = uuid.uuid4()
        mock_row.document_name = "test_document.pdf"
        mock_row.content = "这是测试内容"
        mock_row.chunk_index = 0
        mock_row.token_count = 10
        mock_row.similarity_score = 0.95
        
        # 模拟数据库执行
        with patch.object(rag_service.db, 'execute') as mock_execute:
            mock_execute.return_value = [mock_row]
            
            results = await rag_service.search_similar_chunks(
                query_embedding=query_embedding,
                top_k=5,
                similarity_threshold=0.7
            )
            
            # 验证结果
            assert len(results) == 1
            assert results[0]["chunk_id"] == str(mock_row.chunk_id)
            assert results[0]["document_id"] == str(mock_row.document_id)
            assert results[0]["document_name"] == mock_row.document_name
            assert results[0]["content"] == mock_row.content
            assert results[0]["similarity_score"] == 0.95
            
            # 验证数据库查询被调用
            mock_execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_similar_chunks_no_results_mock(
        self,
        rag_service: RAGService
    ):
        """测试没有结果的情况（使用模拟数据库）"""
        query_embedding = [0.5] * 1536
        
        # 模拟空结果
        with patch.object(rag_service.db, 'execute') as mock_execute:
            mock_execute.return_value = []
            
            results = await rag_service.search_similar_chunks(
                query_embedding=query_embedding,
                top_k=5,
                similarity_threshold=0.9
            )
            
            # 应该返回空列表
            assert results == []
            assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_search_similar_chunks_multiple_results_mock(
        self,
        rag_service: RAGService
    ):
        """测试多个结果的情况（使用模拟数据库）"""
        query_embedding = [0.5] * 1536
        
        # 模拟多个结果
        mock_rows = []
        for i in range(3):
            mock_row = MagicMock()
            mock_row.chunk_id = uuid.uuid4()
            mock_row.document_id = uuid.uuid4()
            mock_row.document_name = f"document_{i}.pdf"
            mock_row.content = f"内容 {i}"
            mock_row.chunk_index = i
            mock_row.token_count = 10 + i
            mock_row.similarity_score = 0.9 - i * 0.1  # 递减的相似度
            mock_rows.append(mock_row)
        
        with patch.object(rag_service.db, 'execute') as mock_execute:
            mock_execute.return_value = mock_rows
            
            results = await rag_service.search_similar_chunks(
                query_embedding=query_embedding,
                top_k=5,
                similarity_threshold=0.0
            )
            
            # 验证结果数量
            assert len(results) == 3
            
            # 验证结果按相似度降序排列
            assert results[0]["similarity_score"] == 0.9
            assert results[1]["similarity_score"] == 0.8
            assert results[2]["similarity_score"] == 0.7
            
            # 验证所有必需字段都存在
            for result in results:
                assert "chunk_id" in result
                assert "document_id" in result
                assert "document_name" in result
                assert "content" in result
                assert "chunk_index" in result
                assert "token_count" in result
                assert "similarity_score" in result


class TestGenerateAnswer:
    """答案生成测试类"""
    
    @pytest.fixture
    def rag_service_with_openai(self, db_session: Session):
        """创建带有模拟OpenAI客户端的RAG服务实例"""
        service = RAGService(db_session)
        # 创建模拟的OpenAI客户端
        service.openai_client = MagicMock()
        return service
    
    @pytest.mark.asyncio
    async def test_generate_answer_empty_question(
        self,
        rag_service_with_openai: RAGService
    ):
        """测试空问题"""
        # 空字符串
        with pytest.raises(ValueError, match="问题不能为空"):
            await rag_service_with_openai.generate_answer(
                question="",
                context_chunks=[]
            )
        
        # 只有空格
        with pytest.raises(ValueError, match="问题不能为空"):
            await rag_service_with_openai.generate_answer(
                question="   ",
                context_chunks=[]
            )
    
    @pytest.mark.asyncio
    async def test_generate_answer_invalid_context_chunks(
        self,
        rag_service_with_openai: RAGService
    ):
        """测试无效的context_chunks参数"""
        # 不是列表
        with pytest.raises(ValueError, match="context_chunks必须是列表"):
            await rag_service_with_openai.generate_answer(
                question="什么是辩论？",
                context_chunks="not a list"  # type: ignore
            )
    
    @pytest.mark.asyncio
    async def test_generate_answer_no_openai_client(
        self,
        db_session: Session
    ):
        """测试OpenAI客户端未初始化的情况"""
        # 创建没有OpenAI客户端的服务
        service = RAGService(db_session)
        service.openai_client = None
        
        with pytest.raises(RuntimeError, match="OpenAI客户端未初始化"):
            await service.generate_answer(
                question="什么是辩论？",
                context_chunks=[]
            )
    
    @pytest.mark.asyncio
    async def test_generate_answer_with_context(
        self,
        rag_service_with_openai: RAGService
    ):
        """测试有上下文的答案生成"""
        question = "什么是辩论的三要素？"
        context_chunks = [
            {
                "content": "辩论的三要素包括：论点、论据和论证。论点是辩论者的主张，论据是支持论点的证据，论证是连接论点和论据的逻辑推理。",
                "document_name": "辩论基础知识.pdf",
                "similarity_score": 0.95
            },
            {
                "content": "在辩论中，清晰的论点、充分的论据和严密的论证缺一不可。",
                "document_name": "辩论技巧.pdf",
                "similarity_score": 0.85
            }
        ]
        
        # 模拟ConfigService
        mock_config = MagicMock()
        mock_config.model_name = "gpt-3.5-turbo"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000
        
        # 模拟OpenAI响应
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "根据辩论基础知识文档，辩论的三要素包括：论点、论据和论证。论点是辩论者的主张，论据是支持论点的证据，论证是连接论点和论据的逻辑推理。"
        mock_response.usage.total_tokens = 150
        
        with patch('services.rag_service.ConfigService') as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(return_value=mock_config)
            
            rag_service_with_openai.openai_client.chat.completions.create.return_value = mock_response
            
            answer = await rag_service_with_openai.generate_answer(
                question=question,
                context_chunks=context_chunks
            )
            
            # 验证答案不为空
            assert answer
            assert isinstance(answer, str)
            assert len(answer) > 0
            
            # 验证OpenAI API被调用
            rag_service_with_openai.openai_client.chat.completions.create.assert_called_once()
            call_args = rag_service_with_openai.openai_client.chat.completions.create.call_args
            
            # 验证调用参数
            assert call_args.kwargs['model'] == "gpt-3.5-turbo"
            assert call_args.kwargs['temperature'] == 0.7
            assert call_args.kwargs['max_tokens'] == 2000
            
            # 验证消息格式
            messages = call_args.kwargs['messages']
            assert len(messages) == 2
            assert messages[0]['role'] == 'system'
            assert messages[1]['role'] == 'user'
            
            # 验证上下文被包含在提示词中
            user_content = messages[1]['content']
            assert "辩论基础知识.pdf" in user_content
            assert "辩论技巧.pdf" in user_content
            assert "论点、论据和论证" in user_content
    
    @pytest.mark.asyncio
    async def test_generate_answer_without_context(
        self,
        rag_service_with_openai: RAGService
    ):
        """测试没有上下文的答案生成"""
        question = "什么是辩论？"
        context_chunks = []
        
        # 模拟ConfigService
        mock_config = MagicMock()
        mock_config.model_name = "gpt-3.5-turbo"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000
        
        # 模拟OpenAI响应
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "辩论是一种通过逻辑推理和证据支持来论证观点的交流方式。"
        mock_response.usage.total_tokens = 100
        
        with patch('services.rag_service.ConfigService') as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(return_value=mock_config)
            
            rag_service_with_openai.openai_client.chat.completions.create.return_value = mock_response
            
            answer = await rag_service_with_openai.generate_answer(
                question=question,
                context_chunks=context_chunks
            )
            
            # 验证答案不为空
            assert answer
            assert isinstance(answer, str)
            
            # 验证OpenAI API被调用
            rag_service_with_openai.openai_client.chat.completions.create.assert_called_once()
            call_args = rag_service_with_openai.openai_client.chat.completions.create.call_args
            
            # 验证消息格式
            messages = call_args.kwargs['messages']
            assert len(messages) == 2
            
            # 验证提示词中提到了没有知识库内容
            user_content = messages[1]['content']
            assert "知识库中没有找到相关内容" in user_content or "一般知识" in user_content
    
    @pytest.mark.asyncio
    async def test_generate_answer_llm_api_failure(
        self,
        rag_service_with_openai: RAGService
    ):
        """测试LLM API调用失败"""
        question = "什么是辩论？"
        context_chunks = []
        
        # 模拟ConfigService
        mock_config = MagicMock()
        mock_config.model_name = "gpt-3.5-turbo"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000
        
        with patch('services.rag_service.ConfigService') as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(return_value=mock_config)
            
            # 模拟API调用失败
            rag_service_with_openai.openai_client.chat.completions.create.side_effect = Exception("API rate limit exceeded")
            
            with pytest.raises(RuntimeError, match="答案生成失败"):
                await rag_service_with_openai.generate_answer(
                    question=question,
                    context_chunks=context_chunks
                )
    
    @pytest.mark.asyncio
    async def test_generate_answer_empty_response(
        self,
        rag_service_with_openai: RAGService
    ):
        """测试LLM返回空答案"""
        question = "什么是辩论？"
        context_chunks = []
        
        # 模拟ConfigService
        mock_config = MagicMock()
        mock_config.model_name = "gpt-3.5-turbo"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000
        
        # 模拟OpenAI返回空答案
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "   "  # 只有空格
        mock_response.usage = None
        
        with patch('services.rag_service.ConfigService') as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(return_value=mock_config)
            
            rag_service_with_openai.openai_client.chat.completions.create.return_value = mock_response
            
            with pytest.raises(RuntimeError, match="LLM返回了空答案"):
                await rag_service_with_openai.generate_answer(
                    question=question,
                    context_chunks=context_chunks
                )
    
    @pytest.mark.asyncio
    async def test_generate_answer_with_multiple_context_chunks(
        self,
        rag_service_with_openai: RAGService
    ):
        """测试多个上下文块的答案生成"""
        question = "如何准备辩论？"
        context_chunks = [
            {
                "content": "准备辩论的第一步是充分理解辩题。",
                "document_name": "辩论准备指南.pdf",
                "similarity_score": 0.92
            },
            {
                "content": "收集相关资料和证据是辩论准备的关键。",
                "document_name": "辩论技巧.pdf",
                "similarity_score": 0.88
            },
            {
                "content": "练习演讲和应对反驳也很重要。",
                "document_name": "辩论训练.pdf",
                "similarity_score": 0.85
            }
        ]
        
        # 模拟ConfigService
        mock_config = MagicMock()
        mock_config.model_name = "gpt-3.5-turbo"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000
        
        # 模拟OpenAI响应
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "根据提供的资料，准备辩论需要：1. 充分理解辩题 2. 收集相关资料和证据 3. 练习演讲和应对反驳。"
        mock_response.usage.total_tokens = 200
        
        with patch('services.rag_service.ConfigService') as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(return_value=mock_config)
            
            rag_service_with_openai.openai_client.chat.completions.create.return_value = mock_response
            
            answer = await rag_service_with_openai.generate_answer(
                question=question,
                context_chunks=context_chunks
            )
            
            # 验证答案
            assert answer
            assert isinstance(answer, str)
            
            # 验证所有文档名称都被包含在提示词中
            call_args = rag_service_with_openai.openai_client.chat.completions.create.call_args
            user_content = call_args.kwargs['messages'][1]['content']
            assert "辩论准备指南.pdf" in user_content
            assert "辩论技巧.pdf" in user_content
            assert "辩论训练.pdf" in user_content


class TestFormatSourceCitations:
    """来源引用格式化测试类"""
    
    @pytest.fixture
    def rag_service(self, db_session: Session):
        """创建RAG服务实例"""
        return RAGService(db_session)
    
    def test_format_source_citations_empty_list(
        self,
        rag_service: RAGService
    ):
        """测试空的检索块列表"""
        sources = rag_service.format_source_citations([])
        
        # 应该返回空列表
        assert sources == []
        assert isinstance(sources, list)
    
    def test_format_source_citations_single_chunk(
        self,
        rag_service: RAGService
    ):
        """测试单个文档块"""
        chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_name": "辩论基础.pdf",
                "content": "辩论是一种通过逻辑推理和证据支持来论证观点的交流方式。",
                "chunk_index": 0,
                "token_count": 20,
                "similarity_score": 0.95
            }
        ]
        
        sources = rag_service.format_source_citations(chunks)
        
        # 验证结果
        assert len(sources) == 1
        assert sources[0]["document_id"] == chunks[0]["document_id"]
        assert sources[0]["document_name"] == "辩论基础.pdf"
        assert sources[0]["excerpt"] == chunks[0]["content"]
        assert sources[0]["similarity_score"] == 0.95
    
    def test_format_source_citations_long_content_truncation(
        self,
        rag_service: RAGService
    ):
        """测试长内容的截断"""
        long_content = "这是一段很长的内容。" * 50  # 生成超过200字符的内容
        
        chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_name": "长文档.pdf",
                "content": long_content,
                "chunk_index": 0,
                "token_count": 100,
                "similarity_score": 0.88
            }
        ]
        
        sources = rag_service.format_source_citations(chunks)
        
        # 验证摘录被截断
        assert len(sources) == 1
        assert len(sources[0]["excerpt"]) <= 203  # 200 + "..."
        assert sources[0]["excerpt"].endswith("...")
        assert sources[0]["excerpt"].startswith("这是一段很长的内容。")
    
    def test_format_source_citations_multiple_chunks(
        self,
        rag_service: RAGService
    ):
        """测试多个文档块"""
        chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_name": "文档1.pdf",
                "content": "内容1",
                "chunk_index": 0,
                "token_count": 10,
                "similarity_score": 0.95
            },
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_name": "文档2.pdf",
                "content": "内容2",
                "chunk_index": 0,
                "token_count": 10,
                "similarity_score": 0.88
            },
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_name": "文档3.pdf",
                "content": "内容3",
                "chunk_index": 0,
                "token_count": 10,
                "similarity_score": 0.82
            }
        ]
        
        sources = rag_service.format_source_citations(chunks)
        
        # 验证所有块都被格式化
        assert len(sources) == 3
        
        # 验证每个来源的字段
        for i, source in enumerate(sources):
            assert source["document_id"] == chunks[i]["document_id"]
            assert source["document_name"] == chunks[i]["document_name"]
            assert source["excerpt"] == chunks[i]["content"]
            assert source["similarity_score"] == chunks[i]["similarity_score"]
    
    def test_format_source_citations_missing_required_fields(
        self,
        rag_service: RAGService
    ):
        """测试缺少必需字段的块"""
        chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_name": "完整文档.pdf",
                "content": "完整内容",
                "similarity_score": 0.95
            },
            {
                # 缺少document_name
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "content": "缺少名称",
                "similarity_score": 0.88
            },
            {
                # 缺少content
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_name": "缺少内容.pdf",
                "similarity_score": 0.82
            }
        ]
        
        sources = rag_service.format_source_citations(chunks)
        
        # 只有第一个块应该被包含
        assert len(sources) == 1
        assert sources[0]["document_name"] == "完整文档.pdf"
    
    def test_format_source_citations_invalid_input_type(
        self,
        rag_service: RAGService
    ):
        """测试无效的输入类型"""
        # 不是列表
        with pytest.raises(ValueError, match="retrieved_chunks必须是列表"):
            rag_service.format_source_citations("not a list")  # type: ignore
    
    def test_format_source_citations_similarity_score_rounding(
        self,
        rag_service: RAGService
    ):
        """测试相似度分数的四舍五入"""
        chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_name": "测试.pdf",
                "content": "测试内容",
                "similarity_score": 0.123456789
            }
        ]
        
        sources = rag_service.format_source_citations(chunks)
        
        # 验证相似度分数被四舍五入到4位小数
        assert sources[0]["similarity_score"] == 0.1235
    
    def test_format_source_citations_preserves_document_id(
        self,
        rag_service: RAGService
    ):
        """测试文档ID被正确保留"""
        doc_id = str(uuid.uuid4())
        chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": doc_id,
                "document_name": "测试.pdf",
                "content": "测试内容",
                "similarity_score": 0.9
            }
        ]
        
        sources = rag_service.format_source_citations(chunks)
        
        # 验证文档ID被正确保留
        assert sources[0]["document_id"] == doc_id
    
    def test_format_source_citations_short_content_no_truncation(
        self,
        rag_service: RAGService
    ):
        """测试短内容不被截断"""
        short_content = "这是一段短内容。"
        
        chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_name": "短文档.pdf",
                "content": short_content,
                "similarity_score": 0.9
            }
        ]
        
        sources = rag_service.format_source_citations(chunks)
        
        # 验证短内容不被截断
        assert sources[0]["excerpt"] == short_content
        assert not sources[0]["excerpt"].endswith("...")


class TestAskQuestion:
    """问答功能测试类"""
    
    @pytest.fixture
    def rag_service_with_openai(self, db_session: Session):
        """创建带有模拟OpenAI客户端的RAG服务实例"""
        service = RAGService(db_session)
        service.openai_client = MagicMock()
        return service
    
    @pytest.mark.asyncio
    async def test_ask_question_empty_question(
        self,
        rag_service_with_openai: RAGService
    ):
        """测试空问题"""
        with pytest.raises(ValueError, match="问题不能为空"):
            await rag_service_with_openai.ask_question(
                question="",
                user_id=str(uuid.uuid4()),
                session_id="test_session"
            )
    
    @pytest.mark.asyncio
    async def test_ask_question_empty_user_id(
        self,
        rag_service_with_openai: RAGService
    ):
        """测试空用户ID"""
        with pytest.raises(ValueError, match="用户ID不能为空"):
            await rag_service_with_openai.ask_question(
                question="什么是辩论？",
                user_id="",
                session_id="test_session"
            )
    
    @pytest.mark.asyncio
    async def test_ask_question_empty_session_id(
        self,
        rag_service_with_openai: RAGService
    ):
        """测试空会话ID"""
        with pytest.raises(ValueError, match="会话ID不能为空"):
            await rag_service_with_openai.ask_question(
                question="什么是辩论？",
                user_id=str(uuid.uuid4()),
                session_id=""
            )
    
    @pytest.mark.asyncio
    async def test_ask_question_with_kb_sources(
        self,
        rag_service_with_openai: RAGService
    ):
        """测试使用知识库来源的问答"""
        question = "什么是辩论？"
        user_id = str(uuid.uuid4())
        session_id = "test_session"
        
        # 模拟嵌入向量生成
        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock()]
        mock_embedding_response.data[0].embedding = [0.5] * 1536
        
        # 模拟LLM响应
        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        mock_llm_response.choices[0].message.content = "根据辩论基础文档，辩论是一种通过逻辑推理和证据支持来论证观点的交流方式。"
        mock_llm_response.usage.total_tokens = 100
        
        # 模拟ConfigService
        mock_config = MagicMock()
        mock_config.model_name = "gpt-3.5-turbo"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000
        
        # 模拟相似块搜索结果
        mock_chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_name": "辩论基础.pdf",
                "content": "辩论是一种通过逻辑推理和证据支持来论证观点的交流方式。",
                "chunk_index": 0,
                "token_count": 20,
                "similarity_score": 0.95
            }
        ]
        
        with patch('services.rag_service.ConfigService') as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(return_value=mock_config)
            
            # 设置OpenAI客户端的返回值
            rag_service_with_openai.openai_client.embeddings.create.return_value = mock_embedding_response
            rag_service_with_openai.openai_client.chat.completions.create.return_value = mock_llm_response
            
            # 模拟search_similar_chunks方法
            with patch.object(
                rag_service_with_openai,
                'search_similar_chunks',
                return_value=mock_chunks
            ):
                result = await rag_service_with_openai.ask_question(
                    question=question,
                    user_id=user_id,
                    session_id=session_id
                )
        
        # 验证结果
        assert "answer" in result
        assert "sources" in result
        assert "used_kb" in result
        assert "confidence" in result
        
        # 验证使用了知识库
        assert result["used_kb"] is True
        assert len(result["sources"]) == 1
        
        # 验证来源格式
        source = result["sources"][0]
        assert "document_id" in source
        assert "document_name" in source
        assert "excerpt" in source
        assert "similarity_score" in source
        assert source["document_name"] == "辩论基础.pdf"
        
        # 验证置信度为高（相似度0.95 >= 0.75）
        assert result["confidence"] == "high"
    
    @pytest.mark.asyncio
    async def test_ask_question_without_kb_sources(
        self,
        rag_service_with_openai: RAGService
    ):
        """测试不使用知识库来源的问答"""
        question = "什么是辩论？"
        user_id = str(uuid.uuid4())
        session_id = "test_session"
        
        # 模拟嵌入向量生成
        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock()]
        mock_embedding_response.data[0].embedding = [0.5] * 1536
        
        # 模拟LLM响应
        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        mock_llm_response.choices[0].message.content = "辩论是一种通过逻辑推理和证据支持来论证观点的交流方式。"
        mock_llm_response.usage.total_tokens = 100
        
        # 模拟ConfigService
        mock_config = MagicMock()
        mock_config.model_name = "gpt-3.5-turbo"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000
        
        with patch('services.rag_service.ConfigService') as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(return_value=mock_config)
            
            # 设置OpenAI客户端的返回值
            rag_service_with_openai.openai_client.embeddings.create.return_value = mock_embedding_response
            rag_service_with_openai.openai_client.chat.completions.create.return_value = mock_llm_response
            
            # 模拟search_similar_chunks返回空列表
            with patch.object(
                rag_service_with_openai,
                'search_similar_chunks',
                return_value=[]
            ):
                result = await rag_service_with_openai.ask_question(
                    question=question,
                    user_id=user_id,
                    session_id=session_id
                )
        
        # 验证结果
        assert "answer" in result
        assert "sources" in result
        assert "used_kb" in result
        assert "confidence" in result
        
        # 验证没有使用知识库
        assert result["used_kb"] is False
        assert len(result["sources"]) == 0
        # 验证置信度为none（未使用知识库）
        assert result["confidence"] == "none"
    
    @pytest.mark.asyncio
    async def test_ask_question_high_confidence(
        self,
        rag_service_with_openai: RAGService
    ):
        """测试高置信度的问答（相似度 >= 0.75）"""
        question = "什么是辩论？"
        user_id = str(uuid.uuid4())
        session_id = "test_session"
        
        # 模拟嵌入向量生成
        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock()]
        mock_embedding_response.data[0].embedding = [0.5] * 1536
        
        # 模拟LLM响应
        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        mock_llm_response.choices[0].message.content = "根据辩论基础文档，辩论是一种通过逻辑推理和证据支持来论证观点的交流方式。"
        mock_llm_response.usage.total_tokens = 100
        
        # 模拟ConfigService
        mock_config = MagicMock()
        mock_config.model_name = "gpt-3.5-turbo"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000
        
        # 模拟高相似度的搜索结果
        mock_chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_name": "辩论基础.pdf",
                "content": "辩论是一种通过逻辑推理和证据支持来论证观点的交流方式。",
                "chunk_index": 0,
                "token_count": 20,
                "similarity_score": 0.95  # 高相似度
            }
        ]
        
        with patch('services.rag_service.ConfigService') as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(return_value=mock_config)
            
            # 设置OpenAI客户端的返回值
            rag_service_with_openai.openai_client.embeddings.create.return_value = mock_embedding_response
            rag_service_with_openai.openai_client.chat.completions.create.return_value = mock_llm_response
            
            # 模拟search_similar_chunks方法
            with patch.object(
                rag_service_with_openai,
                'search_similar_chunks',
                return_value=mock_chunks
            ):
                result = await rag_service_with_openai.ask_question(
                    question=question,
                    user_id=user_id,
                    session_id=session_id
                )
        
        # 验证结果
        assert "answer" in result
        assert "sources" in result
        assert "used_kb" in result
        assert "confidence" in result
        
        # 验证使用了知识库且置信度高
        assert result["used_kb"] is True
        assert len(result["sources"]) == 1
        assert result["confidence"] == "high"
    
    @pytest.mark.asyncio
    async def test_ask_question_low_confidence(
        self,
        rag_service_with_openai: RAGService
    ):
        """测试低置信度的问答（相似度 < 0.75）"""
        question = "什么是辩论？"
        user_id = str(uuid.uuid4())
        session_id = "test_session"
        
        # 模拟嵌入向量生成
        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock()]
        mock_embedding_response.data[0].embedding = [0.5] * 1536
        
        # 模拟LLM响应
        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        mock_llm_response.choices[0].message.content = "根据相关资料，辩论是一种交流方式。"
        mock_llm_response.usage.total_tokens = 100
        
        # 模拟ConfigService
        mock_config = MagicMock()
        mock_config.model_name = "gpt-3.5-turbo"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000
        
        # 模拟低相似度的搜索结果
        mock_chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_name": "辩论相关.pdf",
                "content": "一些相关但不太匹配的内容。",
                "chunk_index": 0,
                "token_count": 15,
                "similarity_score": 0.72  # 低相似度（超过阈值0.7但低于0.75）
            }
        ]
        
        with patch('services.rag_service.ConfigService') as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(return_value=mock_config)
            
            # 设置OpenAI客户端的返回值
            rag_service_with_openai.openai_client.embeddings.create.return_value = mock_embedding_response
            rag_service_with_openai.openai_client.chat.completions.create.return_value = mock_llm_response
            
            # 模拟search_similar_chunks方法
            with patch.object(
                rag_service_with_openai,
                'search_similar_chunks',
                return_value=mock_chunks
            ):
                result = await rag_service_with_openai.ask_question(
                    question=question,
                    user_id=user_id,
                    session_id=session_id
                )
        
        # 验证结果
        assert "answer" in result
        assert "sources" in result
        assert "used_kb" in result
        assert "confidence" in result
        
        # 验证使用了知识库但置信度低
        assert result["used_kb"] is True
        assert len(result["sources"]) == 1
        assert result["confidence"] == "low"
    
    @pytest.mark.asyncio
    async def test_ask_question_confidence_boundary(
        self,
        rag_service_with_openai: RAGService
    ):
        """测试置信度边界值（相似度 = 0.75）"""
        question = "什么是辩论？"
        user_id = str(uuid.uuid4())
        session_id = "test_session"
        
        # 模拟嵌入向量生成
        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock()]
        mock_embedding_response.data[0].embedding = [0.5] * 1536
        
        # 模拟LLM响应
        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        mock_llm_response.choices[0].message.content = "根据辩论基础文档，辩论是一种交流方式。"
        mock_llm_response.usage.total_tokens = 100
        
        # 模拟ConfigService
        mock_config = MagicMock()
        mock_config.model_name = "gpt-3.5-turbo"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000
        
        # 模拟边界相似度的搜索结果
        mock_chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_name": "辩论基础.pdf",
                "content": "辩论相关内容。",
                "chunk_index": 0,
                "token_count": 15,
                "similarity_score": 0.75  # 边界值
            }
        ]
        
        with patch('services.rag_service.ConfigService') as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(return_value=mock_config)
            
            # 设置OpenAI客户端的返回值
            rag_service_with_openai.openai_client.embeddings.create.return_value = mock_embedding_response
            rag_service_with_openai.openai_client.chat.completions.create.return_value = mock_llm_response
            
            # 模拟search_similar_chunks方法
            with patch.object(
                rag_service_with_openai,
                'search_similar_chunks',
                return_value=mock_chunks
            ):
                result = await rag_service_with_openai.ask_question(
                    question=question,
                    user_id=user_id,
                    session_id=session_id
                )
        
        # 验证结果 - 0.75应该被视为高置信度（>= 0.75）
        assert result["confidence"] == "high"


class TestGetConversationHistory:
    """对话历史获取测试类"""
    
    @pytest.fixture
    def rag_service(self, db_session: Session):
        """创建RAG服务实例"""
        return RAGService(db_session)
    
    def test_get_conversation_history_empty_user_id(
        self,
        rag_service: RAGService
    ):
        """测试空用户ID"""
        with pytest.raises(ValueError, match="用户ID不能为空"):
            rag_service.get_conversation_history(
                user_id="",
                session_id="test_session"
            )
    
    def test_get_conversation_history_empty_session_id(
        self,
        rag_service: RAGService
    ):
        """测试空会话ID"""
        with pytest.raises(ValueError, match="会话ID不能为空"):
            rag_service.get_conversation_history(
                user_id=str(uuid.uuid4()),
                session_id=""
            )
    
    def test_get_conversation_history_invalid_limit(
        self,
        rag_service: RAGService
    ):
        """测试无效的limit值"""
        with pytest.raises(ValueError, match="limit必须大于0"):
            rag_service.get_conversation_history(
                user_id=str(uuid.uuid4()),
                session_id="test_session",
                limit=0
            )


class TestConversationStorage:
    """对话存储测试类 - 验证Requirements 8.1, 8.2"""
    
    @pytest.fixture
    def rag_service_with_openai(self, db_session: Session):
        """创建带有模拟OpenAI客户端的RAG服务实例"""
        service = RAGService(db_session)
        service.openai_client = MagicMock()
        return service
    
    @pytest.mark.asyncio
    async def test_conversation_storage_saves_all_fields(
        self,
        rag_service_with_openai: RAGService,
        db_session: Session
    ):
        """
        测试对话存储包含所有必需字段
        验证Requirements 8.1, 8.2: 存储question, answer, sources, user_id, session_id, timestamp
        """
        question = "什么是辩论？"
        user_id = str(uuid.uuid4())
        session_id = "test_session_123"
        
        # 模拟嵌入向量生成
        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock()]
        mock_embedding_response.data[0].embedding = [0.5] * 1536
        
        # 模拟LLM响应
        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        mock_llm_response.choices[0].message.content = "辩论是一种交流方式。"
        mock_llm_response.usage.total_tokens = 100
        
        # 模拟ConfigService
        mock_config = MagicMock()
        mock_config.model_name = "gpt-3.5-turbo"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000
        
        # 模拟搜索结果
        mock_chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_name": "辩论基础.pdf",
                "content": "辩论相关内容",
                "chunk_index": 0,
                "token_count": 10,
                "similarity_score": 0.85
            }
        ]
        
        with patch('services.rag_service.ConfigService') as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(return_value=mock_config)
            
            rag_service_with_openai.openai_client.embeddings.create.return_value = mock_embedding_response
            rag_service_with_openai.openai_client.chat.completions.create.return_value = mock_llm_response
            
            with patch.object(
                rag_service_with_openai,
                'search_similar_chunks',
                return_value=mock_chunks
            ):
                # 执行问答
                result = await rag_service_with_openai.ask_question(
                    question=question,
                    user_id=user_id,
                    session_id=session_id
                )
        
        # 从数据库中检索保存的对话
        from models.kb_conversation import KBConversation
        saved_conversation = db_session.query(KBConversation).filter(
            KBConversation.user_id == uuid.UUID(user_id),
            KBConversation.session_id == session_id
        ).first()
        
        # 验证对话已保存
        assert saved_conversation is not None, "对话应该被保存到数据库"
        
        # 验证所有必需字段
        assert saved_conversation.question == question, "问题应该被正确保存"
        assert saved_conversation.answer == result["answer"], "答案应该被正确保存"
        assert saved_conversation.user_id == uuid.UUID(user_id), "用户ID应该被正确保存"
        assert saved_conversation.session_id == session_id, "会话ID应该被正确保存"
        assert saved_conversation.sources is not None, "来源应该被保存"
        assert isinstance(saved_conversation.sources, list), "来源应该是列表"
        assert len(saved_conversation.sources) > 0, "应该有来源信息"
        assert saved_conversation.created_at is not None, "创建时间应该被保存"
        
        # 验证来源字段的结构（JSONB）
        source = saved_conversation.sources[0]
        assert "document_id" in source, "来源应该包含document_id"
        assert "document_name" in source, "来源应该包含document_name"
        assert "excerpt" in source, "来源应该包含excerpt"
        assert "similarity_score" in source, "来源应该包含similarity_score"
    
    @pytest.mark.asyncio
    async def test_conversation_storage_with_empty_sources(
        self,
        rag_service_with_openai: RAGService,
        db_session: Session
    ):
        """
        测试没有知识库来源时的对话存储
        验证Requirements 8.1, 8.2: sources字段可以为空列表
        """
        question = "什么是辩论？"
        user_id = str(uuid.uuid4())
        session_id = "test_session_empty_sources"
        
        # 模拟嵌入向量生成
        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock()]
        mock_embedding_response.data[0].embedding = [0.5] * 1536
        
        # 模拟LLM响应
        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        mock_llm_response.choices[0].message.content = "辩论是一种交流方式。"
        mock_llm_response.usage.total_tokens = 100
        
        # 模拟ConfigService
        mock_config = MagicMock()
        mock_config.model_name = "gpt-3.5-turbo"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000
        
        with patch('services.rag_service.ConfigService') as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(return_value=mock_config)
            
            rag_service_with_openai.openai_client.embeddings.create.return_value = mock_embedding_response
            rag_service_with_openai.openai_client.chat.completions.create.return_value = mock_llm_response
            
            # 模拟没有搜索结果
            with patch.object(
                rag_service_with_openai,
                'search_similar_chunks',
                return_value=[]
            ):
                # 执行问答
                result = await rag_service_with_openai.ask_question(
                    question=question,
                    user_id=user_id,
                    session_id=session_id
                )
        
        # 从数据库中检索保存的对话
        from models.kb_conversation import KBConversation
        saved_conversation = db_session.query(KBConversation).filter(
            KBConversation.user_id == uuid.UUID(user_id),
            KBConversation.session_id == session_id
        ).first()
        
        # 验证对话已保存
        assert saved_conversation is not None, "对话应该被保存到数据库"
        
        # 验证sources为空列表
        assert saved_conversation.sources == [], "没有知识库来源时sources应该为空列表"
        assert result["used_kb"] is False, "used_kb应该为False"
    
    @pytest.mark.asyncio
    async def test_conversation_storage_timestamp_ordering(
        self,
        rag_service_with_openai: RAGService,
        db_session: Session
    ):
        """
        测试对话按时间戳排序
        验证Requirements 8.2: 添加timestamp用于排序
        """
        user_id = str(uuid.uuid4())
        session_id = "test_session_ordering"
        
        # 模拟嵌入向量生成
        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock()]
        mock_embedding_response.data[0].embedding = [0.5] * 1536
        
        # 模拟LLM响应
        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        mock_llm_response.choices[0].message.content = "这是答案。"
        mock_llm_response.usage.total_tokens = 100
        
        # 模拟ConfigService
        mock_config = MagicMock()
        mock_config.model_name = "gpt-3.5-turbo"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000
        
        with patch('services.rag_service.ConfigService') as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(return_value=mock_config)
            
            rag_service_with_openai.openai_client.embeddings.create.return_value = mock_embedding_response
            rag_service_with_openai.openai_client.chat.completions.create.return_value = mock_llm_response
            
            with patch.object(
                rag_service_with_openai,
                'search_similar_chunks',
                return_value=[]
            ):
                # 创建多个对话
                questions = ["问题1", "问题2", "问题3"]
                for question in questions:
                    await rag_service_with_openai.ask_question(
                        question=question,
                        user_id=user_id,
                        session_id=session_id
                    )
        
        # 获取对话历史
        history = rag_service_with_openai.get_conversation_history(
            user_id=user_id,
            session_id=session_id,
            limit=10
        )
        
        # 验证对话数量
        assert len(history) == 3, "应该有3条对话记录"
        
        # 验证按时间倒序排列（最新的在前）
        assert history[0]["question"] == "问题3", "最新的对话应该在最前面"
        assert history[1]["question"] == "问题2"
        assert history[2]["question"] == "问题1"
        
        # 验证所有对话都有created_at字段
        for conv in history:
            assert "created_at" in conv, "每条对话都应该有created_at字段"
            assert conv["created_at"] is not None, "created_at不应该为空"
    
    @pytest.mark.asyncio
    async def test_conversation_storage_rollback_on_failure(
        self,
        rag_service_with_openai: RAGService,
        db_session: Session
    ):
        """
        测试保存失败时的回滚
        验证：保存失败不影响返回结果
        """
        question = "什么是辩论？"
        user_id = str(uuid.uuid4())
        session_id = "test_session_rollback"
        
        # 模拟嵌入向量生成
        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock()]
        mock_embedding_response.data[0].embedding = [0.5] * 1536
        
        # 模拟LLM响应
        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        mock_llm_response.choices[0].message.content = "辩论是一种交流方式。"
        mock_llm_response.usage.total_tokens = 100
        
        # 模拟ConfigService
        mock_config = MagicMock()
        mock_config.model_name = "gpt-3.5-turbo"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000
        
        with patch('services.rag_service.ConfigService') as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(return_value=mock_config)
            
            rag_service_with_openai.openai_client.embeddings.create.return_value = mock_embedding_response
            rag_service_with_openai.openai_client.chat.completions.create.return_value = mock_llm_response
            
            with patch.object(
                rag_service_with_openai,
                'search_similar_chunks',
                return_value=[]
            ):
                # 模拟数据库提交失败
                with patch.object(db_session, 'commit', side_effect=Exception("Database error")):
                    # 执行问答 - 应该不抛出异常
                    result = await rag_service_with_openai.ask_question(
                        question=question,
                        user_id=user_id,
                        session_id=session_id
                    )
        
        # 验证仍然返回了结果
        assert "answer" in result, "即使保存失败也应该返回答案"
        assert "sources" in result
        assert "used_kb" in result
        assert "confidence" in result
    
    @pytest.mark.asyncio
    async def test_conversation_storage_jsonb_sources_format(
        self,
        rag_service_with_openai: RAGService,
        db_session: Session
    ):
        """
        测试JSONB sources字段的格式
        验证Requirements 8.1: 使用JSONB存储sources
        """
        question = "什么是辩论？"
        user_id = str(uuid.uuid4())
        session_id = "test_session_jsonb"
        
        # 模拟嵌入向量生成
        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock()]
        mock_embedding_response.data[0].embedding = [0.5] * 1536
        
        # 模拟LLM响应
        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        mock_llm_response.choices[0].message.content = "辩论是一种交流方式。"
        mock_llm_response.usage.total_tokens = 100
        
        # 模拟ConfigService
        mock_config = MagicMock()
        mock_config.model_name = "gpt-3.5-turbo"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000
        
        # 模拟多个搜索结果
        doc_id_1 = str(uuid.uuid4())
        doc_id_2 = str(uuid.uuid4())
        mock_chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": doc_id_1,
                "document_name": "文档1.pdf",
                "content": "内容1" * 100,  # 长内容，会被截断
                "chunk_index": 0,
                "token_count": 50,
                "similarity_score": 0.95
            },
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": doc_id_2,
                "document_name": "文档2.pdf",
                "content": "内容2",
                "chunk_index": 1,
                "token_count": 10,
                "similarity_score": 0.85
            }
        ]
        
        with patch('services.rag_service.ConfigService') as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(return_value=mock_config)
            
            rag_service_with_openai.openai_client.embeddings.create.return_value = mock_embedding_response
            rag_service_with_openai.openai_client.chat.completions.create.return_value = mock_llm_response
            
            with patch.object(
                rag_service_with_openai,
                'search_similar_chunks',
                return_value=mock_chunks
            ):
                # 执行问答
                await rag_service_with_openai.ask_question(
                    question=question,
                    user_id=user_id,
                    session_id=session_id
                )
        
        # 从数据库中检索保存的对话
        from models.kb_conversation import KBConversation
        saved_conversation = db_session.query(KBConversation).filter(
            KBConversation.user_id == uuid.UUID(user_id),
            KBConversation.session_id == session_id
        ).first()
        
        # 验证JSONB sources字段的格式
        assert saved_conversation.sources is not None
        assert isinstance(saved_conversation.sources, list)
        assert len(saved_conversation.sources) == 2
        
        # 验证第一个来源
        source1 = saved_conversation.sources[0]
        assert source1["document_id"] == doc_id_1
        assert source1["document_name"] == "文档1.pdf"
        assert "excerpt" in source1
        assert len(source1["excerpt"]) <= 203  # 应该被截断（200 + "..."）
        assert source1["similarity_score"] == 0.95
        
        # 验证第二个来源
        source2 = saved_conversation.sources[1]
        assert source2["document_id"] == doc_id_2
        assert source2["document_name"] == "文档2.pdf"
        assert source2["excerpt"] == "内容2"  # 短内容不应该被截断
        assert source2["similarity_score"] == 0.85


class TestAskQuestionStreamPersistence:
    """流式问答持久化测试。"""

    @pytest.fixture
    def rag_service_with_openai(self, db_session: Session):
        service = RAGService(db_session)
        service.openai_client = MagicMock()
        service.embedding_model = "test-embedding-model"
        return service

    def _make_stream_chunk(self, content: str) -> MagicMock:
        chunk = MagicMock()
        choice = MagicMock()
        choice.delta.content = content
        chunk.choices = [choice]
        return chunk

    @pytest.mark.asyncio
    async def test_ask_question_stream_persists_completed_answer(
        self,
        rag_service_with_openai: RAGService,
        db_session: Session
    ):
        question = "什么是辩论？"
        user_id = str(uuid.uuid4())
        session_id = "stream_session_completed"

        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock()]
        mock_embedding_response.data[0].embedding = [0.5] * 1536
        rag_service_with_openai.openai_client.embeddings.create.return_value = (
            mock_embedding_response
        )

        mock_config = MagicMock()
        mock_config.model_name = "qwen3.5-flash"
        mock_config.api_endpoint = "https://example.com/v1/chat/completions"
        mock_config.api_key = "test-key"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000

        mock_chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_name": "辩论基础.pdf",
                "content": "辩论是一种通过论证表达观点的交流方式。",
                "chunk_index": 0,
                "token_count": 20,
                "similarity_score": 0.91,
            }
        ]

        llm_client = MagicMock()
        llm_client.chat.completions.create.return_value = [
            self._make_stream_chunk("segment-one"),
            self._make_stream_chunk("segment-two"),
        ]

        with patch("services.rag_service.ConfigService") as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(
                return_value=mock_config
            )

            with patch.object(
                rag_service_with_openai,
                "search_similar_chunks",
                return_value=mock_chunks
            ):
                with patch(
                    "services.rag_service.OpenAI",
                    return_value=llm_client
                ):
                    events = []
                    async for raw_event in rag_service_with_openai.ask_question_stream(
                        question=question,
                        user_id=user_id,
                        session_id=session_id
                    ):
                        events.append(json.loads(raw_event))

        assert [event["type"] for event in events] == [
            "sources",
            "answer",
            "answer",
            "done",
        ]

        from models.kb_conversation import KBConversation

        saved_conversation = db_session.query(KBConversation).filter(
            KBConversation.user_id == uuid.UUID(user_id),
            KBConversation.session_id == session_id
        ).first()

        assert saved_conversation is not None
        assert saved_conversation.question == question
        assert saved_conversation.answer == "segment-onesegment-two"
        assert saved_conversation.sources == events[0]["data"]
        assert events[-1]["id"] == str(saved_conversation.id)

    @pytest.mark.asyncio
    async def test_ask_question_stream_persists_partial_answer_when_cancelled(
        self,
        rag_service_with_openai: RAGService,
        db_session: Session
    ):
        question = "如何构建论点？"
        user_id = str(uuid.uuid4())
        session_id = "stream_session_cancelled"

        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock()]
        mock_embedding_response.data[0].embedding = [0.5] * 1536
        rag_service_with_openai.openai_client.embeddings.create.return_value = (
            mock_embedding_response
        )

        mock_config = MagicMock()
        mock_config.model_name = "qwen3.5-flash"
        mock_config.api_endpoint = "https://example.com/v1/chat/completions"
        mock_config.api_key = "test-key"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2000

        llm_client = MagicMock()

        def interrupted_stream():
            yield self._make_stream_chunk("partial-answer")
            raise asyncio.CancelledError()

        llm_client.chat.completions.create.return_value = interrupted_stream()

        with patch("services.rag_service.ConfigService") as MockConfigService:
            mock_config_service = MockConfigService.return_value
            mock_config_service.get_model_config = AsyncMock(
                return_value=mock_config
            )

            with patch.object(
                rag_service_with_openai,
                "search_similar_chunks",
                return_value=[]
            ):
                with patch(
                    "services.rag_service.OpenAI",
                    return_value=llm_client
                ):
                    events = []
                    with pytest.raises(asyncio.CancelledError):
                        async for raw_event in rag_service_with_openai.ask_question_stream(
                            question=question,
                            user_id=user_id,
                            session_id=session_id
                        ):
                            events.append(json.loads(raw_event))

        assert [event["type"] for event in events] == ["sources", "answer"]

        from models.kb_conversation import KBConversation

        saved_conversation = db_session.query(KBConversation).filter(
            KBConversation.user_id == uuid.UUID(user_id),
            KBConversation.session_id == session_id
        ).first()

        assert saved_conversation is not None
        assert saved_conversation.question == question
        assert "partial-answer" in saved_conversation.answer
        assert "回答未完成" in saved_conversation.answer
        assert saved_conversation.sources == []


# 集成测试标记 - 需要PostgreSQL + pgvector
@pytest.mark.integration
@pytest.mark.skipif(
    True,  # 默认跳过，需要PostgreSQL环境时设置为False
    reason="需要PostgreSQL + pgvector环境"
)
class TestRAGServiceIntegration:
    """RAG服务集成测试（需要PostgreSQL + pgvector）"""
    
    @pytest.mark.asyncio
    async def test_search_similar_chunks_real_database(self):
        """
        使用真实PostgreSQL数据库测试向量搜索
        
        注意：此测试需要：
        1. PostgreSQL数据库
        2. pgvector扩展
        3. 正确的数据库连接配置
        """
        # TODO: 实现真实数据库的集成测试
        pass
