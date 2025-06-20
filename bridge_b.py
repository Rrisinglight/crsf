#!/usr/bin/env python3
"""
Bridge B - Умный мост между UDP и TX модулем
Подключается к TX модулю по UART, парсит CRSF фреймы и предоставляет доступ к Payload
"""

import time
import threading
import argparse
from typing import Dict, List, Optional
from dual_gpio_uart import DualGPIO_UART
from udp_transport import BidirectionalUDPTransport
from crsf_protocol import CRSFParser, CRSFFrame, CRSFFrameType, create_heartbeat_frame, create_ping_frame

class SmartBridge:
    """Умный мост с парсингом CRSF протокола"""
    
    def __init__(self, uart_port: str, uart_baudrate: int, tx_en_pin: int, rx_en_pin: int,
                 udp_local_port: int, udp_remote_host: str, udp_remote_port: int,
                 debug: bool = False):
        
        self.debug_mode = debug
        self.uart = DualGPIO_UART(
            port=uart_port,
            baudrate=uart_baudrate,
            tx_en_pin=tx_en_pin,
            rx_en_pin=rx_en_pin
        )
        self.uart.set_data_callback(self._on_uart_data)

        self.udp_transport = BidirectionalUDPTransport(
            udp_local_port, udp_remote_host, udp_remote_port
        )
        
        # CRSF парсеры
        self.uart_parser = CRSFParser()
        self.udp_parser = CRSFParser()
        
        # Статистика и состояние
        self.stats = {
            'uart_frames_rx': 0,
            'uart_frames_tx': 0,
            'udp_frames_rx': 0,
            'udp_frames_tx': 0,
            'uart_bytes_rx': 0,
            'uart_bytes_tx': 0,
            'udp_bytes_rx': 0,
            'udp_bytes_tx': 0,
            'start_time': time.time(),
            'last_uart_frame': 0,
            'last_udp_frame': 0,
            'frame_types_uart_rx': {},
            'frame_types_udp_rx': {},
            'parse_errors': 0
        }
        
        # Данные от различных сенсоров (последние полученные)
        self.telemetry_data = {
            'link_stats': None,
            'battery': None,
            'gps': None,
            'attitude': None,
            'flight_mode': None,
            'last_update': {}
        }
        
        # Потоки
        self.stats_thread = None
        self.heartbeat_thread = None
        
        # Callbacks для пользовательской обработки
        self.frame_callbacks = {}
        
    def start(self):
        """Запуск умного моста"""
        print("Запуск Smart Bridge (Bridge B)...")
        
        # Запуск UART
        self.uart.start()
        
        # Запуск UDP транспорта
        self.udp_transport.set_data_callback(self._on_udp_data)
        self.udp_transport.start()
        
        # Запуск потоков
        self.stats_thread = threading.Thread(target=self._stats_loop, daemon=True)
        self.stats_thread.start()
        
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        
        print("Smart Bridge запущен")
        print(f"UART: {self.uart.port} @ {self.uart.baudrate}, TX_EN pin: {self.uart.tx_en_pin}, RX_EN pin: {self.uart.rx_en_pin}")
        print(f"UDP: {self.udp_transport.transport.local_port} -> {self.udp_transport.transport.remote_host}:{self.udp_transport.transport.remote_port}")
        
    def stop(self):
        """Остановка умного моста"""
        print("Остановка Smart Bridge...")
        self.udp_transport.stop()
        self.uart.stop()
        print("Smart Bridge остановлен")
        
    def set_frame_callback(self, frame_type: CRSFFrameType, callback):
        """Установка callback для определенного типа фрейма"""
        self.frame_callbacks[frame_type] = callback
        
    def _on_uart_data(self, data: bytes):
        """Обработчик данных от UART - парсим и пересылаем в UDP"""
        if len(data) > 0:
            self.stats['uart_bytes_rx'] += len(data)
            
            # Парсим CRSF фреймы
            frames = self.uart_parser.add_data(data)
            
            for frame in frames:
                self._process_uart_frame(frame)
                
                # Пересылаем в UDP
                frame_data = frame.build()
                success = self.udp_transport.send_crsf_data(frame_data)
                if success:
                    self.stats['udp_frames_tx'] += 1
                    self.stats['udp_bytes_tx'] += len(frame_data)
                    
            if not frames and len(data) > 0:
                # Если не удалось распарсить, пересылаем как есть
                self.udp_transport.send_crsf_data(data)
                
    def _on_udp_data(self, data: bytes):
        """Обработчик данных от UDP - парсим и пересылаем в UART"""
        if len(data) > 0:
            if self.debug_mode:
                hex_data = ' '.join(f'{b:02X}' for b in data)
                print(f"[DEBUG RECV] ({len(data)} bytes): {hex_data}")

            self.stats['udp_bytes_rx'] += len(data)
            
            # Парсим CRSF фреймы
            frames = self.udp_parser.add_data(data)
            
            for frame in frames:
                self._process_udp_frame(frame)
                
                # Пересылаем в UART
                frame_data = frame.build()
                success = self.uart.send(frame_data)
                if success:
                    self.stats['uart_frames_tx'] += 1
                    self.stats['uart_bytes_tx'] += len(frame_data)
                    
            if not frames and len(data) > 0:
                # Если не удалось распарсить, пересылаем как есть
                self.uart.send(data)
                
    def _process_uart_frame(self, frame: CRSFFrame):
        """Обработка фрейма от UART (телеметрия от TX модуля)"""
        self.stats['uart_frames_rx'] += 1
        self.stats['last_uart_frame'] = time.time()
        
        # Статистика по типам фреймов
        frame_type = frame.frame_type
        if frame_type not in self.stats['frame_types_uart_rx']:
            self.stats['frame_types_uart_rx'][frame_type] = 0
        self.stats['frame_types_uart_rx'][frame_type] += 1
        
        # Извлечение данных телеметрии
        self._extract_telemetry_data(frame)
        
        # Пользовательские callbacks
        if frame_type in self.frame_callbacks:
            try:
                self.frame_callbacks[frame_type](frame)
            except Exception as e:
                print(f"Ошибка в callback для фрейма {frame_type:02X}: {e}")
                
        # Логирование для отладки
        print(f"UART->UDP: {frame}")
        
    def _process_udp_frame(self, frame: CRSFFrame):
        """Обработка фрейма от UDP (команды от пульта)"""
        self.stats['udp_frames_rx'] += 1
        self.stats['last_udp_frame'] = time.time()
        
        # Статистика по типам фреймов
        frame_type = frame.frame_type
        if frame_type not in self.stats['frame_types_udp_rx']:
            self.stats['frame_types_udp_rx'][frame_type] = 0
        self.stats['frame_types_udp_rx'][frame_type] += 1
        
        # Пользовательские callbacks
        if frame_type in self.frame_callbacks:
            try:
                self.frame_callbacks[frame_type](frame)
            except Exception as e:
                print(f"Ошибка в callback для фрейма {frame_type:02X}: {e}")
                
        # Логирование для отладки
        print(f"UDP->UART: {frame}")
        
    def _extract_telemetry_data(self, frame: CRSFFrame):
        """Извлечение данных телеметрии из фрейма"""
        frame_type = frame.frame_type
        current_time = time.time()
        
        try:
            if frame_type == CRSFFrameType.LINK_STATISTICS and len(frame.payload) >= 10:
                # Статистика линка связи
                payload = frame.payload
                self.telemetry_data['link_stats'] = {
                    'uplink_rssi_1': -payload[0] if payload[0] > 0 else None,
                    'uplink_rssi_2': -payload[1] if payload[1] > 0 else None,
                    'uplink_quality': payload[2],
                    'uplink_snr': payload[3] if payload[3] < 128 else payload[3] - 256,
                    'antenna': payload[4],
                    'rf_mode': payload[5],
                    'tx_power': payload[6],
                    'downlink_rssi': -payload[7] if payload[7] > 0 else None,
                    'downlink_quality': payload[8],
                    'downlink_snr': payload[9] if payload[9] < 128 else payload[9] - 256,
                }
                self.telemetry_data['last_update']['link_stats'] = current_time
                
            elif frame_type == CRSFFrameType.BATTERY_SENSOR and len(frame.payload) >= 8:
                # Данные батареи
                payload = frame.payload
                voltage = int.from_bytes(payload[0:2], byteorder='big') / 100.0  # В вольтах
                current = int.from_bytes(payload[2:4], byteorder='big', signed=True) / 100.0  # В амперах
                capacity = int.from_bytes(payload[4:7], byteorder='big')  # мАч
                remaining = payload[7]  # проценты
                
                self.telemetry_data['battery'] = {
                    'voltage': voltage,
                    'current': current,
                    'capacity_used': capacity,
                    'remaining_percent': remaining
                }
                self.telemetry_data['last_update']['battery'] = current_time
                
            elif frame_type == CRSFFrameType.ATTITUDE and len(frame.payload) >= 6:
                # Данные ориентации
                payload = frame.payload
                pitch = int.from_bytes(payload[0:2], byteorder='big', signed=True) / 10000.0
                roll = int.from_bytes(payload[2:4], byteorder='big', signed=True) / 10000.0
                yaw = int.from_bytes(payload[4:6], byteorder='big', signed=True) / 10000.0
                
                self.telemetry_data['attitude'] = {
                    'pitch': pitch,
                    'roll': roll,
                    'yaw': yaw
                }
                self.telemetry_data['last_update']['attitude'] = current_time
                
            elif frame_type == CRSFFrameType.FLIGHT_MODE:
                # Режим полета
                try:
                    flight_mode = frame.payload.decode('utf-8').rstrip('\x00')
                    self.telemetry_data['flight_mode'] = flight_mode
                    self.telemetry_data['last_update']['flight_mode'] = current_time
                except:
                    pass
                    
        except Exception as e:
            print(f"Ошибка извлечения телеметрии из фрейма {frame_type:02X}: {e}")
            
    def get_telemetry_data(self) -> dict:
        """Возвращает последние данные телеметрии"""
        return self.telemetry_data.copy()
        
    def get_stats(self) -> dict:
        """Возвращает статистику моста"""
        return self.stats.copy()
        
    def _heartbeat_loop(self):
        """Цикл отправки heartbeat пакетов в TX модуль"""
        while self.uart.is_running:
            # Отправляем heartbeat каждые 10 секунд
            heartbeat = create_heartbeat_frame()
            heartbeat_data = heartbeat.build()
            self.uart.send(heartbeat_data)
            
            time.sleep(10.0)
            
    def _stats_loop(self):
        """Цикл вывода статистики"""
        while self.uart.is_running:
            time.sleep(30)  # Статистика каждые 30 секунд
            self._print_stats()
            
    def _print_stats(self):
        """Вывод подробной статистики"""
        uptime = time.time() - self.stats['start_time']
        uart_frame_ago = time.time() - self.stats['last_uart_frame'] if self.stats['last_uart_frame'] > 0 else uptime
        udp_frame_ago = time.time() - self.stats['last_udp_frame'] if self.stats['last_udp_frame'] > 0 else uptime
        
        udp_stats = self.udp_transport.get_stats()
        
        print("\n" + "="*70)
        print("SMART BRIDGE СТАТИСТИКА")
        print("="*70)
        print(f"Время работы: {uptime:.1f} сек")
        print(f"UART RX: {self.stats['uart_frames_rx']} фреймов, {self.stats['uart_bytes_rx']} байт")
        print(f"UART TX: {self.stats['uart_frames_tx']} фреймов, {self.stats['uart_bytes_tx']} байт")
        print(f"UDP RX:  {self.stats['udp_frames_rx']} фреймов, {self.stats['udp_bytes_rx']} байт")
        print(f"UDP TX:  {self.stats['udp_frames_tx']} фреймов, {self.stats['udp_bytes_tx']} байт")
        print(f"Последний UART фрейм: {uart_frame_ago:.1f} сек назад")
        print(f"Последний UDP фрейм: {udp_frame_ago:.1f} сек назад")
        print(f"UDP соединение: {'активно' if udp_stats['connection_active'] else 'неактивно'}")
        
        # Типы фреймов
        if self.stats['frame_types_uart_rx']:
            print("\nТипы фреймов UART RX:")
            for frame_type, count in self.stats['frame_types_uart_rx'].items():
                print(f"  0x{frame_type:02X}: {count}")
                
        if self.stats['frame_types_udp_rx']:
            print("\nТипы фреймов UDP RX:")
            for frame_type, count in self.stats['frame_types_udp_rx'].items():
                print(f"  0x{frame_type:02X}: {count}")
                
        # Телеметрия
        print("\nПоследняя телеметрия:")
        for data_type, data in self.telemetry_data.items():
            if data_type != 'last_update' and data is not None:
                age = time.time() - self.telemetry_data['last_update'].get(data_type, 0)
                print(f"  {data_type}: {data} ({age:.1f}s)")
                
        print("="*70)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='CRSF Smart Bridge (Bridge B)')
    
    # UART параметры
    parser.add_argument('--uart-port', default='/dev/serial0',
                       help='UART порт (по умолчанию: /dev/serial0)')
    parser.add_argument('--uart-baudrate', type=int, default=416666,
                       help='UART baudrate (по умолчанию: 416666)')
    parser.add_argument('--tx-en-pin', type=int, default=24,
                       help='GPIO пин для включения TX (по умолчанию: 24)')
    parser.add_argument('--rx-en-pin', type=int, default=23,
                       help='GPIO пин для включения RX (по умолчанию: 23)')
    
    # UDP параметры
    parser.add_argument('--udp-local-port', type=int, default=5001,
                       help='Локальный UDP порт (по умолчанию: 5001)')
    parser.add_argument('--udp-remote-host', default='192.168.1.101',
                       help='IP адрес удаленного моста (по умолчанию: 192.168.1.101)')
    parser.add_argument('--udp-remote-port', type=int, default=5000,
                       help='UDP порт удаленного моста (по умолчанию: 5000)')
    parser.add_argument('--debug', action='store_true', help='Включить подробный отладочный вывод HEX-пакетов')
    
    args = parser.parse_args()
    
    # Создание и запуск моста
    bridge = SmartBridge(
        uart_port=args.uart_port,
        uart_baudrate=args.uart_baudrate,
        tx_en_pin=args.tx_en_pin,
        rx_en_pin=args.rx_en_pin,
        udp_local_port=args.udp_local_port,
        udp_remote_host=args.udp_remote_host,
        udp_remote_port=args.udp_remote_port,
        debug=args.debug
    )
    
    # Пример установки callback для фрейма RC каналов
    def on_rc_channels(frame):
        if len(frame.payload) == 22:  # RC_CHANNELS_PACKED
            print("Получены RC каналы от пульта")
            
    bridge.set_frame_callback(CRSFFrameType.RC_CHANNELS_PACKED, on_rc_channels)
    
    try:
        with bridge:
            print("Smart Bridge работает. Нажмите Ctrl+C для остановки.")
            while True:
                time.sleep(1)
                
                # Пример получения телеметрии
                # telemetry = bridge.get_telemetry_data()
                # if telemetry['link_stats']:
                #     print(f"Link Quality: {telemetry['link_stats']['uplink_quality']}%")
                
    except KeyboardInterrupt:
        print("\nПолучен сигнал остановки...")
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        print("Smart Bridge завершен")

if __name__ == '__main__':
    main()