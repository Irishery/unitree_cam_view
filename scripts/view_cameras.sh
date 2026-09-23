#!/usr/bin/env bash
# Show the G1 camera mosaic in RViz on the laptop.
# The viewer joins the robot's CycloneDDS domain in a Humble container and only
# subscribes to image topics; it never publishes motor or velocity commands.

set -euo pipefail

if [[ -z "${DISPLAY:-}" ]]; then
  echo "DISPLAY is unset. Run this from the laptop's graphical desktop session." >&2
  exit 1
fi
if ! command -v xhost >/dev/null; then
  echo "xhost is required for Docker to open an X11 RViz window." >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
rviz_config="${repo_root}/src/g1_cam_view/rviz/cameras.rviz"
image_name="unitree-g1-camera-viewer:humble"

if [[ ! -f "$rviz_config" ]]; then
  echo "RViz profile not found: $rviz_config" >&2
  exit 1
fi

camera_domain_id="${ROS_DOMAIN_ID:-0}"
camera_network_interface="${G1_CAM_NETWORK_INTERFACE:-}"
camera_peers="${G1_CAM_PEERS-10.0.88.180:7410}"
declare -a cyclonedds_peer_array=()

if [[ "${camera_domain_id}" != "0" ]]; then
  echo "The G1 camera viewer requires ROS_DOMAIN_ID=0 (got ${camera_domain_id})." >&2
  exit 2
fi
if [[ -n "${camera_network_interface}" ]]; then
  if ! ip link show dev "${camera_network_interface}" >/dev/null 2>&1; then
    echo "G1 camera network interface does not exist: ${camera_network_interface}" >&2
    exit 2
  fi
fi
if ! docker image inspect "${image_name}" >/dev/null 2>&1; then
  echo "Camera viewer image is missing: ${image_name}" >&2
  echo "Build it first with: ./scripts/viewer_build.sh" >&2
  exit 1
fi

xhost +si:localuser:root >/dev/null
cleanup() {
  xhost -si:localuser:root >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker_args=(
  --rm
  --network host
  --ipc host
  -e "DISPLAY=${DISPLAY}"
  -e QT_X11_NO_MITSHM=1
  -e XDG_RUNTIME_DIR=/tmp/runtime-root
  -e "ROS_DOMAIN_ID=${camera_domain_id}"
  -e ROS_LOCALHOST_ONLY=0
  -e RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw
  -v "${rviz_config}:/tmp/g1_cameras.rviz:ro"
)

cyclonedds_general=""
# RViz is the only DDS application in this container, so a fixed participant
# index is safe and gives the robot a deterministic discovery endpoint.  For
# ROS_DOMAIN_ID=0, participant index 0 uses the standard unicast port 7410.
cyclonedds_discovery="<Discovery><ParticipantIndex>0</ParticipantIndex></Discovery>"
if [[ -n "${camera_network_interface}" ]]; then
  cyclonedds_general="<General><Interfaces><NetworkInterface name=\"${camera_network_interface}\" priority=\"default\" multicast=\"default\" /></Interfaces><MulticastRecvNetworkInterfaceAddresses>all</MulticastRecvNetworkInterfaceAddresses></General>"
fi
if [[ -n "${camera_peers}" ]]; then
  cyclonedds_peers=""
  read -r -a cyclonedds_peer_array <<<"${camera_peers}"
  for peer in "${cyclonedds_peer_array[@]}"; do
    if [[ ! "${peer}" =~ ^[[:alnum:]_.:-]+$ ]]; then
      echo "Invalid CycloneDDS peer: ${peer}" >&2
      exit 2
    fi
    cyclonedds_peers+="<Peer Address=\"${peer}\" />"
  done
  cyclonedds_discovery="<Discovery><ParticipantIndex>0</ParticipantIndex><Peers>${cyclonedds_peers}</Peers></Discovery>"
fi
if [[ -n "${cyclonedds_general}${cyclonedds_discovery}" ]]; then
  docker_args+=(
    -e "CYCLONEDDS_URI=<CycloneDDS><Domain>${cyclonedds_general}${cyclonedds_discovery}</Domain></CycloneDDS>"
  )
fi

case "${RVIZ_GL:-software}" in
  software)
    docker_args+=(-e LIBGL_ALWAYS_SOFTWARE=1 -e MESA_GL_VERSION_OVERRIDE=3.3 -e MESA_GLSL_VERSION_OVERRIDE=330)
    ;;
  hardware)
    docker_args+=(--device /dev/dri:/dev/dri)
    ;;
  *)
    echo "Unknown RVIZ_GL=${RVIZ_GL}. Use software or hardware." >&2
    exit 2
    ;;
esac

docker run "${docker_args[@]}" \
  "${image_name}" \
  rviz2 -d /tmp/g1_cameras.rviz "$@"
