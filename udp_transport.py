#!/usr/bin/env python3
"""
UDP транспорт для передачи CRSF данных между мостами
"""

import socket
import threading
import time
import struct
from typing import Callable, Optional, Tuple
from enum import IntEnum

class UDPPacketType(IntEnum):
    """Типы UDP пакетов"""
    CRSF_DATA = 0x01      # CRSF данные
    HEARTBEAT = 0x02      # Heartbeat для проверки связи
    STATUS = 0x03         # Статусная информация

class UDPTransport:
    """UDP транспорт для CRSF данных"""
    
    def __init__(self, local_port: int, remote_host: str, remote_port: int):
        """
        Инициализация UDP транспорта
        
        Args:
            local_port: Локальный порт для прослушивания
            remote_host: IP адрес удаленного моста
            remote_port: Порт удаленного моста
        """
        self.local_port = local_port
        self.remote_host = remote_host
        self.remote_port = remote_port
        
        self.socket = None
        self.is_running = False
        self.rx_thread = None
        self.heartbeat_thread = None
        
        # Callbacks
        self.data_callback: Optional[Callable[[bytes], None]] = None
        self.status_callback: Optional[Callable[[dict], None]] = None
        
        # Статистика
        self.stats = {
            'tx_packets': 0,
            'rx_packets': 0,
            'tx_bytes': 0,
            'rx_bytes': 0,
            'last_rx_time': 0,
            'connection_active': False
        }
        
    def start(self):
        """Запуск UDP транспорта"""
        if self.is_running:
            return
            
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('', self.local_port))
            self.socket.settimeout(0.1)  # Неблокирующий режим с timeout
            
            self.is_running = True
            
            # Запуск потоков
            self.rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
            self.rx_thread.start()
            
            self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self.heartbeat_thread.start()
            
            print(f"UDP транспорт запущен на порту {self.local_port}")
            
        except Exception as e:
            print(f"Ошибка запуска UDP транспорта: {e}")
            self.stop()
            
    def stop(self):
        """Остановка UDP транспорта"""
        self.is_running = False
        
        if self.rx_thread:
            self.rx_thread.join(timeout=1.0)
            
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=1.0)
            
        if self.socket:
            self.socket.close()
            self.socket = None
            
        print("UDP транспорт остановлен")
        
    def set_data_callback(self, callback: Callable[[bytes], None]):
        """Устанавливает callback для получения CRSF данных"""
        self.data_callback = callback
        
    def set_status_callback(self, callback: Callable[[dict], None]):
        """Устанавливает callback для получения статуса"""
        self.status_callback = callback
        
    def send_crsf_data(self, data: bytes) -> bool:
        """
        Отправка CRSF данных
        
        Args:
            data: CRSF данные для отправки
            
        Returns:
            True если отправка успешна
        """
        return self._send_packet(UDPPacketType.CRSF_DATA, data)
        
    def send_status(self, status_data: dict) -> bool:
        """
        Отправка статуса
        
        Args:
            status_data: Словарь со статусной информацией
            
        Returns:
            True если отправка успешна
        """
        # Простая сериализация статуса (можно улучшить)
        status_str = str(status_data).encode('utf-8')
        return self._send_packet(UDPPacketType.STATUS, status_str)
        
    def _send_packet(self, packet_type: UDPPacketType, data: bytes) -> bool:
        """Отправка UDP пакета с заголовком"""
        if not self.socket or not self.is_running:
            return False
            
        try:
            # Формат пакета: [type:1][timestamp:8][length:2][data:N]
            timestamp = int(time.time() * 1000000)  # микросекунды
            packet = struct.pack('!BQH', packet_type, timestamp, len(data)) + data
            
            sent_bytes = self.socket.sendto(packet, (self.remote_host, self.remote_port))
            
            self.stats['tx_packets'] += 1
            self.stats['tx_bytes'] += sent_bytes
            
            return True
            
        except Exception as e:
            print(f"Ошибка отправки UDP пакета: {e}")
            return False
            
    def _rx_loop(self):
        """Основной цикл получения UDP пакетов"""
        while self.is_running:
            try:
                data, addr = self.socket.recvfrom(1024)
                
                if len(data) < 11:  # Минимальный размер заголовка
                    continue
                    
                # Разбираем заголовок
                packet_type, timestamp, data_length = struct.unpack('!BQH', data[:11])
                payload = data[11:11+data_length]
                
                if len(payload) != data_length:
                    continue
                    
                self.stats['rx_packets'] += 1
                self.stats['rx_bytes'] += len(data)
                self.stats['last_rx_time'] = time.time()
                self.stats['connection_active'] = True
                
                # Обработка по типу пакета
                if packet_type == UDPPacketType.CRSF_DATA:
                    if self.data_callback:
                        self.data_callback(payload)
                        
                elif packet_type == UDPPacketType.HEARTBEAT:
                    # Отвечаем на heartbeat
                    self._send_packet(UDPPacketType.HEARTBEAT, b'pong')
                    
                elif packet_type == UDPPacketType.STATUS:
                    if self.status_callback:
                        try:
                            status_str = payload.decode('utf-8')
                            status_dict = eval(status_str)  # Простая десериализация
                            self.status_callback(status_dict)
                        except:
                            pass
                            
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    print(f"Ошибка получения UDP пакета: {e}")
                    time.sleep(0.1)
                    
    def _heartbeat_loop(self):
        """Цикл отправки heartbeat пакетов"""
        while self.is_running:
            # Отправляем heartbeat каждые 5 секунд
            self._send_packet(UDPPacketType.HEARTBEAT, b'ping')
            
            # Проверяем состояние соединения
            if time.time() - self.stats['last_rx_time'] > 15:  # 15 секунд без данных
                self.stats['connection_active'] = False
                
            time.sleep(5.0)
            
    def get_stats(self) -> dict:
        """Возвращает статистику транспорта"""
        return self.stats.copy()
        
    def __enter__(self):
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

class BidirectionalUDPTransport:
    """Двунаправленный UDP транспорт (сервер + клиент)"""
    
    def __init__(self, local_port: int, remote_host: str, remote_port: int):
        self.transport = UDPTransport(local_port, remote_host, remote_port)
        
    def start(self):
        """Запуск транспорта"""
        self.transport.start()
        
    def stop(self):
        """Остановка транспорта"""
        self.transport.stop()
        
    def send_crsf_data(self, data: bytes) -> bool:
        """Отправка CRSF данных"""
        return self.transport.send_crsf_data(data)
        
    def set_data_callback(self, callback: Callable[[bytes], None]):
        """Установка callback для получения данных"""
        self.transport.set_data_callback(callback)
        
    def get_stats(self) -> dict:
        """Получение статистики"""
        return self.transport.get_stats()
        
    def __enter__(self):
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()