# unitree_cam_view

Минимальный ROS 2-контур для просмотра камер Unitree G1: цветная RealSense
D435 и две USB-камеры Logitech. Из репозитория `~/unitree` взята только
сетевая/DDS-обвязка; локомоция, DEX3, LiDAR, SLAM/Nav2, MuJoCo и Gazebo
удалены.

```text
Робот (Ubuntu 22.04, ROS 2 Humble, CycloneDDS, ROS_DOMAIN_ID=0)
  RealSense D435 -- realsense2_camera -- /camera/camera/color/image_raw --+
  Logitech 1     -- usb_cam ----------- /logi_1/image_raw --------------+--> camera_mosaic
  Logitech 2     -- usb_cam ----------- /logi_2/image_raw --------------+         |
                                                                                  v
                        /cameras/mosaic/compressed (JPEG, один поток) -- DDS -->  Ноутбук
                                                                                  RViz в Docker
```

Мозаика собирается на бортовом компьютере, поэтому по Wi-Fi передаётся один
JPEG-поток вместо трёх сырых. Отдельные камеры тоже видны на ноутбуке, если
включить соответствующие Image-панели в RViz.

## Топики

| Топик | Тип | Где публикуется |
|---|---|---|
| `/camera/camera/color/image_raw` | `sensor_msgs/msg/Image` (rgb8) | робот, RealSense D435 |
| `/camera/camera/color/image_raw/compressed` | `sensor_msgs/msg/CompressedImage` | робот, D435 (для RViz) |
| `/logi_1/image_raw`, `/logi_1/image_raw/compressed` | `sensor_msgs/msg/Image` (rgb8) | робот, Logitech 1 |
| `/logi_2/image_raw`, `/logi_2/image_raw/compressed` | `sensor_msgs/msg/Image` (rgb8) | робот, Logitech 2 |
| `/cameras/mosaic/compressed` | `sensor_msgs/msg/CompressedImage` (jpeg) | робот, мозаика 3 камер |

## Состав репозитория

```text
docker/camera_viewer.Dockerfile      образ RViz (Humble + CycloneDDS) для ноутбука
docker/camera_robot.Dockerfile       образ камер (Humble + драйверы) для робота
docker/robot_entrypoint.sh           entrypoint робот-образа
scripts/build.sh                     сборка пакета на роботе (без Docker)
scripts/cam_env.sh                   окружение робота (Humble, CycloneDDS, domain 0)
scripts/dds_env.sh                   общий помощник CycloneDDS для скриптов
scripts/find_cameras.sh              by-id пути и форматы подключённых камер
scripts/robot_build.sh               сборка робот-образа
scripts/robot_up.sh                  запуск камер на роботе в Docker
scripts/viewer_build.sh              сборка Docker-образа на ноутбуке
scripts/view_cameras.sh              запуск RViz на ноутбуке
src/g1_cam_view/
  config/cameras.yaml                параметры двух Logitech
  launch/cameras.launch.py           драйверы камер + мозаика
  rviz/cameras.rviz                  профиль RViz
  scripts/camera_mosaic.py           сборка JPEG-мозаики
```

## Робот: подготовка

```bash
sudo apt update
sudo apt install -y \
  ros-humble-realsense2-camera \
  ros-humble-usb-cam \
  ros-humble-compressed-image-transport \
  ros-humble-rmw-cyclonedds-cpp \
  python3-opencv v4l-utils
```

Скопировать репозиторий на робота, собрать:

```bash
cd ~/unitree_cam_view
./scripts/build.sh
```

Для доступа к RealSense без root может понадобиться пакет udev-правил
`librealsense2-udev-rules` из репозитория librealsense (см. раздел
«Диагностика»).

## Робот: настройка камер (необязательно)

RealSense драйвер находит сам, а Logitech launch ищет автоматически: сканирует
`/dev/v4l/by-id/`, берёт ссылки `usb-046d_*-video-index0` (Logitech по USB-ID
`046d`), сортирует и назначает первые две на `logi_1` и `logi_2`. Камеры можно
подключать в любом порядке — привязка к by-id стабильна. Назначение видно в
логе запуска:

```text
[g1_cam_view] logi_1: auto camera /dev/v4l/by-id/usb-046d_...-video-index0
[g1_cam_view] logi_2: auto camera /dev/v4l/by-id/usb-046d_...-video-index0
```

Ручной конфиг нужен только если:

