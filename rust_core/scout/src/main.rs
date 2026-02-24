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
        model: "tinyllama:1.1b-chat".to_string(),
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

    // Extract all links to chapters
    let link_selector = Selector::parse("a").unwrap();
    let mut chapter_urls = Vec::new();
    for link in document.select(&link_selector) {
        if let Some(href) = link.value().attr("href") {
            if href.ends_with(".html") && !href.contains("http") {
                let full_url = format!("https://doc.rust-lang.org/book/{}", href);
                if !chapter_urls.contains(&full_url) {
                    chapter_urls.push(full_url);
                }
            }
        }
    }

    println!("📚 Found {} chapters to index.", chapter_urls.len());

    let mut total_count = 0;
    let p_selector = Selector::parse("p").unwrap();

    for url in chapter_urls {
        println!("📖 Indexing chapter: {}...", url);
        let chapter_res = match reqwest::get(&url).await {
            Ok(res) => match res.text().await {
                Ok(text) => text,
                Err(_) => continue,
            },
            Err(_) => continue,
        };

        let chapter_doc = Html::parse_document(&chapter_res);

        for element in chapter_doc.select(&p_selector) {
            let raw_content = element.text().collect::<Vec<_>>().join(" ").trim().to_string();

            if raw_content.is_empty() || raw_content.len() < 40 {
                continue;
            }

            let preview_len = raw_content.chars().count();
            let preview: String = raw_content.chars().take(std::cmp::min(preview_len, 50)).collect();
            println!("🧠 Distilling content: {}...", preview);
            let content = distill_content(&raw_content).await;

            let node_id = Uuid::new_v4();
            let domain_id = Uuid::parse_str("8a31f9dd-cd47-426c-bd1d-3ecb435fca8a").unwrap();
            let confidence_score = 0.9;
            let is_verified = true;
            let now = Utc::now();

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

            total_count += 1;
        }
    }

    println!("✅ Successfully indexed {} nodes from all Rust Book chapters.", total_count);

    Ok(())
}
