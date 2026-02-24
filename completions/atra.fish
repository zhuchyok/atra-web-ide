# Print an optspec for argparse to handle cmd's options that are independent of any subcommand.
function __fish_atra_global_optspecs
	string join \n generate= c/config= h/help
end

function __fish_atra_needs_command
	# Figure out if the current invocation already has a command.
	set -l cmd (commandline -opc)
	set -e cmd[1]
	argparse -s (__fish_atra_global_optspecs) -- $cmd 2>/dev/null
	or return
	if set -q argv[1]
		# Also print the command, so this can be used to figure out what it is.
		echo $argv[1]
		return 1
	end
	return 0
end

function __fish_atra_using_subcommand
	set -l cmd (__fish_atra_needs_command)
	test -z "$cmd"
	and return 1
	contains -- $cmd[1] $argv
end

complete -c atra -n "__fish_atra_needs_command" -l generate -d 'Generate shell completions' -r -f -a "bash\t''
elvish\t''
fish\t''
powershell\t''
zsh\t''"
complete -c atra -n "__fish_atra_needs_command" -s c -l config -d 'Config file path' -r -F
complete -c atra -n "__fish_atra_needs_command" -s h -l help -d 'Print help'
complete -c atra -n "__fish_atra_needs_command" -f -a "health" -d 'Checks connection to Rust API Gateway and Victoria'
complete -c atra -n "__fish_atra_needs_command" -f -a "chat" -d 'Sends a message to Victoria through the Gateway'
complete -c atra -n "__fish_atra_needs_command" -f -a "plan" -d 'Requests a plan from Victoria'
complete -c atra -n "__fish_atra_needs_command" -f -a "status" -d 'Shows system metrics and health'
complete -c atra -n "__fish_atra_needs_command" -f -a "cleanup" -d 'Triggers data retention cleanup'
complete -c atra -n "__fish_atra_needs_command" -f -a "describe" -d 'Describes an image using Vision'
complete -c atra -n "__fish_atra_needs_command" -f -a "apply" -d 'Applies SEARCH/REPLACE blocks to a file'
complete -c atra -n "__fish_atra_needs_command" -f -a "git" -d 'Git: status, diff, log, branch, commit (via Gateway)'
complete -c atra -n "__fish_atra_needs_command" -f -a "help" -d 'Print this message or the help of the given subcommand(s)'
complete -c atra -n "__fish_atra_using_subcommand health" -s c -l config -d 'Config file path' -r -F
complete -c atra -n "__fish_atra_using_subcommand health" -s h -l help -d 'Print help'
complete -c atra -n "__fish_atra_using_subcommand chat" -s c -l config -d 'Config file path' -r -F
complete -c atra -n "__fish_atra_using_subcommand chat" -s h -l help -d 'Print help'
complete -c atra -n "__fish_atra_using_subcommand plan" -s c -l config -d 'Config file path' -r -F
complete -c atra -n "__fish_atra_using_subcommand plan" -s h -l help -d 'Print help'
complete -c atra -n "__fish_atra_using_subcommand status" -s c -l config -d 'Config file path' -r -F
complete -c atra -n "__fish_atra_using_subcommand status" -s h -l help -d 'Print help'
complete -c atra -n "__fish_atra_using_subcommand cleanup" -l tables -d 'Tables to clean (comma-separated)' -r
complete -c atra -n "__fish_atra_using_subcommand cleanup" -s c -l config -d 'Config file path' -r -F
complete -c atra -n "__fish_atra_using_subcommand cleanup" -l dry-run -d 'Dry run mode (default: true)'
complete -c atra -n "__fish_atra_using_subcommand cleanup" -s h -l help -d 'Print help'
complete -c atra -n "__fish_atra_using_subcommand describe" -l prompt -d 'Optional prompt for description' -r
complete -c atra -n "__fish_atra_using_subcommand describe" -s c -l config -d 'Config file path' -r -F
complete -c atra -n "__fish_atra_using_subcommand describe" -s h -l help -d 'Print help'
complete -c atra -n "__fish_atra_using_subcommand apply" -s c -l config -d 'Config file path' -r -F
complete -c atra -n "__fish_atra_using_subcommand apply" -s h -l help -d 'Print help'
complete -c atra -n "__fish_atra_using_subcommand git; and not __fish_seen_subcommand_from status diff log branch commit help" -s c -l config -d 'Config file path' -r -F
complete -c atra -n "__fish_atra_using_subcommand git; and not __fish_seen_subcommand_from status diff log branch commit help" -s h -l help -d 'Print help'
complete -c atra -n "__fish_atra_using_subcommand git; and not __fish_seen_subcommand_from status diff log branch commit help" -f -a "status" -d 'Show working tree status'
complete -c atra -n "__fish_atra_using_subcommand git; and not __fish_seen_subcommand_from status diff log branch commit help" -f -a "diff" -d 'Show diff (optional path)'
complete -c atra -n "__fish_atra_using_subcommand git; and not __fish_seen_subcommand_from status diff log branch commit help" -f -a "log" -d 'Show commit log'
complete -c atra -n "__fish_atra_using_subcommand git; and not __fish_seen_subcommand_from status diff log branch commit help" -f -a "branch" -d 'Show current branch and list'
complete -c atra -n "__fish_atra_using_subcommand git; and not __fish_seen_subcommand_from status diff log branch commit help" -f -a "commit" -d 'Commit staged or all changes'
complete -c atra -n "__fish_atra_using_subcommand git; and not __fish_seen_subcommand_from status diff log branch commit help" -f -a "help" -d 'Print this message or the help of the given subcommand(s)'
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from status" -s c -l config -d 'Config file path' -r -F
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from status" -s h -l help -d 'Print help'
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from diff" -s p -l path -r
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from diff" -s c -l config -d 'Config file path' -r -F
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from diff" -s h -l help -d 'Print help'
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from log" -s n -l n -r
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from log" -s c -l config -d 'Config file path' -r -F
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from log" -s h -l help -d 'Print help'
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from branch" -s c -l config -d 'Config file path' -r -F
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from branch" -s h -l help -d 'Print help'
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from commit" -s m -l message -d 'Commit message' -r
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from commit" -s p -l paths -d 'Paths to add (default: all)' -r
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from commit" -s c -l config -d 'Config file path' -r -F
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from commit" -s h -l help -d 'Print help'
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from help" -f -a "status" -d 'Show working tree status'
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from help" -f -a "diff" -d 'Show diff (optional path)'
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from help" -f -a "log" -d 'Show commit log'
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from help" -f -a "branch" -d 'Show current branch and list'
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from help" -f -a "commit" -d 'Commit staged or all changes'
complete -c atra -n "__fish_atra_using_subcommand git; and __fish_seen_subcommand_from help" -f -a "help" -d 'Print this message or the help of the given subcommand(s)'
complete -c atra -n "__fish_atra_using_subcommand help; and not __fish_seen_subcommand_from health chat plan status cleanup describe apply git help" -f -a "health" -d 'Checks connection to Rust API Gateway and Victoria'
complete -c atra -n "__fish_atra_using_subcommand help; and not __fish_seen_subcommand_from health chat plan status cleanup describe apply git help" -f -a "chat" -d 'Sends a message to Victoria through the Gateway'
complete -c atra -n "__fish_atra_using_subcommand help; and not __fish_seen_subcommand_from health chat plan status cleanup describe apply git help" -f -a "plan" -d 'Requests a plan from Victoria'
complete -c atra -n "__fish_atra_using_subcommand help; and not __fish_seen_subcommand_from health chat plan status cleanup describe apply git help" -f -a "status" -d 'Shows system metrics and health'
complete -c atra -n "__fish_atra_using_subcommand help; and not __fish_seen_subcommand_from health chat plan status cleanup describe apply git help" -f -a "cleanup" -d 'Triggers data retention cleanup'
complete -c atra -n "__fish_atra_using_subcommand help; and not __fish_seen_subcommand_from health chat plan status cleanup describe apply git help" -f -a "describe" -d 'Describes an image using Vision'
complete -c atra -n "__fish_atra_using_subcommand help; and not __fish_seen_subcommand_from health chat plan status cleanup describe apply git help" -f -a "apply" -d 'Applies SEARCH/REPLACE blocks to a file'
complete -c atra -n "__fish_atra_using_subcommand help; and not __fish_seen_subcommand_from health chat plan status cleanup describe apply git help" -f -a "git" -d 'Git: status, diff, log, branch, commit (via Gateway)'
complete -c atra -n "__fish_atra_using_subcommand help; and not __fish_seen_subcommand_from health chat plan status cleanup describe apply git help" -f -a "help" -d 'Print this message or the help of the given subcommand(s)'
complete -c atra -n "__fish_atra_using_subcommand help; and __fish_seen_subcommand_from git" -f -a "status" -d 'Show working tree status'
complete -c atra -n "__fish_atra_using_subcommand help; and __fish_seen_subcommand_from git" -f -a "diff" -d 'Show diff (optional path)'
complete -c atra -n "__fish_atra_using_subcommand help; and __fish_seen_subcommand_from git" -f -a "log" -d 'Show commit log'
complete -c atra -n "__fish_atra_using_subcommand help; and __fish_seen_subcommand_from git" -f -a "branch" -d 'Show current branch and list'
complete -c atra -n "__fish_atra_using_subcommand help; and __fish_seen_subcommand_from git" -f -a "commit" -d 'Commit staged or all changes'
