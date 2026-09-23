#!/usr/bin/env bash
# Source this file on the G1 before starting the camera stack:
#   source scripts/cam_env.sh [network-interface ...]

_g1_cam_had_nounset=false
case "$-" in
  *u*)
    _g1_cam_had_nounset=true
    set +u
    ;;
esac

_g1_cam_setup() {
  local script_dir workspace_dir interfaces_string peers_string interface_list peer_list
  local cyclonedds_uri

  script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  workspace_dir="$(cd -- "${script_dir}/.." && pwd)"

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

  if [[ ! -f /opt/ros/humble/setup.bash ]]; then
    echo "G1 camera environment error: /opt/ros/humble/setup.bash is missing" >&2
    return 1
  fi
  source /opt/ros/humble/setup.bash

  if [[ ! -f "${workspace_dir}/install/setup.bash" ]]; then
    echo "G1 camera environment error: project overlay is missing; run ./scripts/build.sh first" >&2
    return 1
  fi
  source "${workspace_dir}/install/setup.bash"

  export ROS_DOMAIN_ID=0
  export ROS_LOCALHOST_ONLY=0
  export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  unset FASTRTPS_DEFAULT_PROFILES_FILE
  unset FASTDDS_DEFAULT_PROFILES_FILE

  # shellcheck source=dds_env.sh
  source "${script_dir}/dds_env.sh"
  if ! cyclonedds_uri="$(g1_cam_cyclonedds_uri "${interfaces_string}" "${peers_string}" 2>&1)"; then
    echo "G1 camera environment error: ${cyclonedds_uri}" >&2
    unset -f g1_cam_cyclonedds_uri
    return 1
  fi
  unset -f g1_cam_cyclonedds_uri

  if [[ -n "${cyclonedds_uri}" ]]; then
    export CYCLONEDDS_URI="${cyclonedds_uri}"
  else
    unset CYCLONEDDS_URI
  fi

  if [[ -n "${interfaces_string}" ]]; then
    interface_list="${interfaces_string// /,}"
  else
    interface_list="auto"
  fi
  if [[ -n "${peers_string}" ]]; then
    peer_list="${peers_string// /,}"
  else
    peer_list="none"
  fi

  if [[ "${ROS_DISTRO:-}" != "humble" ]]; then
    echo "G1 camera environment error: expected ROS_DISTRO=humble, got ${ROS_DISTRO:-unset}" >&2
    return 1
  fi
  if ! command -v ros2 >/dev/null 2>&1; then
    echo "G1 camera environment error: ros2 is unavailable" >&2
    return 1
  fi
  if ! ros2 pkg prefix rmw_cyclonedds_cpp >/dev/null 2>&1; then
    echo "G1 camera environment error: rmw_cyclonedds_cpp is not installed" >&2
    return 1
  fi

  echo "G1 camera ROS environment: distro=${ROS_DISTRO}, domain=${ROS_DOMAIN_ID}, rmw=${RMW_IMPLEMENTATION}, interfaces=${interface_list}, peers=${peer_list}"
}

if _g1_cam_setup "$@"; then
  _g1_cam_status=0
else
  _g1_cam_status=$?
fi
unset -f _g1_cam_setup
if [[ "${_g1_cam_had_nounset}" == true ]]; then
  set -u
fi
unset _g1_cam_had_nounset
if [[ ${_g1_cam_status} -ne 0 ]]; then
  return "${_g1_cam_status}" 2>/dev/null || exit "${_g1_cam_status}"
fi
unset _g1_cam_status
