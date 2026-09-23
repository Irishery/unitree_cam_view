#!/usr/bin/env bash
# Internal helper for the G1 camera scripts. Source it, then call:
#   uri=$(g1_cam_cyclonedds_uri "<iface1 iface2>" "<peer1:port peer2:port>")
# The function prints the CycloneDDS URI on stdout and validation errors on
# stderr, returning non-zero for invalid interfaces or peers.

g1_cam_cyclonedds_uri() {
  local interfaces_string="$1"
  local peers_string="$2"
  local network_interface interfaces_xml general_xml
  local peer peers_xml discovery_xml
  local -a network_interfaces=()
  local -a peers=()

  if [[ -n "${interfaces_string}" ]]; then
    read -r -a network_interfaces <<<"${interfaces_string}"
  fi
  if [[ -n "${peers_string}" ]]; then
    read -r -a peers <<<"${peers_string}"
  fi

  if [[ ${#network_interfaces[@]} -gt 0 ]]; then
    interfaces_xml=""
    for network_interface in "${network_interfaces[@]}"; do
      if [[ ! "${network_interface}" =~ ^[[:alnum:]_.:-]+$ ]]; then
        echo "invalid network interface name: ${network_interface}" >&2
        return 1
      fi
      if ! ip link show dev "${network_interface}" >/dev/null 2>&1; then
        echo "network interface does not exist: ${network_interface}" >&2
        return 1
      fi
      interfaces_xml+="<NetworkInterface name=\"${network_interface}\" priority=\"default\" multicast=\"default\" />"
    done
    general_xml="<General><Interfaces>${interfaces_xml}</Interfaces><MulticastRecvNetworkInterfaceAddresses>all</MulticastRecvNetworkInterfaceAddresses></General>"
  else
    general_xml=""
  fi

  peers_xml=""
  for peer in "${peers[@]}"; do
    if [[ ! "${peer}" =~ ^[[:alnum:]_.:-]+$ ]]; then
      echo "invalid CycloneDDS peer: ${peer}" >&2
      return 1
    fi
    peers_xml+="<Peer Address=\"${peer}\" />"
  done
  if [[ -n "${peers_xml}" ]]; then
    discovery_xml="<Discovery><ParticipantIndex>auto</ParticipantIndex><MaxAutoParticipantIndex>120</MaxAutoParticipantIndex><Peers>${peers_xml}</Peers></Discovery>"
  else
    discovery_xml=""
  fi

  if [[ -z "${general_xml}${discovery_xml}" ]]; then
    return 0
  fi

  printf '<CycloneDDS><Domain>%s%s</Domain></CycloneDDS>' "${general_xml}" "${discovery_xml}"
}
