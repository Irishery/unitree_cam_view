#!/usr/bin/env bash
set -euo pipefail

workspace_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f /opt/ros/humble/setup.bash ]]; then
  echo "ROS 2 Humble is not installed in /opt/ros/humble" >&2
  exit 1
fi

set +u
source /opt/ros/humble/setup.bash
set -u

cd "${workspace_dir}"
colcon build --symlink-install --packages-select g1_cam_view
