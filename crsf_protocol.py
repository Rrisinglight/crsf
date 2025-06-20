#!/usr/bin/env python3
"""
CRSF Protocol handler - базовые классы для работы с CRSF фреймами
"""

import time
from typing import Optional, List, Tuple
from enum import IntEnum, Enum

# Основные адреса устройств CRSF
# https://www.team-blacksheep.com/crsf-protocol.pdf (старая версия)
# https://github.com/crsf-wg/crsf/wiki/CRSF-Protocol#device-addresses (актуальный)
SYNC_BYTE = 0xC8 # Используется для телеметрии от FC
CRSF_ADDRESS_FLIGHT_CONTROLLER = 0xC8
CRSF_ADDRESS_RADIO_TRANSMITTER = 0xEA
CRSF_ADDRESS_RECEIVER = 0xEC
CRSF_ADDRESS_TRANSMITTER = 0xEE

# Список всех возможных байтов, с которых может начинаться валидный CRSF пакет
VALID_SYNC_BYTES = (
    CRSF_ADDRESS_FLIGHT_CONTROLLER,
    CRSF_ADDRESS_RADIO_TRANSMITTER,
    CRSF_ADDRESS_RECEIVER,
    CRSF_ADDRESS_TRANSMITTER,
)

class CRSFFrameType(Enum):
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

CRSF_MAX_FRAME_SIZE = 64

class CRSFFrame:
    def __init__(self, frame_type, payload: bytes, sync_byte: int = SYNC_BYTE):
        if isinstance(frame_type, CRSFFrameType):
            self.frame_type = frame_type.value
        else:
            self.frame_type = frame_type # Для неизвестных типов
        self.payload = payload
        self.sync_byte = sync_byte

    @staticmethod
    def calc_crc(data: bytes) -> int:
        crc = 0
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0xD5
                else:
                    crc <<= 1
                crc &= 0xFF
        return crc

    def build(self) -> bytes:
        # Длина = тип (1) + payload + CRC (1)
        length = 1 + len(self.payload) + 1
        
        # Формируем данные для CRC: тип + payload
        crc_data = bytes([self.frame_type]) + self.payload
        crc = self.calc_crc(crc_data)
        
        # Собираем фрейм
        return bytes([self.sync_byte, length, self.frame_type]) + self.payload + bytes([crc])

    def __str__(self):
        payload_str = ' '.join(f'{b:02X}' for b in self.payload[:16])
        if len(self.payload) > 16:
            payload_str += '...'
        type_name = CRSFFrameType(self.frame_type).name if self.frame_type in [e.value for e in CRSFFrameType] else f'UNKNOWN(0x{self.frame_type:02X})'
        return (f"CRSF Frame: Sync: {self.sync_byte:02X}, Type: {type_name}, "
                f"Len: {len(self.payload) + 2}, Payload: [{payload_str}]")

class CRSFParser:
    def __init__(self):
        self.buffer = bytearray()

    def add_data(self, data: bytes) -> List['CRSFFrame']:
        self.buffer.extend(data)
        frames = []
        while len(self.buffer) > 2:
            try:
                # Ищем один из валидных синхробайтов
                sync_index = -1
                for sync_byte in VALID_SYNC_BYTES:
                    sync_index = self.buffer.find(sync_byte)
                    if sync_index != -1:
                        break
                
                if sync_index == -1:
                    # Если не нашли, выходим, оставляем данные в буфере
                    # В будущем можно добавить логику очистки "мусорных" байт
                    break
                
                # Если перед синхробайтом есть мусор, удаляем его
                if sync_index > 0:
                    self.buffer = self.buffer[sync_index:]

                # Проверяем, достаточно ли данных для чтения длины и типа
                if len(self.buffer) < 2:
                    break
                
                frame_len = self.buffer[1]
                # Длина включает Type, Payload и CRC
                if frame_len < 2 or frame_len > 62: # Валидация длины
                    # Невалидная длина, удаляем битый синхробайт и ищем дальше
                    self.buffer.pop(0)
                    continue

                # Проверяем, получили ли мы весь фрейм
                if len(self.buffer) < frame_len + 2:
                    # Фрейм еще неполный
                    break
                
                # Извлекаем полный пакет
                packet = self.buffer[:frame_len + 2]
                
                # Проверяем CRC
                crc_payload = packet[2:frame_len + 1]
                crc_received = packet[frame_len + 1]
                crc_calculated = self.calc_crc(crc_payload)

                if crc_calculated == crc_received:
                    frame_type_val = packet[2]
                    payload = packet[3:frame_len+1]
                    
                    try:
                        frame_type = CRSFFrameType(frame_type_val)
                        frame = CRSFFrame(frame_type, payload, sync_byte=packet[0])
                        frames.append(frame)
                    except ValueError:
                        # Неизвестный тип фрейма, но CRC верный. Создаем как есть.
                        frame = CRSFFrame(frame_type_val, payload, sync_byte=packet[0])
                        frames.append(frame)

                # Удаляем обработанный (или не прошедший CRC) пакет из буфера
                self.buffer = self.buffer[frame_len + 2:]

            except IndexError:
                # Недостаточно данных для обработки, выходим из цикла
                break
        return frames

def create_heartbeat_frame():
    # Heartbeat (0x0B) отправляется от FC к приемнику, но мы можем его использовать для проверки связи
    # Обычно это пустой пакет, но для надежности можно использовать официальный формат
    # В данном случае, это скорее "Ping"
    return create_ping_frame()

def create_ping_frame(destination: int = CRSFAddress.BROADCAST, 
                     origin: int = CRSFAddress.FC) -> CRSFFrame:
    """Создает ping фрейм"""
    frame = CRSFFrame(CRSF_ADDRESS_TRANSMITTER, b'')
    frame.destination = destination
    frame.origin = origin
    return frame