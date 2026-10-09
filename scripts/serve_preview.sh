#!/usr/bin/env bash
# Serve the delivered e-portfolio locally over HTTP.
# The site MUST be served (not opened as file://): every academic page fetches
# the shared footer.html fragment at runtime, which the file scheme blocks.
#
# Usage:  ./scripts/serve_preview.sh [port]      (default port 8756)
set -u
PORT="${1:-8756}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Serving ${ROOT}"
echo "Open http://localhost:${PORT}/index.html  (Ctrl+C to stop)"
cd "${ROOT}" && exec python3 -m http.server "${PORT}" --bind 127.0.0.1
