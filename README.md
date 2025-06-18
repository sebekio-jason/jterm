# reload your shell
. "$HOME/.cargo/env"

# install libs
sudo apt update && sudo apt install pkg-config libssl-dev build-essential pkg-config libssh2-1-dev

# Required vscode extensions
Rust Analyzer (best for Rust development)
CodeLLDB (for debugging)

# Debugging building
If you ever want to check what a crate needs, look for these dependencies in error logs:
libssl-dev → for OpenSSL
libz-dev or zlib1g-dev → for zlib
libssh2-1-dev → for SSH2 stuff