- важно, какая физическая камера попадёт в `logi_1`, а какая в `logi_2`;
- камеры не Logitech (поменяйте `G1_CAM_LOGI_FILTER`, по умолчанию `usb-046d`);
- ссылки `/dev/v4l/by-id` нет (задайте пути вручную или каталог
  через `G1_CAM_DEVICE_DIR`).

Тогда выполнить `./scripts/find_cameras.sh` и вписать пути в
`src/g1_cam_view/config/cameras.yaml` вместо `CHANGE_ME`; указанные в конфиге
пути имеют приоритет над авто-обнаружением:

```yaml
/logi_1/usb_cam:
  ros__parameters:
    video_device: "/dev/v4l/by-id/usb-046d_Brio_505_XXXXXXXX-video-index0"
```

Разрешение и частоту обеих Logitech задают там же (`image_width`,
`image_height`, `framerate`, `pixel_format`). Если камера не умеет MJPEG,
заменить `mjpeg2rgb` на `yuyv2rgb`.

## Робот: запуск

В каждом новом терминале робота:

```bash
cd ~/unitree_cam_view
export G1_CAM_PEERS=10.0.88.165:7410
source scripts/cam_env.sh <внешний-интерфейс> [внутренний-интерфейс]
ros2 launch g1_cam_view cameras.launch.py
```

Аргументы запуска:

| Аргумент | По умолчанию | Значение |
|---|---|---|
| `realsense` | `true` | включить RealSense D435 |
| `logi_1`, `logi_2` | `true` | включить соответствующую Logitech |
| `mosaic` | `true` | публиковать `/cameras/mosaic/compressed` |
| `serial_no` | `""` | серийник RealSense, если подключено несколько |
| `device_type` | `""` | фильтр модели RealSense, например `d435` при нескольких камерах |
| `color_profile` | `640x480x15` | профиль цвета D435 (`ШxВxЧД`) |
| `mosaic_fps` | `10.0` | частота мозаики |
| `mosaic_quality` | `80` | JPEG quality мозаики |
| `tile_width`, `tile_height` | `640`, `480` | размер плитки одной камеры |
| `columns` | `3` | плиток в ряд |

Дополнительно авто-обнаружение настраивается переменными окружения:
`G1_CAM_DEVICE_DIR` (по умолчанию `/dev/v4l/by-id`) и `G1_CAM_LOGI_FILTER`
(по умолчанию `usb-046d`).

Пример только с RealSense:

```bash
ros2 launch g1_cam_view cameras.launch.py logi_1:=false logi_2:=false
```

Проверка на роботе:

```bash
ros2 topic list | grep -E 'image|mosaic'
timeout 8 ros2 topic hz /camera/camera/color/image_raw
timeout 8 ros2 topic hz /logi_1/image_raw
timeout 8 ros2 topic hz /cameras/mosaic/compressed
```

## Робот: запуск в Docker (альтернатива)

Если не хочется ставить драйверы и пакет на хоста робота, тот же стек
запускается в контейнере. На хосте нужен только Docker.

```bash
cd ~/unitree_cam_view
./scripts/robot_build.sh

export G1_CAM_PEERS=10.0.88.165:7410
./scripts/robot_up.sh wlxfc23cd952598 enP8p1s0
```

`robot_up.sh` сам собирает CycloneDDS URI, пробрасывает USB-устройства
(`/dev` + cgroup-правила для video/USB), монтирует
`src/g1_cam_view/config/cameras.yaml` (плюс работает авто-обнаружение Logitech)
и запускает `cameras.launch.py`. Правки `cameras.yaml` применяются без
пересборки образа, остального — требуют `robot_build.sh`.

Дополнительные аргументы launch передаются через `G1_CAM_LAUNCH_ARGS`:

```bash
G1_CAM_LAUNCH_ARGS="logi_1:=false logi_2:=false" ./scripts/robot_up.sh
```

Полезно знать:

- образ можно собрать на ноутбуке и перенести:
  `docker save unitree-g1-camera-robot:humble | ssh unitree@10.0.88.180 docker load`;
- если камеры не видны в контейнере, запустить с `--privileged -v /dev:/dev`
  вместо `--device-cgroup-rule` (и проверить udev-правила RealSense на хосте);
- интерфейсы и peer ноутбука задаются так же, как в `cam_env.sh`
  (`G1_CAM_NETWORK_INTERFACE(S)`, `G1_CAM_PEERS`), аргументами или переменными;
