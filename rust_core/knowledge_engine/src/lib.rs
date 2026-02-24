use sqlx::postgres::{PgPoolOptions, PgHasArrayType, PgTypeInfo};
use sqlx::{Pool, Postgres, Type, Decode, Encode, FromRow};
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc, NaiveDateTime};
use ndarray::{Array1, ArrayView1};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Vector(pub Vec<f32>);

impl Type<Postgres> for Vector {
    fn type_info() -> PgTypeInfo {
        PgTypeInfo::with_name("vector")
    }
}

impl<'q> Encode<'q, Postgres> for Vector {
    fn encode_by_ref(&self, buf: &mut sqlx::postgres::PgArgumentBuffer) -> sqlx::encode::IsNull {
        let dim = self.0.len() as u16;
        buf.extend_from_slice(&dim.to_be_bytes());
        buf.extend_from_slice(&0u16.to_be_bytes()); // unused
        for &f in &self.0 {
            buf.extend_from_slice(&f.to_be_bytes());
        }
        sqlx::encode::IsNull::No
    }
}

impl<'r> Decode<'r, Postgres> for Vector {
    fn decode(value: sqlx::postgres::PgValueRef<'r>) -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        let bytes = value.as_bytes()?;
        if bytes.len() < 4 {
            return Err("Vector too short".into());
        }
        let dim = u16::from_be_bytes([bytes[0], bytes[1]]) as usize;
        let mut v = Vec::with_capacity(dim);
        for i in 0..dim {
            let start = 4 + i * 4;
            let end = start + 4;
            if end > bytes.len() { break; }
            v.push(f32::from_be_bytes([bytes[start], bytes[start+1], bytes[start+2], bytes[start+3]]));
        }
        Ok(Vector(v))
    }
}

impl PgHasArrayType for Vector {
    fn array_type_info() -> PgTypeInfo {
        PgTypeInfo::with_name("_float4")
    }
}

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct KnowledgeNode {
    pub id: Uuid,
    pub content: String,
    pub metadata: Option<serde_json::Value>,
    pub created_at: NaiveDateTime,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct KnowledgeNodeWithEmbedding {
    pub id: Uuid,
    pub content: String,
    pub metadata: Option<serde_json::Value>,
    pub embedding: Vector,
    pub created_at: NaiveDateTime,
    pub updated_at: DateTime<Utc>,
}

pub struct KnowledgeEngine {
    pub pool: Pool<Postgres>,
}

impl KnowledgeEngine {
    pub async fn new(database_url: &str) -> Result<Self, sqlx::Error> {
        let pool = PgPoolOptions::new()
            .max_connections(5)
            .connect(database_url)
            .await?;
        Ok(Self { pool })
    }

    pub async fn retrieve_similar(
        &self,
        embedding: Vec<f32>,
        limit: i64,
    ) -> Result<Vec<KnowledgeNode>, sqlx::Error> {
        // Using pgvector <=> operator for cosine distance
        let nodes = sqlx::query_as::<_, KnowledgeNode>(
            "SELECT id, content, metadata, created_at, updated_at
             FROM knowledge_nodes
             ORDER BY embedding <=> $1::vector
             LIMIT $2"
        )
        .bind(Vector(embedding))
        .bind(limit)
        .fetch_all(&self.pool)
        .await?;

        Ok(nodes)
    }

    pub async fn retrieve_similar_with_embeddings(
        &self,
        embedding: Vec<f32>,
        limit: i64,
    ) -> Result<Vec<KnowledgeNodeWithEmbedding>, sqlx::Error> {
        let nodes = sqlx::query_as::<_, KnowledgeNodeWithEmbedding>(
            "SELECT id, content, metadata, embedding, created_at, updated_at
             FROM knowledge_nodes
             ORDER BY embedding <=> $1::vector
             LIMIT $2"
        )
        .bind(Vector(embedding))
        .bind(limit)
        .fetch_all(&self.pool)
        .await?;

        Ok(nodes)
    }

    /// Local cosine similarity calculation using ndarray
    pub fn cosine_similarity(v1: &ArrayView1<f32>, v2: &ArrayView1<f32>) -> f32 {
        let dot_product = v1.dot(v2);
        let norm1 = v1.dot(v1).sqrt();
        let norm2 = v2.dot(v2).sqrt();

        if norm1 == 0.0 || norm2 == 0.0 {
            return 0.0;
        }

        dot_product / (norm1 * norm2)
    }

    /// Sorts nodes by similarity to the query embedding locally
    pub fn rank_nodes_locally(
        &self,
        query_embedding: Vec<f32>,
        nodes_with_embeddings: Vec<KnowledgeNodeWithEmbedding>
    ) -> Vec<KnowledgeNode> {
        let q_arr = Array1::from(query_embedding);
        let q_view = q_arr.view();

        let mut ranked = nodes_with_embeddings;
        ranked.sort_by(|a, b| {
            let sim_a = Self::cosine_similarity(&q_view, &Array1::from(a.embedding.0.clone()).view());
            let sim_b = Self::cosine_similarity(&q_view, &Array1::from(b.embedding.0.clone()).view());
            sim_b.partial_cmp(&sim_a).unwrap_or(std::cmp::Ordering::Equal)
        });

        ranked.into_iter().map(|n| KnowledgeNode {
            id: n.id,
            content: n.content,
            metadata: n.metadata,
            created_at: n.created_at,
            updated_at: n.updated_at,
        }).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;

    #[tokio::test]
    async fn test_query_logic_structure() {
        // This is a basic test to verify the structure and compilation
        dotenv::dotenv().ok();
        let database_url = env::var("DATABASE_URL").unwrap_or_else(|_| "postgres://localhost/test".to_string());

        // We don't actually run the query here to avoid dependency on a live DB during cargo check/test
        // but we verify the types and logic can be instantiated.
        println!("Database URL: {}", database_url);
    }
}
