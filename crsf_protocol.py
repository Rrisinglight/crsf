#!/usr/bin/env python3
"""
CRSF Protocol handler - базовые классы для работы с CRSF фреймами
"""

import time
from typing import Optional, List, Tuple
from enum import IntEnum

class CRSFFrameType(IntEnum):
    GPS = 0x02
    BATTERY_SENSOR = 0x08
    HEARTBEAT = 0x0B
    LINK_STATISTICS = 0x14
    RC_CHANNELS_PACKED = 0x16
    ATTITUDE = 0x1E
    FLIGHT_MODE = 0x21
    PING = 0x28
    DEVICE_INFO = 0x29
    PARAM_ENTRY = 0x2B
    PARAM_READ = 0x2C
    PARAM_WRITE = 0x2D

class CRSFAddress(IntEnum):
    BROADCAST = 0x00
    FC = 0xC8
    REMOTE = 0xEA
    RX = 0xEC
    TX = 0xEE

CRSF_SYNC_BYTE = 0xC8
CRSF_MAX_FRAME_SIZE = 64

class CRSFFrame:
    def __init__(self, data: bytes = None):
        self.sync_byte = CRSF_SYNC_BYTE
        self.frame_length = 0
        self.frame_type = 0
        self.destination = None
        self.origin = None
        self.payload = b''
        self.crc = 0
        
        if data:
            self.parse(data)
    
    def parse(self, data: bytes) -> bool:
        """Парсит CRSF фрейм из байтов"""
        if len(data) < 4:
            return False
            
        if data[0] != CRSF_SYNC_BYTE:
            return False
            
        self.sync_byte = data[0]
        self.frame_length = data[1]
        
        if len(data) != self.frame_length + 2:
            return False
            
        self.frame_type = data[2]
        
        # Проверяем, extended фрейм или нет
        if self.is_extended_frame():
            if len(data) < 6:
                return False
            self.destination = data[3]
            self.origin = data[4]
            self.payload = data[5:-1]
        else:
            self.payload = data[3:-1]
            
        self.crc = data[-1]
        
        # Проверяем CRC
        return self.validate_crc(data)
    
    def is_extended_frame(self) -> bool:
        """Проверяет, является ли фрейм extended (с адресами)"""
        return self.frame_type >= 0x28
    
    def build(self) -> bytes:
        """Собирает фрейм в байты"""
        frame = bytearray()
        frame.append(self.sync_byte)
        
        # Временно добавляем длину (пересчитаем позже)
        frame.append(0)
        frame.append(self.frame_type)
        
        if self.is_extended_frame():
            if self.destination is not None:
                frame.append(self.destination)
            if self.origin is not None:
                frame.append(self.origin)
                
        frame.extend(self.payload)
        
        # Устанавливаем правильную длину
        self.frame_length = len(frame) - 1  # Исключаем sync байт
        frame[1] = self.frame_length
        
        # Добавляем CRC
        self.crc = self.calculate_crc(frame[2:])
        frame.append(self.crc)
        
        return bytes(frame)
    
    @staticmethod
    def calculate_crc(data: bytes) -> int:
        """Вычисляет CRC8 для CRSF (полином 0xD5)"""
        crc = 0
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0xD5
                else:
                    crc <<= 1
                crc &= 0xFF
        return crc
    
    def validate_crc(self, data: bytes) -> bool:
        """Проверяет CRC фрейма"""
        expected_crc = self.calculate_crc(data[2:-1])
        return expected_crc == data[-1]
    
    def __str__(self):
        ext_info = ""
        if self.is_extended_frame():
            ext_info = f" {self.origin:02X}->{self.destination:02X}"
        return f"CRSF[{self.frame_type:02X}{ext_info}] len={self.frame_length} payload={len(self.payload)}b"

class CRSFParser:
    def __init__(self):
        self.buffer = bytearray()
        
    def add_data(self, data: bytes) -> List[CRSFFrame]:
        """Добавляет данные в буфер и возвращает найденные фреймы"""
        self.buffer.extend(data)
        frames = []
        
        while len(self.buffer) >= 4:
            # Ищем sync байт
            sync_pos = self.buffer.find(CRSF_SYNC_BYTE)
            if sync_pos == -1:
                self.buffer.clear()
                break
                
            if sync_pos > 0:
                self.buffer = self.buffer[sync_pos:]
                
            if len(self.buffer) < 2:
                break
                
            frame_length = self.buffer[1]
            total_length = frame_length + 2
            
            if total_length > CRSF_MAX_FRAME_SIZE:
                self.buffer = self.buffer[1:]
                continue
                
            if len(self.buffer) < total_length:
                break
                
            frame_data = bytes(self.buffer[:total_length])
            frame = CRSFFrame()
            
            if frame.parse(frame_data):
                frames.append(frame)
                
            self.buffer = self.buffer[total_length:]
            
        return frames

def create_heartbeat_frame(origin: int = CRSFAddress.FC) -> CRSFFrame:
    """Создает heartbeat фрейм"""
    frame = CRSFFrame()
    frame.frame_type = CRSFFrameType.HEARTBEAT
    frame.payload = bytes([origin])
    return frame

def create_ping_frame(destination: int = CRSFAddress.BROADCAST, 
                     origin: int = CRSFAddress.FC) -> CRSFFrame:
    """Создает ping фрейм"""
    frame = CRSFFrame()
    frame.frame_type = CRSFFrameType.PING
    frame.destination = destination
    frame.origin = origin
    frame.payload = b''
    return frame