#!/bin/sh
set -eu
cd "$(dirname "$0")"
./cargo-local build --locked --release
exec ./target/release/live-connection-util "$@"
