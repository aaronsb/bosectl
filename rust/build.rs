use std::path::Path;
use std::process::Command;

fn main() {
    // Outside the git checkout (e.g. building the crates.io package) git
    // exits non-zero with empty stdout, so fall back on status, not output.
    let hash = Command::new("git")
        .args(["rev-parse", "--short", "HEAD"])
        .output()
        .ok()
        .filter(|o| o.status.success())
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .unwrap_or_else(|| "unknown".into());
    println!("cargo:rustc-env=GIT_HASH={}", hash.trim());
    // A missing rerun-if-changed path makes cargo rerun this script every build.
    if Path::new("../.git/HEAD").exists() {
        println!("cargo:rerun-if-changed=../.git/HEAD");
    }
}
