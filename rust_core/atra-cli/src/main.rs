use clap::{Parser, Subcommand};
use colored::*;
use dotenv::dotenv;
use serde::{Deserialize, Serialize};
use std::env;

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

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    dotenv().ok();

    let gateway_url = env::var("GATEWAY_URL").unwrap_or_else(|_| "http://localhost:8081".to_string());
    let victoria_url = env::var("VICTORIA_URL").unwrap_or_else(|_| "http://localhost:8010".to_string());

    let cli = Cli::parse();

    match &cli.command {
        Commands::Health => {
            println!("{}", "Checking system health...".cyan());

            // Check Gateway
            let client = reqwest::Client::new();
            match client.get(format!("{}/health", gateway_url)).send().await {
                Ok(res) if res.status().is_success() => {
                    println!("{} Gateway ({}): {}", "✔".green(), gateway_url, "Connected".green());
                }
                _ => {
                    println!("{} Gateway ({}): {}", "✘".red(), gateway_url, "Disconnected".red());
                }
            }

            // Check Victoria
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
            let client = reqwest::Client::new();
            let project_context = env::var("PROJECT_CONTEXT").unwrap_or_else(|_| "atra-web-ide".to_string());

            let request = ChatRequest {
                message: message.clone(),
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
    }

    Ok(())
}
