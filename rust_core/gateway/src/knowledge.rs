use sqlx::postgres::PgPool;
use sqlx::Error;
use tracing::{info, error};

pub struct KnowledgeEngine {
    pool: PgPool,
}

impl KnowledgeEngine {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }

    pub async fn get_context(&self, query: &str) -> Result<String, Error> {
        info!("Searching knowledge for: {}", query);

        // Simple text search in knowledge_nodes
        // We assume knowledge_nodes table exists with 'content' column
        // This is a placeholder for more advanced GraphRAG/Vector search
        let rows: Vec<(String,)> = sqlx::query_as(
            "SELECT content FROM knowledge_nodes 
             WHERE content ILIKE $1 
             LIMIT 5"
        )
        .bind(format!("%{}%", query))
        .fetch_all(&self.pool)
        .await?;

        if rows.is_empty() {
            return Ok("No relevant knowledge found.".to_string());
        }

        let mut context = String::from("Relevant knowledge from Singularity 14.0 database:\n\n");
        for (i, row) in rows.iter().enumerate() {
            context.push_str(&format!("{}. {}\n", i + 1, row.0));
        }

        Ok(context)
    }
}
