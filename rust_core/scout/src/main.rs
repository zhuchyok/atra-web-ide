use sqlx::postgres::PgPoolOptions;
use std::env;
use scraper::{Html, Selector};
use uuid::Uuid;
use chrono::Utc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    dotenv::dotenv().ok();
    let db_url = env::var("DATABASE_URL").unwrap_or_else(|_| "postgresql://admin:secret@localhost:5432/knowledge_os".to_string());
    
    println!("🚀 Scout-agent initializing connection to Knowledge OS...");
    
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&db_url).await?;

    println!("✅ Connected to database. Scout-agent ready for indexing.");
    
    let target_url = "https://doc.rust-lang.org/book/";
    println!("🔍 Fetching Rust documentation from {}...", target_url);
    
    let response = reqwest::get(target_url).await?.text().await?;
    let document = Html::parse_document(&response);
    let selector = Selector::parse("p").unwrap();
    
    let mut count = 0;
    for element in document.select(&selector) {
        let content = element.text().collect::<Vec<_>>().join(" ").trim().to_string();
        
        if content.is_empty() || content.len() < 20 {
            continue;
        }

        let node_id = Uuid::new_v4();
        let domain_id = "AI Research"; // or "Rust Documentation"
        let confidence_score = 0.9;
        let is_verified = true;
        let now = Utc::now();

        // Inserting into knowledge_nodes
        // Note: Adjust column names based on actual schema if needed
        sqlx::query(
            "INSERT INTO knowledge_nodes (id, content, domain_id, confidence_score, is_verified, created_at, updated_at) 
             VALUES ($1, $2, $3, $4, $5, $6, $7)"
        )
        .bind(node_id)
        .bind(&content)
        .bind(domain_id)
        .bind(confidence_score)
        .bind(is_verified)
        .bind(now)
        .bind(now)
        .execute(&pool)
        .await?;
        
        count += 1;
        if count >= 10 { break; } // Limit for basic implementation
    }
    
    println!("✅ Successfully indexed {} nodes from Rust documentation.", count);
    
    Ok(())
}
