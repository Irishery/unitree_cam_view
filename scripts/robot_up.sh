#!/usr/bin/env bash
# Run the G1 camera stack on the robot in Docker:
#   ./scripts/robot_up.sh [network-interface ...]
# Interfaces may also come from G1_CAM_NETWORK_INTERFACES / G1_CAM_NETWORK_INTERFACE,
# and the laptop peer from G1_CAM_PEERS. Extra ros2 launch arguments go through
# G1_CAM_LAUNCH_ARGS, for example: G1_CAM_LAUNCH_ARGS="logi_1:=false"

set -euo pipefail

if ! command -v docker >/dev/null; then
  echo "docker is required on the robot" >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
image_name="unitree-g1-camera-robot:humble"
config_file="${repo_root}/src/g1_cam_view/config/cameras.yaml"
config_target="/ws/install/g1_cam_view/share/g1_cam_view/config/cameras.yaml"

if ! docker image inspect "${image_name}" >/dev/null 2>&1; then
  echo "Camera robot image is missing: ${image_name}" >&2
  echo "Build it first with: ./scripts/robot_build.sh" >&2
  exit 1
fi
if [[ ! -f "${config_file}" ]]; then
  echo "Camera config not found: ${config_file}" >&2
  exit 1
fi

if [[ $# -gt 0 ]]; then
  interfaces_string="$*"
elif [[ -n "${G1_CAM_NETWORK_INTERFACES:-}" ]]; then
  interfaces_string="${G1_CAM_NETWORK_INTERFACES}"
elif [[ -n "${G1_CAM_NETWORK_INTERFACE:-}" ]]; then
  interfaces_string="${G1_CAM_NETWORK_INTERFACE}"
else
  interfaces_string=""
fi
peers_string="${G1_CAM_PEERS:-}"

# shellcheck source=dds_env.sh
source "${script_dir}/dds_env.sh"
if ! cyclonedds_uri="$(g1_cam_cyclonedds_uri "${interfaces_string}" "${peers_string}" 2>&1)"; then
  echo "G1 camera error: ${cyclonedds_uri}" >&2
  exit 2
fi

launch_arguments=()
if [[ -n "${G1_CAM_LAUNCH_ARGS:-}" ]]; then
  read -r -a launch_arguments <<<"${G1_CAM_LAUNCH_ARGS}"
fi

docker_args=(
  --rm
  --init
  --network host
  --device-cgroup-rule "c 81:* rmw"
  --device-cgroup-rule "c 189:* rmw"
  -v /dev:/dev
  -e ROS_DOMAIN_ID=0
  -e ROS_LOCALHOST_ONLY=0
  -e RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  -v "${config_file}:${config_target}:ro"
)
if [[ -t 0 ]]; then
  docker_args+=(-it)
fi
if [[ -n "${cyclonedds_uri}" ]]; then
  docker_args+=(-e "CYCLONEDDS_URI=${cyclonedds_uri}")
fi

exec docker run "${docker_args[@]}" "${image_name}" \
  ros2 launch g1_cam_view cameras.launch.py "${launch_arguments[@]}"
