#!/usr/bin/env python3
"""
Bridge A - Простой мост между пультом и UDP
Подключается к пульту по UART и пересылает данные в UDP
"""

import time
import threading
import argparse
import serial
from udp_transport import BidirectionalUDPTransport

class SimpleBridge:
    """Простой мост - только пересылка данных без парсинга"""
    
    def __init__(self, uart_port: str, uart_baudrate: int,
                 udp_local_port: int, udp_remote_host: str, udp_remote_port: int):
        self.uart_port = uart_port
        self.uart_baudrate = uart_baudrate
        self.uart = None
        self.is_running = False
        self.uart_thread = None

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
        
    def start(self):
        """Запуск простого моста"""
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
        
        self.udp_transport.set_data_callback(self._on_udp_data)
        self.udp_transport.start()
        
        self.stats_thread = threading.Thread(target=self._stats_loop, daemon=True)
        self.stats_thread.start()
        
        print("Simple Bridge запущен")
        print(f"UART: {self.uart.port} @ {self.uart.baudrate}")
        print(f"UDP: {self.udp_transport.transport.local_port} -> {self.udp_transport.transport.remote_host}:{self.udp_transport.transport.remote_port}")
        
    def stop(self):
        """Остановка простого моста"""
        print("Остановка Simple Bridge...")
        self.is_running = False
        if self.uart_thread:
            self.uart_thread.join()
        
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
        """Обработчик данных от UART - пересылаем в UDP"""
        if len(data) > 0:
            success = self.udp_transport.send_crsf_data(data)
            if success:
                self.stats['uart_to_udp_packets'] += 1
                self.stats['uart_to_udp_bytes'] += len(data)
                self.stats['last_uart_rx'] = time.time()
                
                print(f"UART->UDP: {len(data)} bytes: {' '.join(f'{b:02X}' for b in data[:16])}{'...' if len(data) > 16 else ''}")
                
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
        udp_rx_ago = time.time() - self.stats['last_udp_rx'] if self.stats['last_udp_rx'] > 0 else uptime
        
        udp_stats = self.udp_transport.get_stats()
        
        print("\n" + "="*60)
        print("SIMPLE BRIDGE СТАТИСТИКА")
        print("="*60)
        print(f"Время работы: {uptime:.1f} сек")
        print(f"UART -> UDP: {self.stats['uart_to_udp_packets']} пакетов, {self.stats['uart_to_udp_bytes']} байт")
        print(f"UDP -> UART: {self.stats['udp_to_uart_packets']} пакетов, {self.stats['udp_to_uart_bytes']} байт")
        print(f"Последний прием UART: {uart_rx_ago:.1f} сек назад")
        print(f"Последний прием UDP: {udp_rx_ago:.1f} сек назад")
        print(f"UDP соединение: {'активно' if udp_stats['connection_active'] else 'неактивно'}")
        print("="*60)

def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='CRSF Simple Bridge (Bridge A)')
    
    parser.add_argument('--uart-port', default='/dev/serial0', help='UART порт (по умолчанию: /dev/serial0)')
    parser.add_argument('--uart-baudrate', type=int, default=416666, help='UART baudrate (по умолчанию: 416666)')
    
    parser.add_argument('--udp-local-port', type=int, required=True, help='Локальный UDP порт')
    parser.add_argument('--udp-remote-host', required=True, help='IP адрес удаленного моста')
    parser.add_argument('--udp-remote-port', type=int, required=True, help='UDP порт удаленного моста')
    
    args = parser.parse_args()
    
    try:
        bridge = SimpleBridge(
            uart_port=args.uart_port,
            uart_baudrate=args.uart_baudrate,
            udp_local_port=args.udp_local_port,
            udp_remote_host=args.udp_remote_host,
            udp_remote_port=args.udp_remote_port
        )
        with bridge:
            print("Simple Bridge работает. Нажмите Ctrl+C для остановки.")
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