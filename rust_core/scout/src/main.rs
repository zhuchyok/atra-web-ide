use sqlx::postgres::PgPoolOptions;
use std::env;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    dotenv::dotenv().ok();
    let db_url = env::var("DATABASE_URL").unwrap_or_else(|_| "postgresql://admin:secret@localhost:5432/knowledge_os".to_string());
    
    println!("🚀 Scout-agent initializing connection to Knowledge OS...");
    
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&db_url).await?;

    println!("✅ Connected to database. Scout-agent ready for indexing.");
    
    // Basic test query
    let row: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM experts")
        .fetch_one(&pool)
        .await?;
        
    println!("📊 Current expert count in DB: {}", row.0);
    
    Ok(())
}
