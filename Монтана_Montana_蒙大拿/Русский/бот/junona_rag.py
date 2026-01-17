# junona_rag.py
# Юнона знает ВСЁ — RAG-система для доступа к полной базе знаний Montana

import os
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

# Пути
MONTANA_ROOT = Path(__file__).parent.parent.parent  # Монтана_Montana_蒙大拿
ACP_ROOT = Path("/Users/kh./Python/ACP_1/Montana ACP")
BOT_DIR = Path(__file__).parent
INDEX_DIR = BOT_DIR / "data" / "rag_index"
METADATA_FILE = INDEX_DIR / "file_hashes.json"

# Расширения для индексации
INDEXABLE_EXTENSIONS = {".md", ".py", ".txt", ".rs", ".toml"}

# Размер чанка (символов)
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200


@dataclass
class Document:
    content: str
    metadata: Dict
    embedding: Optional[List[float]] = None


class JunonaRAG:
    def __init__(self):
        self.index_dir = INDEX_DIR
        self.index_dir.mkdir(parents=True, exist_ok=True)

        # Инициализация векторной базы
        self.collection = None
        self.embedder = None
        self._init_components()

    def _init_components(self):
        """Инициализация ChromaDB и embeddings"""
        try:
            import chromadb
            from chromadb.config import Settings

            # Локальная персистентная база
            self.client = chromadb.PersistentClient(
                path=str(self.index_dir / "chroma"),
                settings=Settings(anonymized_telemetry=False)
            )

            # Коллекция для Montana
            self.collection = self.client.get_or_create_collection(
                name="montana_knowledge",
                metadata={"description": "Полная база знаний Montana"}
            )

            # Embeddings — sentence-transformers (локально, бесплатно)
            from sentence_transformers import SentenceTransformer
            self.embedder = SentenceTransformer('intfloat/multilingual-e5-small')

            print(f"🧠 Юнона RAG: ChromaDB + multilingual-e5-small")
            print(f"   Документов в базе: {self.collection.count()}")

        except ImportError as e:
            print(f"⚠️ RAG недоступен: {e}")
            print("   Установите: pip install chromadb sentence-transformers")

    def _get_file_hash(self, filepath: Path) -> str:
        """SHA256 хеш файла для отслеживания изменений"""
        content = filepath.read_bytes()
        return hashlib.sha256(content).hexdigest()[:16]

    def _load_metadata(self) -> Dict[str, str]:
        """Загрузить хеши проиндексированных файлов"""
        if METADATA_FILE.exists():
            return json.loads(METADATA_FILE.read_text())
        return {}

    def _save_metadata(self, metadata: Dict[str, str]):
        """Сохранить хеши"""
        METADATA_FILE.write_text(json.dumps(metadata, indent=2))

    def _chunk_text(self, text: str, filepath: str) -> List[Document]:
        """Разбить текст на чанки с перекрытием"""
        chunks = []

        # Разбиваем по параграфам сначала
        paragraphs = text.split('\n\n')
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) < CHUNK_SIZE:
                current_chunk += para + "\n\n"
            else:
                if current_chunk.strip():
                    chunks.append(Document(
                        content=current_chunk.strip(),
                        metadata={
                            "source": filepath,
                            "type": Path(filepath).suffix,
                            "lang": self._detect_lang(filepath)
                        }
                    ))
                # Начинаем новый чанк с перекрытием
                overlap = current_chunk[-CHUNK_OVERLAP:] if len(current_chunk) > CHUNK_OVERLAP else ""
                current_chunk = overlap + para + "\n\n"

        # Последний чанк
        if current_chunk.strip():
            chunks.append(Document(
                content=current_chunk.strip(),
                metadata={
                    "source": filepath,
                    "type": Path(filepath).suffix,
                    "lang": self._detect_lang(filepath)
                }
            ))

        return chunks

    def _detect_lang(self, filepath: str) -> str:
        """Определить язык по пути"""
        fp = filepath.lower()
        if "русский" in fp or "russian" in fp:
            return "ru"
        elif "english" in fp:
            return "en"
        elif "中文" in fp or "chinese" in fp:
            return "zh"
        return "ru"  # default

    def _collect_files(self) -> List[Path]:
        """Собрать все файлы для индексации"""
        files = []

        # Montana документация
        for ext in INDEXABLE_EXTENSIONS:
            files.extend(MONTANA_ROOT.rglob(f"*{ext}"))

        # ACP протокол (если есть)
        if ACP_ROOT.exists():
            for ext in INDEXABLE_EXTENSIONS:
                files.extend(ACP_ROOT.rglob(f"*{ext}"))

        # Фильтруем системные файлы
        files = [f for f in files if not any(p in str(f) for p in [
            "__pycache__", ".git", "node_modules", "venv", ".env"
        ])]

        return files

    def index(self, force: bool = False):
        """Проиндексировать все документы Montana"""
        if not self.collection or not self.embedder:
            print("⚠️ RAG не инициализирован")
            return

        files = self._collect_files()
        metadata = self._load_metadata()

        new_docs = 0
        updated_docs = 0

        for filepath in files:
            try:
                file_hash = self._get_file_hash(filepath)
                filepath_str = str(filepath)

                # Пропускаем если не изменился
                if not force and metadata.get(filepath_str) == file_hash:
                    continue

                # Читаем и чанкуем
                try:
                    content = filepath.read_text(encoding='utf-8')
                except UnicodeDecodeError:
                    continue  # пропускаем бинарные файлы

                if len(content) < 50:
                    continue  # слишком короткие

                chunks = self._chunk_text(content, filepath_str)

                # Удаляем старые чанки этого файла
                try:
                    self.collection.delete(where={"source": filepath_str})
                except:
                    pass

                # Добавляем новые
                for i, chunk in enumerate(chunks):
                    doc_id = f"{file_hash}_{i}"
                    embedding = self.embedder.encode(chunk.content).tolist()

                    self.collection.add(
                        ids=[doc_id],
                        embeddings=[embedding],
                        documents=[chunk.content],
                        metadatas=[chunk.metadata]
                    )

                # Обновляем метаданные
                if filepath_str in metadata:
                    updated_docs += 1
                else:
                    new_docs += 1
                metadata[filepath_str] = file_hash

            except Exception as e:
                print(f"⚠️ Ошибка индексации {filepath}: {e}")

        self._save_metadata(metadata)

        print(f"✓ Индексация завершена: +{new_docs} новых, ~{updated_docs} обновлено")
        print(f"  Всего в базе: {self.collection.count()} чанков")

    def search(self, query: str, n_results: int = 5, lang: str = None) -> List[Dict]:
        """Найти релевантные документы"""
        if not self.collection or not self.embedder:
            return []

        # Embedding запроса
        query_embedding = self.embedder.encode(query).tolist()

        # Фильтр по языку (опционально)
        where_filter = {"lang": lang} if lang else None

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        # Форматируем результаты
        docs = []
        for i in range(len(results['documents'][0])):
            docs.append({
                "content": results['documents'][0][i],
                "source": results['metadatas'][0][i]['source'],
                "lang": results['metadatas'][0][i]['lang'],
                "score": 1 - results['distances'][0][i]  # similarity score
            })

        return docs

    def get_context(self, query: str, max_tokens: int = 2000) -> str:
        """Получить контекст для LLM из релевантных документов"""
        docs = self.search(query, n_results=5)

        if not docs:
            return ""

        context_parts = []
        current_tokens = 0  # грубая оценка

        for doc in docs:
            # ~4 символа на токен
            doc_tokens = len(doc['content']) // 4

            if current_tokens + doc_tokens > max_tokens:
                break

            source_name = Path(doc['source']).stem
            context_parts.append(f"[{source_name}]\n{doc['content']}")
            current_tokens += doc_tokens

        return "\n\n---\n\n".join(context_parts)


# Singleton instance
_rag = None

def get_rag() -> JunonaRAG:
    global _rag
    if _rag is None:
        _rag = JunonaRAG()
    return _rag


def init_and_index(background: bool = True):
    """Инициализировать RAG и запустить индексацию"""
    rag = get_rag()

    if background:
        import threading
        def _index():
            rag.index(force=False)
        thread = threading.Thread(target=_index, daemon=True)
        thread.start()
        print("🔄 Индексация запущена в фоне")
    else:
        rag.index(force=False)

    return rag


def reindex_if_needed():
    """Проверить и переиндексировать изменённые файлы (для watchdog)"""
    rag = get_rag()
    rag.index(force=False)


# CLI для первичной индексации
if __name__ == "__main__":
    import sys

    rag = get_rag()

    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        print("🔄 Полная переиндексация...")
        rag.index(force=True)
    else:
        print("🔄 Инкрементальная индексация...")
        rag.index(force=False)

    # Тест поиска
    print("\n📖 Тест поиска: 'что такое ACP'")
    results = rag.search("что такое ACP", n_results=3)
    for r in results:
        print(f"  [{r['score']:.2f}] {Path(r['source']).name}")
        print(f"       {r['content'][:100]}...")
