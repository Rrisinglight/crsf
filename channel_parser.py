#!/usr/bin/env python3
import serial
import time

BAUDRATE = 400000
SERIAL_PORT = '/dev/serial0'
RC_CHANNELS_TYPE = 0x16

# CRC8 lookup table для CRSF (полином 0xD5)
crc8_table = [
    0x00, 0xD5, 0x7F, 0xAA, 0xFE, 0x2B, 0x81, 0x54, 0x29, 0xFC, 0x56, 0x83, 0xD7, 0x02, 0xA8, 0x7D,
    0x52, 0x87, 0x2D, 0xF8, 0xAC, 0x79, 0xD3, 0x06, 0x7B, 0xAE, 0x04, 0xD1, 0x85, 0x50, 0xFA, 0x2F,
    0xA4, 0x71, 0xDB, 0x0E, 0x5A, 0x8F, 0x25, 0xF0, 0x8D, 0x58, 0xF2, 0x27, 0x73, 0xA6, 0x0C, 0xD9,
    0xF6, 0x23, 0x89, 0x5C, 0x08, 0xDD, 0x77, 0xA2, 0xDF, 0x0A, 0xA0, 0x75, 0x21, 0xF4, 0x5E, 0x8B,
    0x9D, 0x48, 0xE2, 0x37, 0x63, 0xB6, 0x1C, 0xC9, 0xB4, 0x61, 0xCB, 0x1E, 0x4A, 0x9F, 0x35, 0xE0,
    0xCF, 0x1A, 0xB0, 0x65, 0x31, 0xE4, 0x4E, 0x9B, 0xE6, 0x33, 0x99, 0x4C, 0x18, 0xCD, 0x67, 0xB2,
    0x39, 0xEC, 0x46, 0x93, 0xC7, 0x12, 0xB8, 0x6D, 0x10, 0xC5, 0x6F, 0xBA, 0xEE, 0x3B, 0x91, 0x44,
    0x6B, 0xBE, 0x14, 0xC1, 0x95, 0x40, 0xEA, 0x3F, 0x42, 0x97, 0x3D, 0xE8, 0xBC, 0x69, 0xC3, 0x16,
    0xEF, 0x3A, 0x90, 0x45, 0x11, 0xC4, 0x6E, 0xBB, 0xC6, 0x13, 0xB9, 0x6C, 0x38, 0xED, 0x47, 0x92,
    0xBD, 0x68, 0xC2, 0x17, 0x43, 0x96, 0x3C, 0xE9, 0x94, 0x41, 0xEB, 0x3E, 0x6A, 0xBF, 0x15, 0xC0,
    0x4B, 0x9E, 0x34, 0xE1, 0xB5, 0x60, 0xCA, 0x1F, 0x62, 0xB7, 0x1D, 0xC8, 0x9C, 0x49, 0xE3, 0x36,
    0x19, 0xCC, 0x66, 0xB3, 0xE7, 0x32, 0x98, 0x4D, 0x30, 0xE5, 0x4F, 0x9A, 0xCE, 0x1B, 0xB1, 0x64,
    0x72, 0xA7, 0x0D, 0xD8, 0x8C, 0x59, 0xF3, 0x26, 0x5B, 0x8E, 0x24, 0xF1, 0xA5, 0x70, 0xDA, 0x0F,
    0x20, 0xF5, 0x5F, 0x8A, 0xDE, 0x0B, 0xA1, 0x74, 0x09, 0xDC, 0x76, 0xA3, 0xF7, 0x22, 0x88, 0x5D,
    0xD6, 0x03, 0xA9, 0x7C, 0x28, 0xFD, 0x57, 0x82, 0xFF, 0x2A, 0x80, 0x55, 0x01, 0xD4, 0x7E, 0xAB,
    0x84, 0x51, 0xFB, 0x2E, 0x7A, 0xAF, 0x05, 0xD0, 0xAD, 0x78, 0xD2, 0x07, 0x53, 0x86, 0x2C, 0xF9
]

def crc8(data):
    """Вычисляет CRC8 для CRSF данных"""
    crc = 0
    for byte in data:
        crc = crc8_table[crc ^ byte]
    return crc

def ticks_to_us(ticks):
    """Конвертирует CRSF ticks в микросекунды"""
    return (ticks - 992) * 5 // 8 + 1500

def unpack_channels(payload):
    """Распаковывает 22 байта в 16 каналов по 11 бит каждый"""
    if len(payload) != 22:
        return None
    
    # Конвертируем байты в бинарную строку (little-endian)
    bit_string = ''.join(f'{byte:08b}'[::-1] for byte in payload)
    
    channels = []
    for i in range(16):
        # Извлекаем 11 бит для каждого канала
        start = i * 11
        end = start + 11
        channel_bits = bit_string[start:end][::-1]  # Реверсируем биты
        ticks = int(channel_bits, 2)
        channels.append(ticks_to_us(ticks))
    
    return channels

def parse_crsf_frame(buffer):
    """Парсит CRSF фрейм из буфера"""
    while len(buffer) >= 4:
        # Ищем начало фрейма (sync byte)
        sync_found = False
        for i in range(len(buffer)):
            if buffer[i] in [0xC8, 0xEE, 0xEA]:  # SYNC или адреса устройств
                if i > 0:
                    buffer[:i] = []  # Удаляем мусор
                sync_found = True
                break
        
        if not sync_found:
            buffer.clear()
            return None
        
        if len(buffer) < 2:
            return None
            
        frame_length = buffer[1]
        if frame_length < 2 or frame_length > 62:
            buffer.pop(0)
            continue
        
        total_length = frame_length + 2
        if len(buffer) < total_length:
            return None
        
        # Извлекаем фрейм
        frame = bytes(buffer[:total_length])
        buffer[:total_length] = []
        
        # Проверяем CRC
        calculated_crc = crc8(frame[2:-1])
        if frame[-1] != calculated_crc:
            continue
        
        return frame
    
    return None

def main():
    print("CRSF Channel Parser - Raspberry Pi")
    print("Press Ctrl+C to exit\n")
    
    try:
        with serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.1) as ser:
            buffer = bytearray()
            
            while True:
                # Читаем данные
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    buffer.extend(data)
                
                # Парсим фреймы
                frame = parse_crsf_frame(buffer)
                if frame and frame[2] == RC_CHANNELS_TYPE:
                    payload = frame[3:-1]
                    channels = unpack_channels(payload)
                    
                    if channels:
                        print(f"CH1-CH8: {channels[0]:4d} {channels[1]:4d} {channels[2]:4d} {channels[3]:4d} "
                              f"{channels[4]:4d} {channels[5]:4d} {channels[6]:4d} {channels[7]:4d}     "
                              f"CH9-CH16: {channels[8]:4d} {channels[9]:4d} {channels[10]:4d} {channels[11]:4d} "
                              f"{channels[12]:4d} {channels[13]:4d} {channels[14]:4d} {channels[15]:4d}")
                
                time.sleep(0.001)
                
    except KeyboardInterrupt:
        print("\nЗавершение работы...")
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    main()