# CRSF-ETH Bridge

Двунаправленный UDP мост для протокола CRSF (Crossfire), позволяющий передавать данные между пультом и TX модулем через сеть Ethernet/WiFi.

## Архитектура

```
[Пульт] ←→ UART ←→ [Bridge A] ←→ UDP ←→ [Bridge B] ←→ UART ←→ [TX модуль]
```

- **Bridge A (Simple Bridge)** - простой мост для подключения к пульту, пересылает данные без парсинга
- **Bridge B (Smart Bridge)** - умный мост для подключения к TX модулю, парсит CRSF фреймы и предоставляет доступ к телеметрии

## Компоненты проекта

### Основные файлы:

1. **`crsf_protocol.py`** - базовые классы для работы с CRSF протоколом
2. **`half_duplex_uart.py`** - управление half-duplex UART через GPIO (SN74LVC1T45)
3. **`udp_transport.py`** - UDP транспорт для передачи данных между мостами
4. **`bridge_a.py`** - простой мост (подключение к пульту)
5. **`bridge_b.py`** - умный мост (подключение к TX модулю)

## Аппаратные требования

### Raspberry Pi 5 для каждого моста:
- GPIO для управления направлением UART
- Микросхема SN74LVC1T45 для half-duplex UART
- Подключение к telemetry UART пульта/TX модуля

### Схема подключения SN74LVC1T45:

**Направление TX (DIR = HIGH):**
- SN74LVC1T45 #1: A→B (Pi TX → TBS модуль)
- SN74LVC1T45 #2: отключен (высокий импеданс)

**Направление RX (DIR = LOW):**
- SN74LVC1T45 #1: отключен (высокий импеданс)  
- SN74LVC1T45 #2: A→B (TBS модуль → Pi RX)

## Установка

### Зависимости:
```bash
pip install pyserial RPi.GPIO
```

### Настройка UART на Raspberry Pi:
```bash
# Включить UART в /boot/config.txt
echo "enable_uart=1" | sudo tee -a /boot/config.txt
echo "dtoverlay=disable-bt" | sudo tee -a /boot/config.txt

# Отключить консоль на UART
sudo systemctl disable hciuart
sudo systemctl stop serial-getty@ttyAMA0.service
sudo systemctl disable serial-getty@ttyAMA0.service
```

## Использование

### Bridge A (Простой мост - подключение к пульту):

```bash
python3 bridge_a.py \
    --uart-port /dev/serial0 \
    --uart-baudrate 416666 \
    --dir-pin 18 \
    --udp-local-port 5000 \
    --udp-remote-host 192.168.1.100 \
    --udp-remote-port 5001
```

### Bridge B (Умный мост - подключение к TX модулю):

```bash
python3 bridge_b.py \
    --uart-port /dev/serial0 \
    --uart-baudrate 416666 \
    --dir-pin 18 \
    --udp-local-port 5001 \
    --udp-remote-host 192.168.1.101 \
    --udp-remote-port 5000
```

## Функции Bridge B (Smart Bridge)

### Парсинг телеметрии:
- **Link Statistics** - качество связи, RSSI, SNR
- **Battery Sensor** - напряжение, ток, емкость, проценты заряда
- **Attitude** - углы ориентации (pitch, roll, yaw)
- **Flight Mode** - текущий режим полета
- **GPS** - координаты, скорость, высота

### Программный интерфейс:

```python
from bridge_b import SmartBridge

# Создание моста
bridge = SmartBridge(
    uart_port='/dev/serial0',
    uart_baudrate=416666,
    dir_pin=18,
    udp_local_port=5001,
    udp_remote_host='192.168.1.101',
    udp_remote_port=5000
)

# Callback для обработки определенных типов фреймов
def on_battery_data(frame):
    # Обработка данных батареи
    print("Получены данные батареи")

bridge.set_frame_callback(CRSFFrameType.BATTERY_SENSOR, on_battery_data)

# Запуск моста
with bridge:
    # Получение телеметрии
    telemetry = bridge.get_telemetry_data()
    
    if telemetry['link_stats']:
        print(f"Link Quality: {telemetry['link_stats']['uplink_quality']}%")
        print(f"RSSI: {telemetry['link_stats']['uplink_rssi_1']} dBm")
        
    if telemetry['battery']:
        print(f"Battery: {telemetry['battery']['voltage']:.2f}V")
        print(f"Current: {telemetry['battery']['current']:.2f}A")
        print(f"Remaining: {telemetry['battery']['remaining_percent']}%")
```

## Параметры командной строки

### Общие параметры:
- `--uart-port` - UART порт (по умолчанию: `/dev/serial0`)
- `--uart-baudrate` - скорость UART (по умолчанию: `416666`)
- `--dir-pin` - GPIO пин управления направлением (по умолчанию: `18`)
- `--udp-local-port` - локальный UDP порт
- `--udp-remote-host` - IP адрес удаленного моста
- `--udp-remote-port` - UDP порт удаленного моста

## Статистика и мониторинг

Оба моста выводят статистику каждые 30 секунд:
- Количество переданных/полученных пакетов и байт
- Время последнего приема данных
- Состояние UDP соединения
- Для Smart Bridge: типы фреймов и последняя телеметрия

## Отладка

### Логирование:
- Bridge A: простое логирование передачи данных
- Bridge B: детальное логирование с парсингом фреймов

### Проверка соединения:
- UDP heartbeat пакеты каждые 5 секунд
- Автоматическое определение состояния соединения
- Статистика ошибок парсинга

## Расширение функциональности

### Добавление новых типов фреймов:
1. Добавить константу в `CRSFFrameType` в `crsf_protocol.py`
2. Добавить обработку в `_extract_telemetry_data()` в `bridge_b.py`
3. Установить callback для нового типа фрейма

### Пример добавления нового типа телеметрии:
```python
# В crsf_protocol.py
class CRSFFrameType(IntEnum):
    # ... существующие типы
    CUSTOM_SENSOR = 0x50

# В bridge_b.py  
def _extract_telemetry_data(self, frame):
    # ... существующая обработка
    elif frame_type == CRSFFrameType.CUSTOM_SENSOR:
        # Обработка пользовательского сенсора
        self.telemetry_data['custom'] = parse_custom_data(frame.payload)
```