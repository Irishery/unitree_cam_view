#!/usr/bin/env python3
import os
import subprocess
import sys

from ament_index_python.packages import get_package_prefix

USB_CAM_EXECUTABLE = os.path.join(
    get_package_prefix("usb_cam"), "lib", "usb_cam", "usb_cam_node_exe"
)


def _apply_control(device, control):
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--device", device, "--set-ctrl", control],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print(
            f"usb_cam_stable: v4l2-ctl not found, cannot set '{control}'",
            file=sys.stderr,
        )
        return
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        print(
            f"usb_cam_stable: failed to set '{control}' on {device}: {message}",
            file=sys.stderr,
        )


def main():
    arguments = sys.argv[1:]
    controls = []
    while len(arguments) >= 2 and arguments[0] == "--control":
        controls.append(arguments[1])
        arguments = arguments[2:]

    if not arguments:
        print(
            "usage: usb_cam_stable.py [--control name=value ...] <device-path> [node arguments...]",
            file=sys.stderr,
        )
        return 1

    device = os.path.realpath(arguments[0])
    for control in controls:
        _apply_control(device, control)

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
