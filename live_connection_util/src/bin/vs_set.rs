//! Native, manual two-Enter handoff from visual preparation to the live set.
#[path = "../set_cli/mod.rs"]
mod set_cli;

fn main() {
    if let Err(error) = set_cli::run() {
        eprintln!("\n{error:#}");
        std::process::exit(if set_cli::cancelled() { 130 } else { 1 });
    }
}
