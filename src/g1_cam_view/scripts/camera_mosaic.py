#!/usr/bin/env python3
import time

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage, Image

DEFAULT_TOPICS = [
    "/logi_1/image_raw",
    "/logi_2/image_raw",
]
DEFAULT_LABELS = ["logi_1", "logi_2"]


class CameraMosaic(Node):
    def __init__(self):
        super().__init__("camera_mosaic")

        self._topics = [str(topic) for topic in self.declare_parameter("topics", DEFAULT_TOPICS).value]
        labels = [str(label) for label in self.declare_parameter("labels", DEFAULT_LABELS).value]
        self._labels = (labels + [f"cam{index}" for index in range(len(labels), len(self._topics))])
        self._labels = self._labels[:len(self._topics)]
        self._output_topic = str(self.declare_parameter("output_topic", "/cameras/mosaic/compressed").value)
        self._fps = float(self.declare_parameter("fps", 10.0).value)
        self._quality = int(self.declare_parameter("quality", 80).value)
        tile_width = max(1, int(self.declare_parameter("tile_width", 640).value))
        tile_height = max(1, int(self.declare_parameter("tile_height", 480).value))
        self._tile_size = (tile_width, tile_height)
        self._columns = max(1, int(self.declare_parameter("columns", 3).value))
        self._stale_timeout = float(self.declare_parameter("stale_timeout", 2.0).value)

        self._frames = [None] * len(self._topics)
        self._stamps = [0.0] * len(self._topics)
        self._warn_stamps = [0.0] * len(self._topics)

        qos = QoSProfile(
            depth=1,
            history=HistoryPolicy.KEEP_LAST,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        for index, topic in enumerate(self._topics):
            self.create_subscription(
                Image,
                topic,
                lambda message, camera_index=index: self._on_image(camera_index, message),
                qos,
            )

        self._publisher = self.create_publisher(CompressedImage, self._output_topic, 1)
        self.create_timer(1.0 / max(self._fps, 1.0), self._on_timer)

        self.get_logger().info(
            f"Mosaic of {len(self._topics)} cameras -> {self._output_topic} "
            f"at {self._fps} Hz, inputs: {', '.join(self._topics)}"
        )

    def _on_image(self, index, message):
        frame = self._to_bgr(message)
        if frame is None:
            now = time.monotonic()
            if now - self._warn_stamps[index] > 5.0:
                self._warn_stamps[index] = now
                self.get_logger().warning(
                    f"{self._topics[index]}: unsupported image encoding '{message.encoding}'"
                )
            return
        self._frames[index] = frame
        self._stamps[index] = time.monotonic()

    def _to_bgr(self, message):
        if message.height == 0 or message.width == 0:
            return None
        channels = 3
        expected = message.height * message.width * channels
        if len(message.data) < expected:
            return None
        try:
            if message.encoding == "bgr8":
                return np.frombuffer(message.data, dtype=np.uint8).reshape(
                    message.height, message.width, channels
                )
            if message.encoding == "rgb8":
                frame = np.frombuffer(message.data, dtype=np.uint8).reshape(
                    message.height, message.width, channels
                )
                return np.ascontiguousarray(frame[:, :, ::-1])
            if message.encoding == "mono8":
                gray = np.frombuffer(message.data, dtype=np.uint8).reshape(
                    message.height, message.width
                )
                return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        except (ValueError, TypeError):
            return None
        return None

    def _on_timer(self):
        if not self._topics:
            return
        if self._publisher.get_subscription_count() == 0:
            return

        now = time.monotonic()
        tiles = [self._render_tile(index, now) for index in range(len(self._topics))]
        rows = []
        for start in range(0, len(tiles), self._columns):
            row = tiles[start:start + self._columns]
            while len(row) < self._columns:
                row.append(self._blank_tile("", "", stale=False))
            rows.append(np.hstack(row))
        canvas = np.vstack(rows)

        ok, encoded = cv2.imencode(
            ".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), self._quality]
        )
        if not ok:
            self.get_logger().warning("JPEG encoding failed", throttle_duration_sec=5.0)
            return

        message = CompressedImage()
        message.header.stamp = self.get_clock().now().to_msg()
        message.format = "jpeg"
        message.data = encoded.tobytes()
        self._publisher.publish(message)

    def _render_tile(self, index, now):
        label = self._labels[index]
        frame = self._frames[index]
        if frame is None:
            return self._blank_tile(label, "waiting for topic", stale=False)
        stale = (now - self._stamps[index]) > self._stale_timeout
        tile = self._fit(frame)
        if stale:
            tile = cv2.convertScaleAbs(tile, alpha=0.35)
        self._draw_label(tile, label, stale)
        return tile

    def _fit(self, frame):
        tile_width, tile_height = self._tile_size
        height, width = frame.shape[:2]
        scale = min(tile_width / width, tile_height / height)
        resized = cv2.resize(
            frame,
            (max(1, int(width * scale)), max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
        tile = np.zeros((tile_height, tile_width, 3), dtype=np.uint8)
        offset_y = (tile_height - resized.shape[0]) // 2
        offset_x = (tile_width - resized.shape[1]) // 2
        tile[
            offset_y:offset_y + resized.shape[0],
            offset_x:offset_x + resized.shape[1],
        ] = resized
        return tile

    def _blank_tile(self, label, note, stale):
        tile = np.zeros((self._tile_size[1], self._tile_size[0], 3), dtype=np.uint8)
        if label:
            self._draw_label(tile, label, stale)
        if note:
            cv2.putText(
                tile,
                note,
                (12, self._tile_size[1] // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (180, 180, 180),
                2,
                cv2.LINE_AA,
            )
        return tile

    def _draw_label(self, tile, label, stale):
        cv2.rectangle(tile, (0, 0), (self._tile_size[0] - 1, self._tile_size[1] - 1), (70, 70, 70), 1)
        cv2.putText(tile, label, (14, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(tile, label, (14, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
        if stale:
            cv2.putText(
                tile,
                "STALE",
                (14, self._tile_size[1] - 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )


def main(args=None):
    rclpy.init(args=args)
    node = CameraMosaic()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
