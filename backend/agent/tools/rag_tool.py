"""RAG 知识库工具

使用 ChromaDB 向量数据库存储和检索旅游攻略
支持 TXT、PDF、CSV、MD 格式的文档导入
"""
import os
import json
from typing import List, Optional, Dict, Any
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    CSVLoader,
    UnstructuredMarkdownLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from backend.config.settings import settings


class TravelRAGTool:
    """旅游攻略向量检索工具

    功能：
    - 从多种格式文档构建知识库
    - 语义相似度检索
    - 支持增量更新
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        embedding_model: str = "text-embedding-v3"
    ):
        """初始化 RAG 工具

        Args:
            persist_dir: 向量数据库持久化目录
            embedding_model: Embedding 模型名称
        """
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self.embedding_model = embedding_model

        # 初始化 Embedding
        self.embeddings = DashScopeEmbeddings(
            model=embedding_model,
            dashscope_api_key=settings.dashscope_api_key
        )

        # 初始化向量数据库
        self.vectorstore: Optional[Chroma] = None
        self._initialize_vectorstore()

        # 文本分割器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
        )

    def _initialize_vectorstore(self):
        """初始化或加载向量数据库"""
        persist_path = Path(self.persist_dir)

        if persist_path.exists() and any(persist_path.iterdir()):
            # 加载已有数据库
            try:
                self.vectorstore = Chroma(
                    persist_directory=str(persist_path),
                    embedding_function=self.embeddings
                )
                print(f"[RAG] 加载已有向量数据库: {self.persist_dir}")
            except Exception as e:
                print(f"[RAG] 加载向量数据库失败: {e}")
                self.vectorstore = None
        else:
            print(f"[RAG] 向量数据库不存在，将在首次导入时创建")

    def search(
        self,
        query: str,
        k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """检索相关文档

        Args:
            query: 查询文本
            k: 返回结果数量，默认使用配置值
            filter_dict: 元数据过滤条件

        Returns:
            相关文档列表
        """
        if not self.vectorstore:
            print("[RAG] 向量数据库未初始化")
            return []

        k = k or settings.rag_top_k

        try:
            if filter_dict:
                results = self.vectorstore.similarity_search(
                    query,
                    k=k,
                    filter=filter_dict
                )
            else:
                results = self.vectorstore.similarity_search(query, k=k)

            print(f"[RAG] 检索 '{query}' 返回 {len(results)} 条结果")
            return results

        except Exception as e:
            print(f"[RAG] 检索失败: {e}")
            return []

    def search_with_scores(
        self,
        query: str,
        k: Optional[int] = None,
        score_threshold: float = 0.0
    ) -> List[tuple]:
        """检索相关文档并返回相似度分数

        Args:
            query: 查询文本
            k: 返回结果数量
            score_threshold: 分数阈值

        Returns:
            (Document, score) 元组列表
        """
        if not self.vectorstore:
            return []

        k = k or settings.rag_top_k

        try:
            results = self.vectorstore.similarity_search_with_score(query, k=k)

            # 过滤低分结果
            if score_threshold > 0:
                results = [(doc, score) for doc, score in results if score >= score_threshold]

            return results

        except Exception as e:
            print(f"[RAG] 检索失败: {e}")
            return []

    def build_knowledge_base(
        self,
        data_dir: str,
        force_recreate: bool = False,
        file_extensions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """从文档目录构建知识库

        Args:
            data_dir: 文档目录路径
            force_recreate: 是否强制重建数据库
            file_extensions: 要处理的文件扩展名列表

        Returns:
            构建结果统计
        """
        data_path = Path(data_dir)
        if not data_path.exists():
            return {"error": f"目录不存在: {data_dir}"}

        file_extensions = file_extensions or [".txt", ".pdf", ".csv", ".md"]

        # 收集所有文档
        all_documents: List[Document] = []
        stats = {
            "total_files": 0,
            "success_files": 0,
            "failed_files": 0,
            "total_chunks": 0,
            "errors": []
        }

        for ext in file_extensions:
            for file_path in data_path.glob(f"*{ext}"):
                stats["total_files"] += 1

                try:
                    docs = self._load_file(file_path)
                    if docs:
                        all_documents.extend(docs)
                        stats["success_files"] += 1
                        print(f"[RAG] ✅ 加载: {file_path.name} ({len(docs)} 个文档块)")
                except Exception as e:
                    stats["failed_files"] += 1
                    stats["errors"].append(f"{file_path.name}: {str(e)}")
                    print(f"[RAG] ❌ 加载失败: {file_path.name} - {e}")

        if not all_documents:
            return {"error": "没有成功加载任何文档", "stats": stats}

        # 分割文档
        split_docs = self.text_splitter.split_documents(all_documents)
        stats["total_chunks"] = len(split_docs)
        print(f"[RAG] 文档分割完成: {len(all_documents)} -> {len(split_docs)} 个块")

        # 创建或更新向量数据库
        persist_path = Path(self.persist_dir)
        persist_path.mkdir(parents=True, exist_ok=True)

        if force_recreate or not self.vectorstore:
            # 创建新数据库
            self.vectorstore = Chroma.from_documents(
                documents=split_docs,
                embedding=self.embeddings,
                persist_directory=str(persist_path)
            )
        else:
            # 增量添加
            self.vectorstore.add_documents(split_docs)

        print(f"[RAG] ✅ 知识库构建完成: {stats['total_chunks']} 个文档块")

        return {
            "success": True,
            "stats": stats
        }

    def _load_file(self, file_path: Path) -> List[Document]:
        """加载单个文件"""
        ext = file_path.suffix.lower()

        loaders = {
            ".txt": lambda: TextLoader(str(file_path), encoding="utf-8"),
            ".pdf": lambda: PyPDFLoader(str(file_path)),
            ".csv": lambda: CSVLoader(str(file_path), encoding="utf-8"),
            ".md": lambda: UnstructuredMarkdownLoader(str(file_path))
        }

        if ext not in loaders:
            raise ValueError(f"不支持的文件格式: {ext}")

        loader = loaders[ext]()
        docs = loader.load()

        # 添加元数据
        for doc in docs:
            doc.metadata["source"] = file_path.name
            doc.metadata["file_type"] = ext

        return docs

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ):
        """直接添加文本到知识库

        Args:
            texts: 文本列表
            metadatas: 元数据列表
        """
        if not self.vectorstore:
            persist_path = Path(self.persist_dir)
            persist_path.mkdir(parents=True, exist_ok=True)

            self.vectorstore = Chroma.from_texts(
                texts=texts,
                embedding=self.embeddings,
                metadatas=metadatas,
                persist_directory=str(persist_path)
            )
        else:
            self.vectorstore.add_texts(texts, metadatas=metadatas)

    def delete_by_source(self, source: str) -> int:
        """删除指定来源的所有文档

        Args:
            source: 文件名或来源标识

        Returns:
            删除的文档数量
        """
        if not self.vectorstore:
            return 0

        try:
            # Chroma 的删除操作
            self.vectorstore._collection.delete(
                where={"source": source}
            )
            print(f"[RAG] 已删除来源 '{source}' 的所有文档")
            return 1
        except Exception as e:
            print(f"[RAG] 删除失败: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        if not self.vectorstore:
            return {
                "initialized": False,
                "total_docs": 0
            }

        try:
            count = self.vectorstore._collection.count()
            return {
                "initialized": True,
                "total_docs": count,
                "persist_dir": self.persist_dir,
                "embedding_model": self.embedding_model
            }
        except Exception as e:
            return {
                "initialized": True,
                "error": str(e)
            }

    def clear(self):
        """清空知识库"""
        if self.vectorstore:
            # 删除所有文档
            self.vectorstore._collection.delete()
            print("[RAG] 知识库已清空")


# ==================== 工具函数 ====================

def format_search_results(docs: List[Document], max_length: int = 500) -> str:
    """格式化搜索结果为文本

    Args:
        docs: 文档列表
        max_length: 每个文档的最大长度

    Returns:
        格式化后的文本
    """
    if not docs:
        return "未找到相关信息"

    lines = []
    for i, doc in enumerate(docs[:5], 1):
        source = doc.metadata.get("source", "未知来源")
        content = doc.page_content[:max_length]
        if len(doc.page_content) > max_length:
            content += "..."
        lines.append(f"{i}. [{source}]\n{content}\n")

    return "\n".join(lines)


# 全局 RAG 实例
_rag_instance: Optional[TravelRAGTool] = None


def get_rag_instance() -> TravelRAGTool:
    """获取全局 RAG 实例"""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = TravelRAGTool()
    return _rag_instance