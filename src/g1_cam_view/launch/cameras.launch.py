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
MOSAIC_TOPICS = [
    "/camera/camera/color/image_raw",
    "/logi_1/image_raw",
    "/logi_2/image_raw",
]
MOSAIC_LABELS = ["D435", "logi_1", "logi_2"]


def _logi_device(params_file, namespace):
    try:
        with open(params_file, "r", encoding="utf-8") as stream:
            config = yaml.safe_load(stream) or {}
        section = config.get(f"/{namespace}/usb_cam", {}).get("ros__parameters", {})
        return str(section.get("video_device", ""))
    except (OSError, yaml.YAMLError, AttributeError):
        return ""


def generate_launch_description():
    package_share = get_package_share_directory(PACKAGE_NAME)
    params_file = os.path.join(package_share, "config", "cameras.yaml")

    arguments = [
        DeclareLaunchArgument("realsense", default_value="true"),
        DeclareLaunchArgument("logi_1", default_value="true"),
        DeclareLaunchArgument("logi_2", default_value="true"),
        DeclareLaunchArgument("mosaic", default_value="true"),
        DeclareLaunchArgument("serial_no", default_value=""),
        DeclareLaunchArgument("device_type", default_value=""),
        DeclareLaunchArgument("color_profile", default_value="640x480x15"),
        DeclareLaunchArgument("mosaic_fps", default_value="10.0"),
        DeclareLaunchArgument("mosaic_quality", default_value="80"),
        DeclareLaunchArgument("tile_width", default_value="640"),
        DeclareLaunchArgument("tile_height", default_value="480"),
        DeclareLaunchArgument("columns", default_value="3"),
    ]

    actions = list(arguments)

    actions.append(
        Node(
            package="realsense2_camera",
            executable="realsense2_camera_node",
            namespace="camera",
            name="camera",
            output="screen",
            condition=IfCondition(LaunchConfiguration("realsense")),
            parameters=[
                {
                    "device_type": ParameterValue(LaunchConfiguration("device_type"), value_type=str),
                    "serial_no": ParameterValue(LaunchConfiguration("serial_no"), value_type=str),
                    "enable_color": True,
                    "rgb_camera.color_profile": ParameterValue(
                        LaunchConfiguration("color_profile"), value_type=str
                    ),
                    "enable_depth": False,
                    "enable_infra": False,
                    "enable_infra1": False,
                    "enable_infra2": False,
                    "enable_gyro": False,
                    "enable_accel": False,
                    "pointcloud.enable": False,
                    "publish_tf": False,
                }
            ],
        )
    )

    for namespace in LOGI_NAMESPACES:
        device = _logi_device(params_file, namespace)
        if "CHANGE_ME" in device:
            actions.append(
                LogInfo(
                    msg=(
                        f"[g1_cam_view] {namespace}: video_device still has the CHANGE_ME "
                        f"placeholder ('{device}'). Run ./scripts/find_cameras.sh and put the "
                        f"real /dev/v4l/by-id path into config/cameras.yaml."
                    ),
                    condition=IfCondition(LaunchConfiguration(namespace)),
                )
            )
        actions.append(
            Node(
                package="usb_cam",
                executable="usb_cam_node_exe",
                name="usb_cam",
                namespace=namespace,
                output="screen",
                parameters=[params_file],
                condition=IfCondition(LaunchConfiguration(namespace)),
            )
        )

    actions.append(
        Node(
            package=PACKAGE_NAME,
            executable="camera_mosaic.py",
            name="camera_mosaic",
            output="screen",
            condition=IfCondition(LaunchConfiguration("mosaic")),
            parameters=[
                {
                    "topics": MOSAIC_TOPICS,
                    "labels": MOSAIC_LABELS,
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
