import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from typing import List

app = FastAPI(title="Knowledge OS VectorCore")

# Initialize model once globally
MODEL_NAME = "all-MiniLM-L6-v2"
print(f"Loading SentenceTransformer model: {MODEL_NAME}...")
model = SentenceTransformer(MODEL_NAME)
print("Model loaded successfully.")

class TextRequest(BaseModel):
    text: str

class BatchRequest(BaseModel):
    texts: List[str]

class VectorResponse(BaseModel):
    embedding: List[float]

class BatchResponse(BaseModel):
    embeddings: List[List[float]]

@app.get("/health")
async def health():
    return {"status": "healthy", "model": MODEL_NAME}

@app.post("/encode", response_model=VectorResponse)
async def encode(request: TextRequest):
    try:
        embedding = model.encode(request.text).tolist()
        return {"embedding": embedding}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/encode_batch", response_model=BatchResponse)
async def encode_batch(request: BatchRequest):
    try:
        embeddings = model.encode(request.texts).tolist()
        return {"embeddings": embeddings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)

