use clap::{Parser, Subcommand};
use colored::*;
use dotenv::dotenv;
use serde::{Deserialize, Serialize};
use std::env;
use std::fs;
use std::io::{self, Write};
use std::path::Path;
use ignore::WalkBuilder;

#[derive(Parser)]
#[command(name = "atra")]
#[command(about = "Atra CLI - Autonomous Cursor Alternative", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Checks connection to Rust API Gateway and Victoria
    Health,
    /// Sends a message to Victoria through the Gateway
    Chat {
        /// The message to send
        message: String,
    },
    /// Applies SEARCH/REPLACE blocks to a file
    Apply {
        /// Path to the file to patch
        file_path: String,
        /// The patch string containing SEARCH/REPLACE blocks
        patch: String,
    },
}

#[derive(Serialize, Deserialize, Debug)]
struct ChatRequest {
    message: String,
    project_context: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct ChatResponse {
    response: String,
}

#[derive(Debug)]
struct PatchBlock {
    search: String,
    replace: String,
}

fn parse_patch_blocks(text: &str) -> Vec<PatchBlock> {
    let mut blocks = Vec::new();
    let mut current_pos = 0;

    while let Some(rel_search_start) = text[current_pos..].find("<<<<<<< SEARCH") {
        let search_start = current_pos + rel_search_start + 14; // skip "<<<<<<< SEARCH"
        if let Some(rel_search_end) = text[search_start..].find("=======") {
            let search_end = search_start + rel_search_end;
            let search_content = text[search_start..search_end].trim_matches('\n');

            let replace_start = search_end + 7; // skip "======="
            if let Some(rel_replace_end) = text[replace_start..].find(">>>>>>> REPLACE") {
                let replace_end = replace_start + rel_replace_end;
                let replace_content = text[replace_start..replace_end].trim_matches('\n');

                blocks.push(PatchBlock {
                    search: search_content.to_string(),
                    replace: replace_content.to_string(),
                });
                current_pos = replace_end + 15; // skip ">>>>>>> REPLACE"
            } else {
                current_pos = search_end + 7;
            }
        } else {
            current_pos = search_start;
        }
    }
    blocks
}

fn apply_patches(file_path: &str, patches: &[PatchBlock]) -> Result<(), Box<dyn std::error::Error>> {
    let path = Path::new(file_path);
    if !path.exists() {
        return Err(format!("File not found: {}", file_path).into());
    }

    let mut content = fs::read_to_string(path)?;
    let mut applied_count = 0;

    for patch in patches {
        if patch.search.is_empty() {
            continue;
        }

        if let Some(pos) = content.find(&patch.search) {
            content.replace_range(pos..pos + patch.search.len(), &patch.replace);
            applied_count += 1;
        } else {
            println!("{} SEARCH block not found in {}:", "⚠".yellow(), file_path);
            println!("---\n{}\n---", patch.search.dimmed());
            return Err(format!("SEARCH block not found in {}", file_path).into());
        }
    }

    fs::write(path, content)?;
    println!("{} Applied {} patches to {}", "✔".green(), applied_count, file_path);
    Ok(())
}

fn gather_context(message: &str) -> String {
    let mut context = String::new();
    let mut included_files = Vec::new();

    // Find all words starting with @
    for word in message.split_whitespace() {
        if word.starts_with('@') {
            let file_ref = &word[1..];
            let path = Path::new(file_ref);

            if path.exists() && path.is_file() {
                if let Ok(content) = fs::read_to_string(path) {
                    context.push_str(&format!("FILE: {}\n---\n{}\n---\n\n", file_ref, content));
                    included_files.push(file_ref);
                }
            } else {
                // If not a direct path, try searching with ignore crate (respecting .gitignore)
                let mut found = false;
                for result in WalkBuilder::new(".").build() {
                    if let Ok(entry) = result {
                        if entry.file_type().map(|ft| ft.is_file()).unwrap_or(false) {
                            if entry.path().to_string_lossy().ends_with(file_ref) {
                                if let Ok(content) = fs::read_to_string(entry.path()) {
                                    let path_str = entry.path().to_string_lossy().to_string();
                                    context.push_str(&format!("FILE: {}\n---\n{}\n---\n\n", path_str, content));
                                    included_files.push(path_str.leak()); // leak for simplicity in this CLI
                                    found = true;
                                    break;
                                }
                            }
                        }
                    }
                }
                if !found {
                    println!("{} Warning: File not found: {}", "⚠".yellow(), file_ref);
                }
            }
        }
    }

    for file in included_files {
        println!("{} Included context from: {}", "📎".cyan(), file);
    }

    context
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    dotenv().ok();

    let gateway_url = env::var("GATEWAY_URL").unwrap_or_else(|_| "http://localhost:8081".to_string());
    let victoria_url = env::var("VICTORIA_URL").unwrap_or_else(|_| "http://localhost:8010".to_string());

    let cli = Cli::parse();

    match &cli.command {
        Commands::Health => {
            println!("{}", "Checking system health...".cyan());

            let client = reqwest::Client::new();
            match client.get(format!("{}/health", gateway_url)).send().await {
                Ok(res) if res.status().is_success() => {
                    println!("{} Gateway ({}): {}", "✔".green(), gateway_url, "Connected".green());
                }
                _ => {
                    println!("{} Gateway ({}): {}", "✘".red(), gateway_url, "Disconnected".red());
                }
            }

            match client.get(format!("{}/health", victoria_url)).send().await {
                Ok(res) if res.status().is_success() => {
                    println!("{} Victoria ({}): {}", "✔".green(), victoria_url, "Connected".green());
                }
                _ => {
                    println!("{} Victoria ({}): {}", "✘".red(), victoria_url, "Disconnected".red());
                }
            }
        }
        Commands::Chat { message } => {
            let context = gather_context(message);
            let full_message = if context.is_empty() {
                message.clone()
            } else {
                format!("{}\n{}", context, message)
            };

            let client = reqwest::Client::new();
            let project_context = env::var("PROJECT_CONTEXT").unwrap_or_else(|_| "atra-web-ide".to_string());

            let request = ChatRequest {
                message: full_message,
                project_context,
            };

            println!("{}", "Sending message to Victoria...".cyan());

            match client
                .post(format!("{}/api/chat", gateway_url))
                .json(&request)
                .send()
                .await
            {
                Ok(res) if res.status().is_success() => {
                    let chat_res: ChatResponse = res.json().await?;
                    println!("\n{}", "Victoria:".bright_magenta().bold());
                    println!("{}", chat_res.response);

                    let patches = parse_patch_blocks(&chat_res.response);
                    if !patches.is_empty() {
                        println!("\n{}", "Detected smart-patch blocks. Apply them?".yellow().bold());
                        print!("Enter file path (or leave empty to skip): ");
                        io::stdout().flush()?;
                        
                        let mut input = String::new();
                        io::stdin().read_line(&mut input)?;
                        let file_path = input.trim();

                        if !file_path.is_empty() {
                            if let Err(e) = apply_patches(file_path, &patches) {
                                println!("{} Error applying patches: {}", "✘".red(), e);
                            }
                        }
                    }
                }
                Ok(res) => {
                    let status = res.status();
                    let text = res.text().await.unwrap_or_default();
                    println!("{} Error: {} - {}", "✘".red(), status, text);
                }
                Err(e) => {
                    println!("{} Connection error: {}", "✘".red(), e);
                }
            }
        }
        Commands::Apply { file_path, patch } => {
            let patches = parse_patch_blocks(patch);
            if patches.is_empty() {
                println!("{} No SEARCH/REPLACE blocks found in the patch string.", "✘".red());
                return Ok(());
            }
            apply_patches(file_path, &patches)?;
        }
    }

    Ok(())
}
