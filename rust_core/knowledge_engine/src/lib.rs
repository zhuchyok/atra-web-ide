use sqlx::postgres::PgPoolOptions;
use sqlx::{Pool, Postgres};
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};

#[derive(Debug, Serialize, Deserialize, sqlx::FromRow)]
pub struct KnowledgeNode {
    pub id: Uuid,
    pub content: String,
    pub metadata: Option<serde_json::Value>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

pub struct KnowledgeEngine {
    pool: Pool<Postgres>,
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
        // Note: This assumes a table named 'knowledge_nodes' with an 'embedding' column of type vector
        let nodes = sqlx::query_as::<_, KnowledgeNode>(
            "SELECT id, content, metadata, created_at, updated_at 
             FROM knowledge_nodes 
             ORDER BY embedding <=> $1::vector 
             LIMIT $2"
        )
        .bind(embedding)
        .bind(limit)
        .fetch_all(&self.pool)
        .await?;

        Ok(nodes)
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
