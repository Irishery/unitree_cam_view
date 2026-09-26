import glob
import os

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

PACKAGE_NAME = "g1_cam_view"
LOGI_NAMESPACES = ("logi_1", "logi_2")


def _configured_device(params_file, namespace):
    try:
        with open(params_file, "r", encoding="utf-8") as stream:
            config = yaml.safe_load(stream) or {}
        section = config.get(f"/{namespace}/usb_cam", {}).get("ros__parameters", {})
        return str(section.get("video_device", ""))
    except (OSError, yaml.YAMLError, AttributeError):
        return ""


def _discover_devices(device_dir, id_filter):
    pattern = os.path.join(device_dir, f"*{id_filter}*-video-index0")
    return [path for path in sorted(glob.glob(pattern)) if os.path.exists(path)]


def _resolve_logi_devices(params_file, device_dir, id_filter):
    resolved = {}
    used = set()

    for namespace in LOGI_NAMESPACES:
        device = _configured_device(params_file, namespace)
        if device and "CHANGE_ME" not in device and os.path.exists(device):
            resolved[namespace] = (os.path.realpath(device), "configured", device)
            used.add(os.path.realpath(device))

    available = _discover_devices(device_dir, id_filter)
    for namespace in LOGI_NAMESPACES:
        if namespace in resolved:
            continue
        for candidate in available:
            real_device = os.path.realpath(candidate)
            if real_device in used:
                continue
            resolved[namespace] = (real_device, "auto", candidate)
            used.add(real_device)
            break

    return resolved


def generate_launch_description():
    package_share = get_package_share_directory(PACKAGE_NAME)
    params_file = os.path.join(package_share, "config", "cameras.yaml")
    device_dir = os.environ.get("G1_CAM_DEVICE_DIR", "/dev/v4l/by-id")
    id_filter = os.environ.get("G1_CAM_LOGI_FILTER", "usb-046d")

    arguments = [
        DeclareLaunchArgument("logi_1", default_value="true"),
        DeclareLaunchArgument("logi_2", default_value="true"),
        DeclareLaunchArgument("mosaic", default_value="true"),
        DeclareLaunchArgument("mosaic_fps", default_value="10.0"),
        DeclareLaunchArgument("mosaic_quality", default_value="80"),
        DeclareLaunchArgument("tile_width", default_value="640"),
        DeclareLaunchArgument("tile_height", default_value="480"),
        DeclareLaunchArgument("columns", default_value="2"),
    ]

    actions = list(arguments)

    resolved = _resolve_logi_devices(params_file, device_dir, id_filter)

    for namespace in LOGI_NAMESPACES:
        entry = resolved.get(namespace)
        if entry is None:
            actions.append(
                LogInfo(
                    msg=(
                        f"[g1_cam_view] {namespace}: camera not found in {device_dir} "
                        f"(filter '*{id_filter}*-video-index0'); node not started"
                    ),
                    condition=IfCondition(LaunchConfiguration(namespace)),
                )
            )
            continue

        device, source, discovered = entry
        actions.append(
            LogInfo(
                msg=f"[g1_cam_view] {namespace}: {source} camera {discovered} -> {device}",
                condition=IfCondition(LaunchConfiguration(namespace)),
            )
        )
        actions.append(
            Node(
                package=PACKAGE_NAME,
                executable="usb_cam_stable.py",
                name="usb_cam",
                namespace=namespace,
                output="screen",
                arguments=[discovered],
                parameters=[params_file],
                condition=IfCondition(LaunchConfiguration(namespace)),
                respawn=True,
                respawn_delay=5.0,
            )
        )

    mosaic_topics = []
    mosaic_labels = []
    for namespace in LOGI_NAMESPACES:
        if namespace in resolved:
            mosaic_topics.append(f"/{namespace}/image_raw")
            mosaic_labels.append(namespace)

    if not mosaic_topics:
        actions.append(
            LogInfo(
                msg="[g1_cam_view] mosaic: no cameras found; mosaic not started",
                condition=IfCondition(LaunchConfiguration("mosaic")),
            )
        )
    else:
        actions.append(
            Node(
                package=PACKAGE_NAME,
                executable="camera_mosaic.py",
                name="camera_mosaic",
                output="screen",
                condition=IfCondition(LaunchConfiguration("mosaic")),
                parameters=[
                    {
                        "topics": mosaic_topics,
                        "labels": mosaic_labels,
                        "output_topic": "/cameras/mosaic/compressed",
                        "fps": ParameterValue(LaunchConfiguration("mosaic_fps"), value_type=float),
                        "quality": ParameterValue(LaunchConfiguration("mosaic_quality"), value_type=int),
                        "tile_width": ParameterValue(LaunchConfiguration("tile_width"), value_type=int),
                        "tile_height": ParameterValue(LaunchConfiguration("tile_height"), value_type=int),
                        "columns": ParameterValue(LaunchConfiguration("columns"), value_type=int),
                    }
                ],
            )
        )

    return LaunchDescription(actions)
