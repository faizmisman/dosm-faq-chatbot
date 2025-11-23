-- Migration: Add pgvector extension and embeddings table
-- This replaces local Chroma artifacts with scalable PostgreSQL storage

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Embeddings table for RAG chunks
CREATE TABLE IF NOT EXISTS embeddings (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    embedding VECTOR(384),  -- MiniLM-L6-v2 produces 384-dimensional embeddings
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for fast vector similarity search (HNSW for production, IVFFlat for dev)
-- Using cosine distance (1 - <=> is cosine similarity)
CREATE INDEX IF NOT EXISTS embeddings_embedding_idx 
ON embeddings 
USING hnsw (embedding vector_cosine_ops);

-- GIN index for metadata queries
CREATE INDEX IF NOT EXISTS embeddings_metadata_idx 
ON embeddings 
USING GIN (metadata);

-- Function to search similar embeddings
CREATE OR REPLACE FUNCTION search_embeddings(
    query_embedding VECTOR(384),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id TEXT,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        embeddings.id,
        embeddings.content,
        embeddings.metadata,
        1 - (embeddings.embedding <=> query_embedding) AS similarity
    FROM embeddings
    WHERE 1 - (embeddings.embedding <=> query_embedding) > match_threshold
    ORDER BY embeddings.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Upsert helper function
CREATE OR REPLACE FUNCTION upsert_embedding(
    p_id TEXT,
    p_content TEXT,
    p_embedding VECTOR(384),
    p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO embeddings (id, content, embedding, metadata)
    VALUES (p_id, p_content, p_embedding, p_metadata)
    ON CONFLICT (id) 
    DO UPDATE SET
        content = EXCLUDED.content,
        embedding = EXCLUDED.embedding,
        metadata = EXCLUDED.metadata,
        created_at = NOW();
END;
$$;

-- Add indexes for common metadata queries
CREATE INDEX IF NOT EXISTS embeddings_start_row_idx 
ON embeddings ((metadata->>'start_row'));

CREATE INDEX IF NOT EXISTS embeddings_end_row_idx 
ON embeddings ((metadata->>'end_row'));

-- Grant permissions (adjust role as needed)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON embeddings TO dosm_app_user;
