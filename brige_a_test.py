#!/usr/bin/env python3

import serial
import struct

def ticks_to_us(ticks):
    return (ticks - 992) * 5 // 8 + 1500

def parse_rc_channels(payload):
    channels = []
    
    # 16 каналов упакованы в 22 байта (11 бит на канал)
    data = int.from_bytes(payload[:22], 'little')
    
    for i in range(16):
        channel_value = (data >> (i * 11)) & 0x7FF
        channels.append(ticks_to_us(channel_value))
    
    return channels

def main():
    ser = serial.Serial('/dev/serial0', 400000, timeout=0.1)
    buffer = bytearray()
    
    while True:
        data = ser.read(100)
        if data:
            buffer.extend(data)
            
            while len(buffer) > 0:
                # Ищем начало пакета
                start_idx = buffer.find(0x23)
                if start_idx == -1:
                    buffer.clear()
                    break
                
                # Удаляем все до начала пакета
                if start_idx > 0:
                    buffer = buffer[start_idx:]
                
                # Ищем конец пакета
                end_idx = buffer.find(0xFC, 1)
                if end_idx == -1:
                    break
                
                # Извлекаем пакет
                packet = buffer[:end_idx + 1]
                buffer = buffer[end_idx + 1:]
                
                if len(packet) == 27:
                    # Извлекаем payload (пропускаем sync, length, type, берем CRC в конце)
                    payload = packet[3:-1]
                    
                    channels = parse_rc_channels(payload)
                    
                    print(f"CH1-8:  {' '.join(f'{ch:4d}' for ch in channels[:8])}")
                    print(f"CH9-16: {' '.join(f'{ch:4d}' for ch in channels[8:16])}")
                    print("-" * 50)

if __name__ == "__main__":
    main()