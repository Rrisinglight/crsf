#!/usr/bin/env python3
"""
Bridge A - Простой мост между пультом и UDP или UART монитор
Подключается к пульту по UART и пересылает данные в UDP,
либо просто отображает данные с UART, если UDP не настроен.
"""

import time
import threading
import argparse
import serial
from udp_transport import BidirectionalUDPTransport
from typing import Optional

class SimpleBridge:
    """Простой мост или UART монитор"""
    
    def __init__(self, uart_port: str, uart_baudrate: int,
                 udp_local_port: Optional[int] = None, udp_remote_host: Optional[str] = None, udp_remote_port: Optional[int] = None,
                 invert_uart: bool = False):
        self.uart_port = uart_port
        self.uart_baudrate = uart_baudrate
        self.uart = None
        self.is_running = False
        self.uart_thread = None
        self.invert_uart = invert_uart

        self.udp_transport = None
        if udp_local_port and udp_remote_host and udp_remote_port:
            self.udp_transport = BidirectionalUDPTransport(
                udp_local_port, udp_remote_host, udp_remote_port
            )
        
        self.stats = {
            'uart_to_udp_packets': 0,
            'udp_to_uart_packets': 0,
            'uart_to_udp_bytes': 0,
            'udp_to_uart_bytes': 0,
            'start_time': time.time(),
            'last_uart_rx': 0,
            'last_udp_rx': 0
        }
        
        self.stats_thread = None
        self.debug_uart_mode = False
        
    def start(self):
        """Запуск моста/монитора"""
        print("Запуск Simple Bridge (Bridge A)...")

        try:
            self.uart = serial.Serial(self.uart_port, self.uart_baudrate, timeout=1)
            print(f"UART порт {self.uart.port} открыт")
        except serial.SerialException as e:
            print(f"Не удалось открыть UART порт {self.uart_port}: {e}")
            raise
        
        self.is_running = True
        self.uart_thread = threading.Thread(target=self._uart_reader_loop, daemon=True)
        self.uart_thread.start()
        
        if self.udp_transport:
            self.udp_transport.set_data_callback(self._on_udp_data)
            self.udp_transport.start()
        
        self.stats_thread = threading.Thread(target=self._stats_loop, daemon=True)
        self.stats_thread.start()
        
        print("Simple Bridge запущен")
        print(f"UART: {self.uart.port} @ {self.uart.baudrate}")
        if self.udp_transport:
            print(f"UDP: {self.udp_transport.transport.local_port} -> {self.udp_transport.transport.remote_host}:{self.udp_transport.transport.remote_port}")
        elif self.debug_uart_mode:
            print("--- РЕЖИМ ОТЛАДКИ UART АКТИВЕН ---")
        else:
            print("UDP транспорт отключен. Работа в режиме монитора UART.")
        
    def stop(self):
        """Остановка моста/монитора"""
        print("Остановка Simple Bridge...")
        self.is_running = False
        if self.uart_thread:
            self.uart_thread.join()
        
        if self.udp_transport:
            self.udp_transport.stop()

        if self.uart and self.uart.is_open:
            self.uart.close()
            print("UART порт закрыт")
            
        print("Simple Bridge остановлен")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        
    def _uart_reader_loop(self):
        """Цикл чтения из UART"""
        while self.is_running:
            try:
                if self.uart and self.uart.is_open and self.uart.in_waiting > 0:
                    data = self.uart.read(self.uart.in_waiting)
                    self._on_uart_data(data)
            except serial.SerialException as e:
                print(f"Ошибка чтения из UART: {e}")
                self.is_running = False
                break
            time.sleep(0.001)

    def send_to_uart(self, data: bytes) -> bool:
        """Отправка данных в UART"""
        if self.uart and self.uart.is_open:
            try:
                self.uart.write(data)
                return True
            except serial.SerialException as e:
                print(f"Ошибка записи в UART: {e}")
        return False
        
    def _on_uart_data(self, data: bytes):
        """Обработчик данных от UART - пересылаем в UDP или выводим на экран"""
        if len(data) > 0:
            
            if self.invert_uart:
                data = bytes(b ^ 0xFF for b in data)

            self.stats['last_uart_rx'] = time.time()
            self.stats['uart_to_udp_packets'] += 1
            self.stats['uart_to_udp_bytes'] += len(data)
            
            if self.debug_uart_mode:
                label = "UART RX (INVERTED)" if self.invert_uart else "UART RX"
                print(f"{label}: {len(data)} bytes: {' '.join(f'{b:02X}' for b in data)}")
                return

            if self.udp_transport:
                print(f"UART->UDP: {len(data)} bytes: {' '.join(f'{b:02X}' for b in data[:16])}{'...' if len(data) > 16 else ''}")
                self.udp_transport.send_crsf_data(data)
            else:
                print(f"UART RX: {len(data)} bytes: {' '.join(f'{b:02X}' for b in data[:16])}{'...' if len(data) > 16 else ''}")
                
    def _on_udp_data(self, data: bytes):
        """Обработчик данных от UDP - пересылаем в UART"""
        if len(data) > 0:
            success = self.send_to_uart(data)
            if success:
                self.stats['udp_to_uart_packets'] += 1
                self.stats['udp_to_uart_bytes'] += len(data)
                self.stats['last_udp_rx'] = time.time()
                
                print(f"UDP->UART: {len(data)} bytes: {' '.join(f'{b:02X}' for b in data[:16])}{'...' if len(data) > 16 else ''}")
                
    def _stats_loop(self):
        """Цикл вывода статистики"""
        while self.is_running:
            time.sleep(30)
            self._print_stats()
            
    def _print_stats(self):
        """Вывод статистики"""
        uptime = time.time() - self.stats['start_time']
        uart_rx_ago = time.time() - self.stats['last_uart_rx'] if self.stats['last_uart_rx'] > 0 else uptime
        
        print("\n" + "="*60)
        print("SIMPLE BRIDGE СТАТИСТИКА")
        print("="*60)
        print(f"Время работы: {uptime:.1f} сек")
        
        if self.udp_transport:
            udp_rx_ago = time.time() - self.stats['last_udp_rx'] if self.stats['last_udp_rx'] > 0 else uptime
            udp_stats = self.udp_transport.get_stats()
            print(f"UART -> UDP: {self.stats['uart_to_udp_packets']} пакетов, {self.stats['uart_to_udp_bytes']} байт")
            print(f"UDP -> UART: {self.stats['udp_to_uart_packets']} пакетов, {self.stats['udp_to_uart_bytes']} байт")
            print(f"Последний прием UART: {uart_rx_ago:.1f} сек назад")
            print(f"Последний прием UDP: {udp_rx_ago:.1f} сек назад")
            print(f"UDP соединение: {'активно' if udp_stats['connection_active'] else 'неактивно'}")
        else:
            print(f"UART получено: {self.stats['uart_to_udp_packets']} пакетов, {self.stats['uart_to_udp_bytes']} байт")
            print(f"Последний прием UART: {uart_rx_ago:.1f} сек назад")
            
        print("="*60)

