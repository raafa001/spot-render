#!/usr/bin/env bash
set -euo pipefail

DOWNLOAD_URL_DEFAULT="https://download.blender.org/demo/rendering/raycast-line.blend"
ASSETS_DIR_DEFAULT="$HOME/spot-render-assets"

usage() {
  cat <<'EOF'
Seed the local render queue with an official Blender demo file.

Usage:
  seed-render-queue.sh [--assets-dir DIR] [--url DOWNLOAD_URL]

Options:
  --assets-dir DIR   Directory that contains queue/output/completed/failed (default: $HOME/spot-render-assets)
  --url URL          Alternative .blend URL (default: Blender Raycast Lines demo)
  -h, --help         Show this help message

The script creates the queue/output/completed/failed directories if necessary,
downloads the demo file, and copies it into the queue so that the worker can
pick it up.
EOF
}

ASSETS_DIR="$ASSETS_DIR_DEFAULT"
DOWNLOAD_URL="$DOWNLOAD_URL_DEFAULT"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --assets-dir)
      ASSETS_DIR="$2"
      shift 2
      ;;
    --url)
      DOWNLOAD_URL="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

for subdir in queue output completed failed; do
  mkdir -p "$ASSETS_DIR/$subdir"
done

tmpfile=$(mktemp)
cleanup() {
  rm -f "$tmpfile"
}
trap cleanup EXIT

echo "Downloading demo from $DOWNLOAD_URL ..."
curl -fsSL "$DOWNLOAD_URL" -o "$tmpfile"

filename=$(basename "$DOWNLOAD_URL")
timestamp=$(date +%Y%m%d%H%M%S)
target="$ASSETS_DIR/queue/${timestamp}_${filename}"

mv "$tmpfile" "$target"
trap - EXIT

cat <<EOF
Demo file copied to $target

Next steps:
  1. Ensure the local overlay is applied (kubectl apply -k k8s/overlays/local).
  2. Wait for the blender-worker pods to pick up the job; rendered frames
     will land under $ASSETS_DIR/output/.
EOF
