FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean \
    && apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5 \
       -o Acquire::http::Timeout=30 update \
    && apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5 \
       -o Acquire::http::Timeout=30 install -y --no-install-recommends \
       ros-humble-realsense2-camera \
       ros-humble-rmw-cyclonedds-cpp \
       ros-humble-usb-cam \
       ros-humble-compressed-image-transport \
       python3-colcon-common-extensions \
       python3-opencv \
       v4l-utils

ENV ROS_DISTRO=humble
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

COPY src/g1_cam_view /ws/src/g1_cam_view
RUN . /opt/ros/humble/setup.sh \
    && cd /ws \
    && colcon build --packages-select g1_cam_view

COPY docker/robot_entrypoint.sh /robot_entrypoint.sh
RUN chmod +x /robot_entrypoint.sh

ENTRYPOINT ["/robot_entrypoint.sh"]
CMD ["ros2", "launch", "g1_cam_view", "cameras.launch.py"]
