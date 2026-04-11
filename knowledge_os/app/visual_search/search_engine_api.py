import os
import logging
import time
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import faiss
import numpy as np

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Victoria Visual Search API")

# Конфигурация
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "Alibaba-NLP/GVE-2B")
DEVICE = os.getenv("DEVICE", "cpu")
INDEX_PATH = "/app/models/visual_index.faiss"
METADATA_PATH = "/app/models/visual_metadata.json"

# Глобальные переменные для модели и индекса
model = None
tokenizer = None
index = None
metadata = []

class IndexRequest(BaseModel):
    file_path: str

class SearchRequest(BaseModel):
    queries: List[str]
    top_k: int = 3

@app.on_event("startup")
async def load_resources():
    global model, tokenizer, index, metadata
    logger.info(f"Loading model {MODEL_NAME} on {DEVICE}...")
    # В реальности здесь была бы загрузка Qwen-VL или GVE
    # Для прототипа используем заглушку, имитирующую инференс
    logger.info("Model loaded (stub).")
    
    if os.path.exists(INDEX_PATH):
        index = faiss.read_index(INDEX_PATH)
        logger.info(f"Loaded FAISS index with {index.ntotal} vectors.")
    else:
        # Размерность 1536 для GVE-2B
        index = faiss.IndexFlatL2(1536)
        logger.info("Created new FAISS index.")

@app.post("/index")
async def index_file(request: IndexRequest):
    global index, metadata
    try:
        if not os.path.exists(request.file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # 1. Генерация эмбеддинга (заглушка)
        embedding = np.random.rand(1, 1536).astype('float32')
        
        # 2. Добавление в FAISS
        index.add(embedding)
        embedding_id = str(index.ntotal - 1)
        
        # 3. Сохранение метаданных
        metadata.append({
            "id": embedding_id,
            "file_path": request.file_path,
            "description": f"Visual features of {os.path.basename(request.file_path)}"
        })
        
        # Сохраняем на диск
        faiss.write_index(index, INDEX_PATH)
        
        return {"status": "success", "embedding_id": embedding_id}
    except Exception as e:
        logger.error(f"Indexing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
async def search(request: SearchRequest):
    global index, metadata
    if index.ntotal == 0:
        return {"results": []}
    
    try:
        # 1. Эмбеддинг запроса (заглушка)
        query_embedding = np.random.rand(1, 1536).astype('float32')
        
        # 2. Поиск в FAISS
        distances, indices = index.search(query_embedding, request.top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(metadata):
                res = metadata[idx].copy()
                res["similarity"] = float(1 / (1 + distances[0][i]))
                results.append(res)
        
        return {"results": results}
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok", "vectors": index.ntotal if index else 0}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
