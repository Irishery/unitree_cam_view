# unitree_cam_view

Минимальный ROS 2-контур для просмотра трёх USB-камер Logitech на Unitree G1.
Из репозитория `~/unitree` взята только сетевая/DDS-обвязка; локомоция, DEX3,
LiDAR, SLAM/Nav2, MuJoCo и Gazebo удалены. RealSense D435 пока исключена из
приложения (её можно вернуть как отдельный источник кадров).

```text
Робот (Ubuntu 22.04, ROS 2 Humble, CycloneDDS, ROS_DOMAIN_ID=0)
  Logitech 1 -- usb_cam -- /logi_1/image_raw --+
  Logitech 2 -- usb_cam -- /logi_2/image_raw --+--> camera_mosaic --> /cameras/mosaic/compressed
  Logitech 3 -- usb_cam -- /logi_3/image_raw --+                             |
                                                        DDS (Wi-Fi) ---------+
                                                              |
                                                      Ноутбук: RViz в Docker
```

Мозаика собирается на бортовом компьютере, поэтому по Wi-Fi передаётся один
JPEG-поток вместо трёх сырых. Отдельные камеры тоже видны на ноутбуке, если
включить соответствующие Image-панели в RViz.

## Топики

| Топик | Тип | Где публикуется |
|---|---|---|
| `/logi_1/image_raw`, `/logi_1/image_raw/compressed` | `sensor_msgs/msg/Image` (rgb8) | робот, Logitech 1 |
| `/logi_2/image_raw`, `/logi_2/image_raw/compressed` | `sensor_msgs/msg/Image` (rgb8) | робот, Logitech 2 |
| `/logi_3/image_raw`, `/logi_3/image_raw/compressed` | `sensor_msgs/msg/Image` (rgb8) | робот, Logitech 3 |
| `/cameras/mosaic/compressed` | `sensor_msgs/msg/CompressedImage` (jpeg) | робот, мозаика найденных камер |

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
  config/cameras.yaml                параметры трёх Logitech
  launch/cameras.launch.py           драйверы камер + мозаика
  rviz/cameras.rviz                  профиль RViz
  scripts/camera_mosaic.py           сборка JPEG-мозаики
```

## Робот: подготовка

```bash
sudo apt update
sudo apt install -y \
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

## Робот: настройка камер (необязательно)

Launch сам ищет Logitech: сканирует `/dev/v4l/by-id/`, берёт ссылки
`usb-046d_*-video-index0` (Logitech по USB-ID `046d`), сортирует и назначает
первые три на `logi_1`, `logi_2` и `logi_3`. Камеры можно подключать в любом
порядке — привязка к by-id стабильна. Назначение видно в логе запуска:

```text
[g1_cam_view] logi_1: auto camera /dev/v4l/by-id/usb-046d_...-video-index0 -> /dev/video6
[g1_cam_view] logi_2: auto camera /dev/v4l/by-id/usb-046d_...-video-index0 -> /dev/video7
[g1_cam_view] logi_3: auto camera /dev/v4l/by-id/usb-046d_...-video-index0 -> /dev/video8
```

Узлы `usb_cam` запускаются через обёртку `usb_cam_stable.py` с
`respawn=true`: при USB-сбое (`Select timeout, exiting...`) поток поднимается
сам, а путь камеры перерезолвится из by-id — если камера переподключилась и
получила другой `/dev/videoN`, она всё равно вернётся.

Ручной конфиг нужен только если:

- важно, какая физическая камера попадёт в `logi_1`/`logi_2`/`logi_3`;
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

Разрешение и частоту каждой Logitech задают там же (`image_width`,
`image_height`, `framerate`, `pixel_format`). По умолчанию камеры работают в
640×360@10 — это меньше грузит USB, чем 640×480@15. Мозаика по умолчанию
складывает те же 640×360 на камеру с частотой 8 Гц и JPEG quality 70. Если
камера не умеет MJPEG, заменить `mjpeg2rgb` на `yuyv2rgb`. Поле
`v4l2_controls` применяется через `v4l2-ctl` перед стартом узла и при каждом
`respawn`; по умолчанию у всех трёх камер стоит
`exposure_dynamic_framerate=0`, чтобы Brio не снижала FPS в темноте.

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
| `logi_1`, `logi_2`, `logi_3` | `true` | включить соответствующую Logitech |
| `mosaic` | `true` | публиковать `/cameras/mosaic/compressed` |
| `mosaic_fps` | `8.0` | частота мозаики |
| `mosaic_quality` | `70` | JPEG quality мозаики |
| `tile_width`, `tile_height` | `640`, `360` | размер плитки одной камеры |
| `columns` | `3` | плиток в ряд |

Дополнительно авто-обнаружение настраивается переменными окружения:
`G1_CAM_DEVICE_DIR` (по умолчанию `/dev/v4l/by-id`) и `G1_CAM_LOGI_FILTER`
(по умолчанию `usb-046d`).

Проверка на роботе:

```bash
ros2 topic list | grep -E 'image|mosaic'
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
G1_CAM_LAUNCH_ARGS="logi_1:=false logi_2:=false logi_3:=false" ./scripts/robot_up.sh
```

Полезно знать:

