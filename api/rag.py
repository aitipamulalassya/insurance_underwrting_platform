"""Gemini-embedding + PostgreSQL/pgvector retrieval and grounded answer generation."""
from __future__ import annotations
import json, os, re, urllib.request, urllib.error
from typing import Any
from fastapi import HTTPException

EMBED_MODEL = os.getenv('GEMINI_EMBEDDING_MODEL', 'gemini-embedding-001')
CHAT_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
API_KEY = os.getenv('GEMINI_API_KEY', '').strip()
DIMENSIONS = 768

def _gemini(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not API_KEY:
        raise HTTPException(503, 'RAG requires GEMINI_API_KEY. Add it to your local .env and restart the API.')
    # Gemini REST method is part of the model path, not a query parameter.
    model, action = method.split('|', 1)
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:{action}?key={API_KEY}'
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors='replace')[:1200]
        raise HTTPException(502, f'Gemini API request failed ({exc.code}): {detail}')
    except Exception as exc:
        raise HTTPException(502, f'Could not reach Gemini API: {exc}')

def embed(text: str) -> list[float]:
    result = _gemini(f'{EMBED_MODEL}|embedContent', {'model':f'models/{EMBED_MODEL}','content':{'parts':[{'text':text[:8000]}]},'outputDimensionality':DIMENSIONS})
    values = result.get('embedding', {}).get('values')
    if not values or len(values) != DIMENSIONS:
        raise HTTPException(502, 'Embedding service returned an unexpected vector dimension.')
    return values

def generate_answer(question: str, sources: list[dict[str, Any]]) -> str:
    context = '\n\n'.join(f"[S{i+1}] {s['title']} (document: {s.get('document_id') or 'configured guidance'}, chunk {s.get('chunk_index', 0)}):\n{s['content']}" for i,s in enumerate(sources))
    prompt = f'''You are an insurance underwriting knowledge assistant. Answer only from the supplied context. Do not invent policy rules, coverage, rates, or facts. If context is insufficient, say so and recommend an authorized reviewer. Cite every material claim using source markers such as [S1] and [S2]. Do not make or imply underwriting approval/decline decisions. Distinguish configured prototype assumptions from real insurance policy.\n\nQUESTION:\n{question}\n\nRETRIEVED CONTEXT:\n{context}\n\nGive a concise, practical answer with source markers.'''
    result = _gemini(f'{CHAT_MODEL}|generateContent', {'contents':[{'role':'user','parts':[{'text':prompt}]}], 'generationConfig':{'temperature':0.2,'maxOutputTokens':900}})
    return ''.join(p.get('text','') for p in result.get('candidates',[{}])[0].get('content',{}).get('parts',[])).strip()

def chunks(text: str, size: int = 1100, overlap: int = 160) -> list[str]:
    clean = re.sub(r'\s+', ' ', text).strip()
    if not clean: return []
    out=[]; start=0
    while start < len(clean):
        end=min(len(clean), start+size)
        if end < len(clean):
            boundary=clean.rfind(' ', start+size//2, end)
            if boundary > start: end=boundary
        piece=clean[start:end].strip()
        if piece: out.append(piece)
        if end >= len(clean): break
        start=max(start+1,end-overlap)
    return out

def ensure_rag_schema() -> None:
    from api.database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('CREATE EXTENSION IF NOT EXISTS vector')
            cur.execute(f'''CREATE TABLE IF NOT EXISTS underwriting_document_chunks (
                chunk_id BIGSERIAL PRIMARY KEY,
                document_id UUID REFERENCES underwriting_documents(document_id) ON DELETE CASCADE,
                source_title TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding vector({DIMENSIONS}) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(document_id, chunk_index)
            )''')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_underwriting_chunks_document ON underwriting_document_chunks(document_id)')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_underwriting_chunks_embedding ON underwriting_document_chunks USING hnsw (embedding vector_cosine_ops)')

def index_document(document_id: str, title: str, text: str) -> int:
    from api.database import get_connection
    ensure_rag_schema()
    pieces=chunks(text)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM underwriting_document_chunks WHERE document_id=%s',(document_id,))
            for i, piece in enumerate(pieces):
                vector=embed(piece)
                cur.execute('INSERT INTO underwriting_document_chunks(document_id,source_title,chunk_index,content,embedding) VALUES(%s,%s,%s,%s,%s::vector)',(document_id,title,i,piece,'['+','.join(map(str,vector))+']'))
    return len(pieces)

def index_guidelines(guidelines: list[tuple[str,str,str]]) -> None:
    from api.database import get_connection
    ensure_rag_schema()
    with get_connection() as conn:
        with conn.cursor() as cur:
            for title, content, category in guidelines:
                source=f'{title} — {category}'
                cur.execute('SELECT 1 FROM underwriting_document_chunks WHERE document_id IS NULL AND source_title=%s LIMIT 1',(source,))
                if cur.fetchone(): continue
                for i,piece in enumerate(chunks(content)):
                    vector=embed(piece)
                    cur.execute('INSERT INTO underwriting_document_chunks(document_id,source_title,chunk_index,content,embedding) VALUES(NULL,%s,%s,%s,%s::vector)',(source,i,piece,'['+','.join(map(str,vector))+']'))

def retrieve(question: str, limit: int = 5) -> list[dict[str, Any]]:
    from api.database import get_connection
    ensure_rag_schema()
    vector=embed(question)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT chunk_id, document_id::text AS document_id, source_title AS title, chunk_index, content,
                1-(embedding <=> %s::vector) AS similarity
                FROM underwriting_document_chunks ORDER BY embedding <=> %s::vector LIMIT %s''',
                ('['+','.join(map(str,vector))+']','['+','.join(map(str,vector))+']',limit))
            rows=cur.fetchall()
    return [r for r in rows if float(r['similarity']) >= 0.35]
