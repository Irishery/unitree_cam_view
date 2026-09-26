#!/usr/bin/env python3
import os
import sys

from ament_index_python.packages import get_package_prefix

USB_CAM_EXECUTABLE = os.path.join(
    get_package_prefix("usb_cam"), "lib", "usb_cam", "usb_cam_node_exe"
)


def main():
    arguments = sys.argv[1:]
    if not arguments:
        print("usage: usb_cam_stable.py <device-path> [node arguments...]", file=sys.stderr)
        return 1

    device = os.path.realpath(arguments[0])
    command = [
        USB_CAM_EXECUTABLE,
        *arguments[1:],
        "--ros-args",
        "-p",
        f"video_device:={device}",
    ]
    os.execv(USB_CAM_EXECUTABLE, command)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
