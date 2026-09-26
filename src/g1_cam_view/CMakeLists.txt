cmake_minimum_required(VERSION 3.8)
project(g1_cam_view)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch rviz DESTINATION share/${PROJECT_NAME})
install(PROGRAMS
  scripts/camera_mosaic.py
  scripts/usb_cam_stable.py
  DESTINATION lib/${PROJECT_NAME})

ament_package()
