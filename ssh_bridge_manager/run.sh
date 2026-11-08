#!/usr/bin/env bash
# Start ssh_bridge_manager (Linux: no desktop shell).
set -euo pipefail
cd "$(dirname "$0")"
exec ./ssh_bridge_manager "$@"
