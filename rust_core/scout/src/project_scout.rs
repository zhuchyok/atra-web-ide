use sqlx::postgres::PgPoolOptions;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use uuid::Uuid;
use chrono::Utc;
use serde::{Deserialize, Serialize};
use walkdir::WalkDir;

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
        "### ROLE: AI Architect / Code Auditor\n### TASK: Summarize the purpose and key components of this file for a knowledge base.\n### CONTENT:\n{}\n### SUMMARY:",
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
                    Err(_) => text.chars().take(500).collect(),
                }
            } else {
                text.chars().take(500).collect()
            }
        }
        Err(_) => text.chars().take(500).collect(),
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    dotenv::dotenv().ok();
    let db_url = env::var("DATABASE_URL").unwrap_or_else(|_| "postgresql://postgres:postgres@localhost:5432/knowledge_os".to_string());

    println!("🚀 Project Scout-agent starting...");

    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&db_url).await?;

    let project_root = Path::new("/Users/bikos/Documents/atra-web-ide");
    let folders_to_index = vec!["backend", "frontend", "rust_core", "knowledge_os"];

    let mut total_count = 0;
    let domain_id = Uuid::parse_str("8a31f9dd-cd47-426c-bd1d-3ecb435fca8a").unwrap(); // General Knowledge domain

    for folder in folders_to_index {
        let folder_path = project_root.join(folder);
        println!("📂 Scanning folder: {:?}...", folder_path);

        for entry in WalkDir::new(folder_path)
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().is_file())
        {
            let path = entry.path();
            let extension = path.extension().and_then(|s| s.to_str()).unwrap_or("");

            // Filter relevant files
            if !["rs", "py", "ts", "js", "svelte", "toml", "json", "md", "sql"].contains(&extension) {
                continue;
            }

            // Skip node_modules, target, .venv, etc.
            let path_str = path.to_string_lossy();
            if path_str.contains("/node_modules/") || path_str.contains("/target/") || path_str.contains("/.venv/") || path_str.contains("/.git/") {
                continue;
            }

            println!("📄 Indexing file: {:?}", path);
            let content = match fs::read_to_string(path) {
                Ok(c) => c,
                Err(_) => continue,
            };

            if content.trim().is_empty() {
                continue;
            }

            let file_info = format!("File: {:?}\n\nContent:\n{}", path.strip_prefix(project_root).unwrap_or(path), content);
            let distilled = distill_content(&file_info).await;

            let node_id = Uuid::new_v4();
            let now = Utc::now();

            sqlx::query(
                "INSERT INTO knowledge_nodes (id, content, domain_id, confidence_score, is_verified, created_at, updated_at)
                 VALUES ($1, $2, $3, $4, $5, $6, $7)"
            )
            .bind(node_id)
            .bind(&format!("PROJECT_FILE: {:?}\n\n{}", path.strip_prefix(project_root).unwrap_or(path), distilled))
            .bind(domain_id)
            .bind(0.95f64)
            .bind(true)
            .bind(now.naive_utc())
            .bind(now)
            .execute(&pool)
            .await?;

            total_count += 1;
        }
    }

    println!("✅ Successfully indexed {} project files into Knowledge OS.", total_count);

    Ok(())
}