- образ можно собрать на ноутбуке и перенести:
  `docker save unitree-g1-camera-robot:humble | ssh unitree@10.0.88.180 docker load`;
- если камеры не видны в контейнере, запустить с `--privileged -v /dev:/dev`
  вместо `--device-cgroup-rule`;
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
явно (без порта, чтобы discovery дошёл до всех процессов робота):

```bash
G1_CAM_NETWORK_INTERFACE=wlp3s0 \
G1_CAM_PEERS=10.0.69.107 \
  ./scripts/view_cameras.sh
```

По умолчанию включена панель `Mosaic (3x Logi)`. Отдельные камеры:
в дереве `Displays` включить `Logitech 1`, `Logitech 2`, `Logitech 3`
(они подписаны на compressed-топики). Панели изображений в RViz можно
перетаскивать; расположение по умолчанию — вкладки.

Флаг `RVIZ_GL=hardware` переключает RViz на GPU (`/dev/dri`), по умолчанию
используется программный рендеринг.

### Второй зритель на другом компьютере

Смотреть можно с нескольких машин одновременно: у каждой свой контейнер, и
participant index 0 может быть занят только один раз **на каждом компьютере**
(поэтому два RViz на одной машине не запускаются).

На втором компьютере (Linux + Docker) скопировать репозиторий, собрать образ
или перенести готовый, и запустить с адресом робота **без порта**:

```bash
./scripts/viewer_build.sh
# либо на первом ноутбуке:
# docker save unitree-g1-camera-viewer:humble | ssh user@pc2 docker load

G1_CAM_NETWORK_INTERFACE=<интерфейс> G1_CAM_PEERS=<ip-робота> ./scripts/view_cameras.sh
```

Робот менять не обязательно: `G1_CAM_PEERS=<ip-робота>` без порта отправит
discovery на все participant-порты робота, и обратный announce придёт сам.
Если сеть режет такой «веер» UDP, добавьте адрес второго зрителя в пиры
робота (они перечисляются через пробел):

```bash
# робот
export G1_CAM_PEERS="10.0.69.163:7410 10.0.69.200:7410"
./scripts/robot_up.sh wlxfc23cd952598
```

Каждый зритель получает свою unicast-копию мозаики (~0.5–1 МБ/с), повторная
JPEG-кодировка на роботе не выполняется. Если в сети работает multicast, пиры
не нужны вообще (`G1_CAM_PEERS=` на всех машинах).

## Сеть и DDS

- Робот и ноутбук должны быть в одной L2-сети; используется `ROS_DOMAIN_ID=0`
  и CycloneDDS, как в `~/unitree`; смешивать Humble и Jazzy в одном домене
  нельзя.
- `cam_env.sh` и `robot_up.sh` принимают интерфейсы робота (внешний и, при
  желании, внутренний Unitree) и список пиров в `G1_CAM_PEERS`. Пир вида
  `<ip-зрителя>:7410` достаёт только participant index 0 зрителя (он там
  фиксирован); пир `<ip-робота>` без порта опрашивает все participant-порты
  робота, поэтому для направления «ноутбук → робот» порт лучше не указывать.
- Камеры живут в том же домене, что и штатный Unitree DDS. Весь видеотрафик
  сжат, наружу уходит только мозаика, но при проблемах с управлением роботом
  останавливайте просмотр.
- На одном компьютере — только один контейнер зрителя; на разных компьютерах
  их может быть сколько угодно (см. «Второй зритель»).

## Диагностика

- **`ros2 topic hz` на роботе молчит.** Для Logitech смотреть строку
  `[g1_cam_view] logi_N: ...` в логе запуска: `camera not found` означает, что
  нет ссылки `usb-046d_*-video-index0` (проверить `find_cameras.sh` и
  `G1_CAM_LOGI_FILTER`); `Device specified is not available` — камера занята
  другим процессом (`fuser -v /dev/videoX`) или путь устарел. Для `usb_cam`
  смотреть лог: он печатает поддерживаемые форматы; при неверном
  `pixel_format` узел падает.
- **Одна из камер пропала / `Select timeout, exiting...`.** uvc-поток сорвался
  (питание/контакт USB). Узел перезапустится сам через `respawn`; если
  повторяется — переставить камеру в другой порт, использовать USB-хаб с
  питанием, снизить `framerate` или разрешение. Сообщения
  `unknown control '...auto'` от Brio 505 безвредны — usb_cam 0.8.1 пробует
  старые имена V4L2-контролов.
- **Камера лагает или плитка `STALE`.** `STALE` означает, что кадров нет
  дольше 2 с: либо узел упал (смотри `process has died` в логе), либо камера
  перестала отдавать поток. Проверить частоту:
  `timeout 8 ros2 topic hz /logi_1/image_raw`. Если частота низкая в тёмном
  помещении — виноват `exposure_dynamic_framerate` (в конфиге он выключен) или
  нехватка света. Если поток обрывается — три камеры не тянут по питанию/USB:
  хаб с питанием, разные порты/контроллеры, `framerate` 10 вместо 15.
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

RealSense D435 исключена из этой версии: драйвер и топики убраны из launch,
образа и профиля RViz, чтобы камера оставалась свободной для других
приложений. Вернуть её можно как отдельный источник кадров и добавить его тему
в мозаику.
