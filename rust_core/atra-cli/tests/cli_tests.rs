#[test]
fn verify_cli() {
    use clap::CommandFactory;
    crate::Cli::command().debug_assert();
}