- камеры публикуются в тот же domain 0, что и штатный Unitree DDS на хосте.

## Ноутбук: просмотр

На ноутбуке ROS не установлен, всё работает в Docker (Humble + CycloneDDS).
Один раз собрать образ:

```bash
cd ~/unitree_cam_view
./scripts/viewer_build.sh
```

Запуск RViz:

```bash
./scripts/view_cameras.sh
```

Если у ноутбука несколько активных интерфейсов, указать нужный и адрес робота
явно:

```bash
G1_CAM_NETWORK_INTERFACE=wlp3s0 \
G1_CAM_PEERS=10.0.88.180:7410 \
  ./scripts/view_cameras.sh
```

По умолчанию включена панель `Mosaic (D435 + 2x Logi)`. Отдельные камеры:
в дереве `Displays` включить `RealSense D435 color`, `Logitech 1`, `Logitech 2`
(они подписаны на compressed-топики). Панели изображений в RViz можно
перетаскивать; расположение по умолчанию — вкладки.

Флаг `RVIZ_GL=hardware` переключает RViz на GPU (`/dev/dri`), по умолчанию
используется программный рендеринг.

## Сеть и DDS

- Робот и ноутбук должны быть в одной L2-сети; используется `ROS_DOMAIN_ID=0`
  и CycloneDDS, как в `~/unitree`; смешивать Humble и Jazzy в одном домене
  нельзя.
- `cam_env.sh` принимает интерфейсы робота (внутренний Unitree и внешний) и
  адрес ноутбука `G1_CAM_PEERS=<ip>:7410`. Контейнер зрителя занимает
  participant index 0, то есть UDP-порт 7410.
- Камеры живут в том же домене, что и штатный Unitree DDS. Весь видеотрафик
  сжат, наружу уходит только мозаика, но при проблемах с управлением роботом
  останавливайте просмотр.
- Одновременно держите запущенным только один контейнер зрителя.

## Диагностика

- **`ros2 topic hz` на роботе молчит.** Для Logitech смотреть строку
  `[g1_cam_view] logi_N: ...` в логе запуска: `camera not found` означает, что
  нет ссылки `usb-046d_*-video-index0` (проверить `find_cameras.sh` и
  `G1_CAM_LOGI_FILTER`); `Device specified is not available` — камера занята
  другим процессом (`fuser -v /dev/videoX`) или путь устарел. Для `usb_cam`
  смотреть лог: он печатает поддерживаемые форматы; при неверном
  `pixel_format` узел падает.
- **RealSense не открывается.** Проверить `lsusb`, кабель USB 3 и udev-правила
  librealsense; при нескольких камерах задать `serial_no:=...`, иначе драйвер
  возьмёт первую.
- **В RViz пусто.** Убедиться, что на роботе идут `/cameras/mosaic/compressed`
  (или compressed-топик отдельной камеры), что установлен
  `ros-humble-compressed-image-transport` и совпадают `G1_CAM_PEERS`. Все
  Image-панели подписаны с QoS Best Effort — менять на Reliable не нужно.
- **`failed to create unicast sockets ... ports 7410, 7411`.** Уже запущен
  другой зритель (participant index 0 может быть только один). Скрипт это
  проверяет и подсказывает команду; принудительно заменить:
  `./scripts/view_cameras.sh --force`. Для робота аналогично:
  `./scripts/robot_up.sh --force`.
- **Низкий FPS / рывки по Wi-Fi.** Уменьшить `mosaic_fps`, разрешение камер или
  `mosaic_quality`. Сырые топики (`.../image_raw`) по Wi-Fi не смотреть:
  только `/compressed` или мозаику.
- **Ошибка `DISPLAY is unset`.** Запускать `view_cameras.sh` из графической
  сессии ноутбука.

## Что вырезано из ~/unitree

Пакеты `g1_bridge`, `g1_gazebo`, `g1_mujoco`, сообщения `unitree_hg` и
`unitree_api`, `unitree_ros2.repos`, локомоция и watchdog, DEX3-кисти,
Livox Mid-360, SLAM/Nav2, симуляторы и их RViz-профили, скрипты hardware
checks. Из общей обвязки сохранены схема CycloneDDS/domain 0 и запуск зрителя
в Docker. Переменные окружения переименованы в `G1_CAM_*`, чтобы не
пересекаться с `~/unitree`.
