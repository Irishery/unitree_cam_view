#!/usr/bin/env bash
set -euo pipefail

workspace_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
docker build \
  -f "${workspace_dir}/docker/camera_viewer.Dockerfile" \
  -t unitree-g1-camera-viewer:humble \
  "${workspace_dir}"
