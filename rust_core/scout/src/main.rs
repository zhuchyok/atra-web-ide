use sqlx::postgres::PgPoolOptions;
use std::env;
use scraper::{Html, Selector};
use uuid::Uuid;
use chrono::Utc;
use serde::{Deserialize, Serialize};

#[derive(Serialize)]
struct OllamaRequest {
    model: String,
    prompt: String,
    stream: bool,
}

#[derive(Deserialize)]
struct OllamaResponse {
    response: String,
}

async fn distill_content(text: &str) -> String {
    let client = reqwest::Client::new();
    let prompt = format!(
        "### ROLE: AI Secretary / Fact Extractor\n### TASK: Extract key facts and technical rules from the text below for a Rust expert.\n### TEXT:\n{}\n### FACTS:",
        text
    );

    let request_body = OllamaRequest {
        model: "phi3.5:3.8b".to_string(),
        prompt,
        stream: false,
    };

    match client
        .post("http://localhost:11434/api/generate")
        .json(&request_body)
        .send()
        .await
    {
        Ok(res) => {
            if res.status().is_success() {
                match res.json::<OllamaResponse>().await {
                    Ok(ollama_res) => ollama_res.response.trim().to_string(),
                    Err(_) => text.to_string(),
                }
            } else {
                text.to_string()
            }
        }
        Err(_) => text.to_string(),
    }
}

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
        let raw_content = element.text().collect::<Vec<_>>().join(" ").trim().to_string();
        
        if raw_content.is_empty() || raw_content.len() < 20 {
            continue;
        }

        println!("🧠 Distilling content: {}...", &raw_content[..std::cmp::min(raw_content.len(), 50)]);
        let content = distill_content(&raw_content).await;

        let node_id = Uuid::new_v4();
        let domain_id = "AI Research"; // or "Rust Documentation"
        let confidence_score = 0.9;
        let is_verified = true;
        let now = Utc::now();

        // Inserting into knowledge_nodes
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
