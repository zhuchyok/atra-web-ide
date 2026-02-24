use clap::{Parser, Subcommand, ValueHint, CommandFactory};
use clap::builder::styling::{AnsiColor, Styles};
use clap_complete::{generate, Shell};
use colored::*;
use dotenv::dotenv;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::env;
use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use ignore::WalkBuilder;

// ATRA branded color scheme for help output
const ATRA_STYLES: Styles = Styles::styled()
    .header(AnsiColor::Cyan.on_default().bold())
    .usage(AnsiColor::Magenta.on_default().bold())
    .literal(AnsiColor::Green.on_default())
    .placeholder(AnsiColor::Yellow.on_default())
    .error(AnsiColor::Red.on_default().bold());

#[derive(Parser)]
#[command(name = "atra")]
#[command(about = "Atra CLI - Autonomous Cursor Alternative", long_about = None)]
#[command(styles = ATRA_STYLES)]
struct Cli {
    /// Generate shell completions
    #[arg(long = "generate", value_enum)]
    generator: Option<Shell>,

    /// Config file path
    #[arg(short, long, value_hint = ValueHint::FilePath, global = true)]
    config: Option<PathBuf>,

    #[command(subcommand)]
    command: Option<Commands>,
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
    /// Requests a plan from Victoria
    Plan {
        /// The goal to plan for
        goal: String,
    },
    /// Shows system metrics and health
    Status,
    /// Triggers data retention cleanup
    Cleanup {
        /// Dry run mode (default: true)
        #[arg(long, default_value_t = true)]
        dry_run: bool,
        /// Tables to clean (comma-separated)
        #[arg(long)]
        tables: Option<String>,
    },
    /// Describes an image using Vision
    Describe {
        /// Path to the image file
        #[arg(value_hint = ValueHint::FilePath)]
        image_path: PathBuf,
        /// Optional prompt for description
        #[arg(long)]
        prompt: Option<String>,
    },
    /// Applies SEARCH/REPLACE blocks to a file
    Apply {
        /// Path to the file to patch
        #[arg(value_hint = ValueHint::FilePath)]
        file_path: PathBuf,
        /// The patch string containing SEARCH/REPLACE blocks
        patch: String,
    },
    /// Git: status, diff, log, branch, commit (via Gateway)
    Git {
        #[command(subcommand)]
        subcommand: GitCommand,
    },
}

#[derive(Subcommand)]
enum GitCommand {
    /// Show working tree status
    Status,
    /// Show diff (optional path)
    Diff {
        #[arg(short, long)]
        path: Option<String>,
    },
    /// Show commit log
    Log {
        #[arg(short, long, default_value_t = 20)]
        n: u32,
    },
    /// Show current branch and list
    Branch,
    /// Commit staged or all changes
    Commit {
        /// Commit message
        #[arg(short, long)]
        message: String,
        /// Paths to add (default: all)
        #[arg(short, long)]
        paths: Option<Vec<String>>,
    },
}

/// Reserved for typed API response (gateway /v1/chat/completions).
#[allow(dead_code)]
#[derive(Serialize, Deserialize, Debug)]
struct ChatRequest {
    message: String,
    project_context: String,
}

/// Reserved for typed API response.
#[allow(dead_code)]
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

/// Project root: ATRA_PROJECT_ROOT env, or directory containing .git, or current dir.
fn project_root() -> std::path::PathBuf {
    if let Ok(root) = env::var("ATRA_PROJECT_ROOT") {
        return std::path::PathBuf::from(root);
    }
    if let Ok(cwd) = env::current_dir() {
        let mut dir = cwd.as_path();
        loop {
            if dir.join(".git").exists() {
                return dir.to_path_buf();
            }
            if let Some(parent) = dir.parent() {
                dir = parent;
            } else {
                break;
            }
        }
        return cwd;
    }
    std::path::PathBuf::from(".")
}

