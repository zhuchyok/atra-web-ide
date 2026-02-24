#!/usr/bin/env bash
# Generate shell completions for atra CLI
# Based on ripgrep completion generation
# Usage: bash scripts/generate_completions.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPLETIONS_DIR="$PROJECT_ROOT/completions"

cd "$PROJECT_ROOT"

echo "🚀 Generating shell completions for atra CLI..."

# Check if atra binary exists
if [ ! -f "target/release/atra" ]; then
    echo "❌ atra binary not found. Building..."
    cargo build --release -p atra-cli
fi

# Create completions directory
mkdir -p "$COMPLETIONS_DIR"

# Generate completions for each shell
echo "📝 Generating Bash completion..."
./target/release/atra --generate-completion bash > "$COMPLETIONS_DIR/atra.bash" 2>/dev/null || {
    echo "⚠️  Warning: --generate-completion not yet implemented"
    echo "   Fallback: Creating manual completion script"
    
    # Manual Bash completion (fallback)
    cat > "$COMPLETIONS_DIR/atra.bash" << 'EOF'
# Bash completion for atra CLI
# Based on ripgrep completion

_atra() {
    local cur prev words cword
    _init_completion || return

    local commands="health chat plan status cleanup describe apply git"
    local git_commands="status diff log branch commit"

    case "$prev" in
        atra)
            COMPREPLY=($(compgen -W "$commands" -- "$cur"))
            return 0
            ;;
        git)
            COMPREPLY=($(compgen -W "$git_commands" -- "$cur"))
            return 0
            ;;
        chat|plan)
            # No completion for message/goal strings
            return 0
            ;;
        describe)
            # File completion for image path
            _filedir '@(jpg|jpeg|png|gif|webp)'
            return 0
            ;;
        apply)
            # File completion for file path
            _filedir
            return 0
            ;;
        *)
            ;;
    esac

    # Default: command completion
    COMPREPLY=($(compgen -W "$commands" -- "$cur"))
}

complete -F _atra atra
EOF
}

echo "📝 Generating Zsh completion..."
cat > "$COMPLETIONS_DIR/_atra" << 'EOF'
#compdef atra
# Zsh completion for atra CLI

_atra() {
    local -a commands git_commands
    commands=(
        'health:Check connection to Gateway and Victoria'
        'chat:Send message to Victoria'
        'plan:Request plan from Victoria'
        'status:Show system metrics'
        'cleanup:Trigger data retention cleanup'
        'describe:Describe image using Vision'
        'apply:Apply SEARCH/REPLACE patches'
        'git:Git commands via Gateway'
    )
    
    git_commands=(
        'status:Show working tree status'
        'diff:Show diff'
        'log:Show commit log'
        'branch:Show branches'
        'commit:Commit changes'
    )

    _arguments -C \
        '1: :->command' \
        '*:: :->args'

    case "$state" in
        command)
            _describe 'atra commands' commands
            ;;
        args)
            case "$words[1]" in
                git)
                    _arguments -C \
                        '1: :->git_command' \
                        '*:: :->git_args'
                    
                    case "$state" in
                        git_command)
                            _describe 'git commands' git_commands
                            ;;
                        git_args)
                            case "$words[1]" in
                                commit)
                                    _arguments \
                                        '--message[Commit message]:message:' \
                                        '--paths[Paths to add]:path:_files'
                                    ;;
                                diff)
                                    _arguments \
                                        '--path[Path to diff]:path:_files'
                                    ;;
                                log)
                                    _arguments \
                                        '--n[Number of commits]:number:'
                                    ;;
                            esac
                            ;;
                    esac
                    ;;
                describe)
                    _arguments \
                        '1:image path:_files -g "*.(jpg|jpeg|png|gif|webp)"' \
                        '--prompt[Description prompt]:prompt:'
                    ;;
                apply)
                    _arguments \
                        '1:file path:_files' \
                        '2:patch string:'
                    ;;
                cleanup)
                    _arguments \
                        '--dry-run[Dry run mode]:bool:(true false)' \
                        '--tables[Tables to clean]:tables:'
                    ;;
            esac
            ;;
    esac
}