def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='CRSF Simple Bridge (Bridge A) - UART-UDP мост или UART монитор.')
    
    parser.add_argument('--uart-port', default='/dev/serial0', help='UART порт (по умолчанию: /dev/serial0)')
    parser.add_argument('--uart-baudrate', type=int, default=416666, help='UART baudrate (по умолчанию: 416666)')
    parser.add_argument('--debug-uart', action='store_true', help='Активировать режим отладки UART (только чтение и вывод)')
    parser.add_argument('--invert-uart', action='store_true', help='Инвертировать входящие UART данные (программно)')
    parser.add_argument('--udp-local-port', type=int, default=None, help='Локальный UDP порт (для активации моста)')
    parser.add_argument('--udp-remote-host', type=str, default=None, help='IP адрес удаленного моста (для активации моста)')
    parser.add_argument('--udp-remote-port', type=int, default=None, help='UDP порт удаленного моста (для активации моста)')
    
    args = parser.parse_args()

    # Проверка, что если указан один UDP параметр, то указаны все
    udp_params = [args.udp_local_port, args.udp_remote_host, args.udp_remote_port]
    if any(udp_params) and not all(udp_params):
        parser.error("Для работы UDP моста необходимо указать все три параметра: --udp-local-port, --udp-remote-host и --udp-remote-port.")

    if args.debug_uart and any(udp_params):
        parser.error("Режим --debug-uart не может использоваться вместе с UDP параметрами.")

    try:
        bridge = SimpleBridge(
            uart_port=args.uart_port,
            uart_baudrate=args.uart_baudrate,
            udp_local_port=args.udp_local_port,
            udp_remote_host=args.udp_remote_host,
            udp_remote_port=args.udp_remote_port,
            invert_uart=args.invert_uart
        )
        bridge.debug_uart_mode = args.debug_uart
        with bridge:
            if bridge.debug_uart_mode:
                print("Simple Bridge работает в режиме отладки UART. Нажмите Ctrl+C для остановки.")
            elif bridge.udp_transport:
                print("Simple Bridge работает в режиме моста. Нажмите Ctrl+C для остановки.")
            else:
                print("Simple Bridge работает в режиме монитора UART. Нажмите Ctrl+C для остановки.")
            while True:
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\nПолучен сигнал остановки...")
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        print("Simple Bridge завершен")

if __name__ == '__main__':
    main()