fn gather_context(message: &str) -> String {
    let mut context = String::new();
    let mut included_files: Vec<String> = Vec::new();
    let root = project_root();

    for word in message.split_whitespace() {
        if word.starts_with('@') {
            let file_ref = word[1..].trim_matches('"');
            let path = Path::new(file_ref);

            let (content_path, display_path): (std::path::PathBuf, String) = if path.exists() && path.is_file() {
                (path.to_path_buf(), file_ref.to_string())
            } else if root.join(file_ref).exists() && root.join(file_ref).is_file() {
                let p = root.join(file_ref);
                (p.clone(), p.to_string_lossy().to_string())
            } else {
                let mut found_path: Option<(std::path::PathBuf, String)> = None;
                for result in WalkBuilder::new(&root).build() {
                    if let Ok(entry) = result {
                        if entry.file_type().map(|ft| ft.is_file()).unwrap_or(false) {
                            let lossy = entry.path().to_string_lossy();
                            if lossy.ends_with(file_ref) || entry.path().ends_with(file_ref) {
                                if let Ok(_content) = fs::read_to_string(entry.path()) {
                                    let path_str = entry.path().to_string_lossy().to_string();
                                    found_path = Some((entry.path().to_path_buf(), path_str));
                                    break;
                                }
                            }
                        }
                    }
                }
                match found_path {
                    Some((p, s)) => (p, s),
                    None => {
                        println!("{} Warning: File not found: {}", "⚠".yellow(), file_ref);
                        continue;
                    }
                }
            };

            if let Ok(content) = fs::read_to_string(&content_path) {
                context.push_str(&format!("FILE: {}\n---\n{}\n---\n\n", display_path, content));
                included_files.push(display_path);
            }
        }
    }

    for file in &included_files {
        println!("{} Included context from: {}", "📎".cyan(), file);
    }

    context
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    dotenv().ok();

    let cli = Cli::parse();

    // Handle shell completion generation
    if let Some(generator) = cli.generator {
        let mut cmd = Cli::command();
        eprintln!("Generating completion file for {:?}...", generator);
        generate(generator, &mut cmd, "atra", &mut io::stdout());
        return Ok(());
    }

    // Load config file if specified or from default location
    if let Some(config_path) = cli.config.or_else(|| {
        let home = env::var("HOME").ok()?;
        let path = PathBuf::from(home).join(".config/atra/config.toml");
        if path.exists() { Some(path) } else { None }
    }) {
        if let Ok(content) = fs::read_to_string(&config_path) {
            if let Ok(config) = toml::from_str::<toml::Value>(&content) {
                if let Some(v) = config.get("gateway_url").and_then(|v| v.as_str()) {
                    env::set_var("GATEWAY_URL", v);
                }
                if let Some(v) = config.get("victoria_url").and_then(|v| v.as_str()) {
                    env::set_var("VICTORIA_URL", v);
                }
                if let Some(v) = config.get("project_context").and_then(|v| v.as_str()) {
                    env::set_var("PROJECT_CONTEXT", v);
                }
            }
        }
    }

    let command = cli.command.unwrap_or_else(|| {
        eprintln!("{}", "Error: No command specified. Use --help for usage.".red());
        std::process::exit(1);
    });

    let gateway_url = env::var("GATEWAY_URL").unwrap_or_else(|_| "http://localhost:8081".to_string());
    let victoria_url = env::var("VICTORIA_URL").unwrap_or_else(|_| "http://localhost:8010".to_string());

    match &command {
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

            let request = json!({
                "model": "victoria-wisdom-30b:latest",
                "messages": [
                    {
                        "role": "user",
                        "content": full_message
                    }
                ],
                "use_rag": true,
                "stream": false,
                "project_context": project_context
            });

            println!("{}", "Sending message to Victoria...".cyan());

            match client
                .post(format!("{}/v1/chat/completions", gateway_url))
                .json(&request)
                .send()
                .await
            {
                Ok(res) if res.status().is_success() => {
                    let chat_res: serde_json::Value = res.json().await?;
                    let response_text = chat_res["choices"][0]["message"]["content"]
                        .as_str()
                        .unwrap_or("No response content");

                    println!("\n{}", "Victoria:".bright_magenta().bold());
                    println!("{}", response_text);

                    let patches = parse_patch_blocks(response_text);
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
        Commands::Plan { goal } => {
            let context = gather_context(goal);
            let full_goal = if context.is_empty() {
                goal.clone()
            } else {
                format!("{}\n{}", context, goal)
            };

            let client = reqwest::Client::new();
            let project_context = env::var("PROJECT_CONTEXT").unwrap_or_else(|_| "atra-web-ide".to_string());

            let request = json!({
                "goal": full_goal,
                "project_context": project_context
            });

            println!("{}", "Requesting plan from Victoria...".cyan());

            match client
                .post(format!("{}/api/chat/plan", gateway_url))
                .json(&request)
                .send()
                .await
            {
                Ok(res) if res.status().is_success() => {
                    let plan_res: serde_json::Value = res.json().await?;
                    let plan_text = plan_res["plan"]
                        .as_str()
                        .or_else(|| plan_res["result"].as_str())
                        .unwrap_or("No plan content");

                    println!("\n{}", "Victoria's Plan:".bright_magenta().bold());
                    println!("{}", plan_text);
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
        Commands::Status => {
            let client = reqwest::Client::new();
            let gateway_url = env::var("GATEWAY_URL").unwrap_or_else(|_| "http://localhost:8081".to_string());

            println!("{}", "Fetching system status...".cyan());

            match client.get(format!("{}/api/system-metrics", gateway_url)).send().await {
                Ok(res) if res.status().is_success() => {
                    let metrics: serde_json::Value = res.json().await?;
                    println!("\n{}", "System Status:".bright_magenta().bold());

                    if let Some(cpu) = metrics["cpu"].as_object() {
                        println!("{} CPU: {}% ({} cores)", "💻".cyan(), cpu["percent"], cpu["count"]);
                    }
                    if let Some(ram) = metrics["ram"].as_object() {
                        println!("{} RAM: {}% ({} GB / {} GB used)", "🧠".cyan(), ram["percent"], ram["used_gb"], ram["total_gb"]);
                    }
                    if let Some(disk) = metrics["disk"].as_object() {
                        println!("{} Disk: {}% ({} GB / {} GB used)", "💾".cyan(), disk["percent"], disk["used_gb"], disk["total_gb"]);
                    }
                    if let Some(db) = metrics["db"].as_object() {
                        println!("{} Knowledge Base: {} experts, {} nodes (Status: {})",
                            "📚".cyan(), db["experts"], db["knowledge_nodes"],
                            if db["healthy"].as_bool().unwrap_or(false) { "Healthy".green() } else { "Warning".yellow() });
                    }
                }
                _ => println!("{} Failed to fetch system metrics", "✘".red()),
            }
        }
        Commands::Cleanup { dry_run, tables } => {
            let client = reqwest::Client::new();
            let gateway_url = env::var("GATEWAY_URL").unwrap_or_else(|_| "http://localhost:8081".to_string());
            let payload = json!({ "dry_run": dry_run, "tables": tables });

            println!("{}", "Requesting data retention cleanup...".cyan());

            match client.post(format!("{}/api/data-retention/cleanup", gateway_url))
                .json(&payload)
                .send()
                .await
            {
                Ok(res) if res.status().is_success() => {
                    let result: serde_json::Value = res.json().await?;
                    println!("\n{}", "Cleanup Status:".bright_yellow().bold());
                    println!("  Status:         {}", result["status"]);
                    println!("  Timestamp:      {}", result["timestamp"]);
                    println!("  Total Affected: {}", result["total_deleted"]);
                    if let Some(results) = result["results"].as_array() {
                        for r in results {
                            let table = r["table"].as_str().unwrap_or("unknown");
                            let deleted = r["deleted"].as_i64().unwrap_or(0);
                            let error = r["error"].as_str();
                            if let Some(err) = error {
                                println!("  - {}: {} (Error: {})", table, deleted, err.red());
                            } else {
                                println!("  - {}: {}", table, deleted);
                            }
                        }
                    }
                }
                Ok(res) => println!("{} Error: {} - {}", "✘".red(), res.status(), res.text().await.unwrap_or_default()),
                Err(e) => println!("{} Connection error: {}", "✘".red(), e),
            }
        }
        Commands::Describe { image_path, prompt } => {
            let client = reqwest::Client::new();
            let gateway_url = env::var("GATEWAY_URL").unwrap_or_else(|_| "http://localhost:8081".to_string());

            let image_data = fs::read(image_path)?;
            let base64_image = base64::Engine::encode(&base64::engine::general_purpose::STANDARD, image_data);

            let payload = json!({
                "image_base64": format!("data:image/png;base64,{}", base64_image),
                "prompt": prompt
            });

            println!("{}", "Sending image to Vision service...".cyan());

            match client.post(format!("{}/api/multimodal/process-image", gateway_url))
                .json(&payload)
                .send()
                .await
            {
                Ok(res) if res.status().is_success() => {
                    let result: serde_json::Value = res.json().await?;
                    println!("\n{}", "Image Description:".bright_magenta().bold());
                    println!("{}", result["text"].as_str().unwrap_or("No description returned"));
                }
                Ok(res) => println!("{} Error: {} - {}", "✘".red(), res.status(), res.text().await.unwrap_or_default()),
                Err(e) => println!("{} Connection error: {}", "✘".red(), e),
            }
        }
        Commands::Apply { file_path, patch } => {
            let patches = parse_patch_blocks(patch);
            if patches.is_empty() {
                println!("{} No SEARCH/REPLACE blocks found in the patch string.", "✘".red());
                return Ok(());
            }
            apply_patches(&file_path.to_string_lossy(), &patches)?;
        }
        Commands::Git { subcommand } => {
            let gateway_url = env::var("GATEWAY_URL").unwrap_or_else(|_| "http://localhost:8081".to_string());
            let client = reqwest::Client::new();

            match subcommand {
                GitCommand::Status => {
                    match client.get(format!("{}/api/git/status", gateway_url)).send().await {
                        Ok(res) if res.status().is_success() => {
                            let data: serde_json::Value = res.json().await?;
                            let empty_vec = vec![];
                            let lines = data["lines"].as_array().unwrap_or(&empty_vec);
                            println!("{}", "Git Status:".bright_magenta().bold());
                            for line in lines {
                                println!("  {}", line.as_str().unwrap_or(""));
                            }
                            if lines.is_empty() {
                                println!("  {} working tree clean", "✔".green());
                            }
                        }
                        Ok(res) => println!("{} {}", "✘".red(), res.text().await.unwrap_or_else(|_| "Error".into())),
                        Err(e) => println!("{} {}", "✘".red(), e),
                    }
                }
                GitCommand::Diff { path } => {
                    let url = path.as_ref()
                        .map(|p| format!("{}/api/git/diff?path={}", gateway_url, urlencoding::encode(p)))
                        .unwrap_or_else(|| format!("{}/api/git/diff", gateway_url));
                    match client.get(&url).send().await {
                        Ok(res) if res.status().is_success() => {
                            let data: serde_json::Value = res.json().await?;
                            println!("{}", data["stdout"].as_str().unwrap_or(""));
                        }
                        Ok(res) => println!("{} {}", "✘".red(), res.text().await.unwrap_or_else(|_| "Error".into())),
                        Err(e) => println!("{} {}", "✘".red(), e),
                    }
                }
                GitCommand::Log { n } => {
                    match client.get(format!("{}/api/git/log?n={}", gateway_url, n)).send().await {
                        Ok(res) if res.status().is_success() => {
                            let data: serde_json::Value = res.json().await?;
                            let empty_vec = vec![];
                            let commits = data["commits"].as_array().unwrap_or(&empty_vec);
                            println!("{}", "Git Log:".bright_magenta().bold());
                            for c in commits {
                                println!("  {} {} {}  {}",
                                    c["hash"].as_str().unwrap_or("").yellow(),
                                    c["date"].as_str().unwrap_or(""),
                                    c["author"].as_str().unwrap_or(""),
                                    c["subject"].as_str().unwrap_or(""));
                            }
                        }
                        Ok(res) => println!("{} {}", "✘".red(), res.text().await.unwrap_or_else(|_| "Error".into())),
                        Err(e) => println!("{} {}", "✘".red(), e),
                    }
                }
                GitCommand::Branch => {
                    match client.get(format!("{}/api/git/branch", gateway_url)).send().await {
                        Ok(res) if res.status().is_success() => {
                            let data: serde_json::Value = res.json().await?;
                            println!("{} current: {}", "Git Branch:".bright_magenta().bold(), data["current"].as_str().unwrap_or(""));
                            if let Some(branches) = data["branches"].as_array() {
                                for b in branches {
                                    println!("  {}", b.as_str().unwrap_or(""));
                                }
                            }
                        }
                        Ok(res) => println!("{} {}", "✘".red(), res.text().await.unwrap_or_else(|_| "Error".into())),
                        Err(e) => println!("{} {}", "✘".red(), e),
                    }
                }
                GitCommand::Commit { message, paths } => {
                    let payload = json!({ "message": message, "paths": paths });
                    match client.post(format!("{}/api/git/commit", gateway_url)).json(&payload).send().await {
                        Ok(res) if res.status().is_success() => {
                            let data: serde_json::Value = res.json().await?;
                            if data["success"].as_bool().unwrap_or(false) {
                                println!("{} {}", "✔".green(), "Committed.".to_string());
                                if let Some(s) = data["stdout"].as_str() {
                                    println!("{}", s);
                                }
                            } else {
                                println!("{} {}", "✘".red(), data["stderr"].as_str().unwrap_or("git commit failed"));
                            }
                        }
                        Ok(res) => println!("{} {}", "✘".red(), res.text().await.unwrap_or_else(|_| "Error".into())),
                        Err(e) => println!("{} {}", "✘".red(), e),
                    }
                }
            }
        }
    }

    Ok(())
}