_atra "$@"
EOF

echo "📝 Generating Fish completion..."
cat > "$COMPLETIONS_DIR/atra.fish" << 'EOF'
# Fish completion for atra CLI

# Commands
complete -c atra -n "__fish_use_subcommand" -f -a "health" -d "Check connection"
complete -c atra -n "__fish_use_subcommand" -f -a "chat" -d "Send message to Victoria"
complete -c atra -n "__fish_use_subcommand" -f -a "plan" -d "Request plan"
complete -c atra -n "__fish_use_subcommand" -f -a "status" -d "Show system metrics"
complete -c atra -n "__fish_use_subcommand" -f -a "cleanup" -d "Data retention cleanup"
complete -c atra -n "__fish_use_subcommand" -f -a "describe" -d "Describe image"
complete -c atra -n "__fish_use_subcommand" -f -a "apply" -d "Apply patches"
complete -c atra -n "__fish_use_subcommand" -f -a "git" -d "Git commands"

# Git subcommands
complete -c atra -n "__fish_seen_subcommand_from git; and not __fish_seen_subcommand_from status diff log branch commit" -f -a "status" -d "Show status"
complete -c atra -n "__fish_seen_subcommand_from git; and not __fish_seen_subcommand_from status diff log branch commit" -f -a "diff" -d "Show diff"
complete -c atra -n "__fish_seen_subcommand_from git; and not __fish_seen_subcommand_from status diff log branch commit" -f -a "log" -d "Show log"
complete -c atra -n "__fish_seen_subcommand_from git; and not __fish_seen_subcommand_from status diff log branch commit" -f -a "branch" -d "Show branches"
complete -c atra -n "__fish_seen_subcommand_from git; and not __fish_seen_subcommand_from status diff log branch commit" -f -a "commit" -d "Commit changes"

# Git commit options
complete -c atra -n "__fish_seen_subcommand_from git; and __fish_seen_subcommand_from commit" -l message -s m -d "Commit message"
complete -c atra -n "__fish_seen_subcommand_from git; and __fish_seen_subcommand_from commit" -l paths -s p -d "Paths to add"

# Git diff options
complete -c atra -n "__fish_seen_subcommand_from git; and __fish_seen_subcommand_from diff" -l path -s p -d "Path to diff"

# Git log options
complete -c atra -n "__fish_seen_subcommand_from git; and __fish_seen_subcommand_from log" -l n -s n -d "Number of commits"

# Cleanup options
complete -c atra -n "__fish_seen_subcommand_from cleanup" -l dry-run -d "Dry run mode"
complete -c atra -n "__fish_seen_subcommand_from cleanup" -l tables -d "Tables to clean"

# Describe options
complete -c atra -n "__fish_seen_subcommand_from describe" -l prompt -d "Description prompt"
EOF

echo ""
echo "✅ Completions generated in: $COMPLETIONS_DIR/"
echo ""
echo "📦 To install:"
echo ""
echo "   Bash:"
echo "   sudo cp $COMPLETIONS_DIR/atra.bash /etc/bash_completion.d/atra"
echo "   # Or:"
echo "   echo 'source $COMPLETIONS_DIR/atra.bash' >> ~/.bashrc"
echo ""
echo "   Zsh:"
echo "   cp $COMPLETIONS_DIR/_atra /usr/local/share/zsh/site-functions/"
echo "   # Or add to ~/.zshrc:"
echo "   fpath=($COMPLETIONS_DIR \$fpath)"
echo "   autoload -Uz compinit && compinit"
echo ""
echo "   Fish:"
echo "   cp $COMPLETIONS_DIR/atra.fish ~/.config/fish/completions/"
echo ""
