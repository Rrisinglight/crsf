#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time
import sys

# --- НАСТРОЙКИ ---
PORT = '/dev/serial0'
BAUDRATE = 400000
DUMP_DURATION = 1  # Длительность сбора данных в секундах
OUTPUT_FILE = 'uart_dump.txt'
# --- КОНЕЦ НАСТРОЕК ---

def main():
    """
    Основная функция для сбора данных из UART в файл.
    """
    ser = None
    dump_file = None
    
    try:
        # 1. Открываем serial порт
        print(f"Попытка подключения к {PORT} на скорости {BAUDRATE}...")
        ser = serial.Serial(port=PORT, baudrate=BAUDRATE, timeout=0.1)
        print(f"Порт {ser.port} успешно открыт.")
        
        # 2. Открываем файл для записи
        print(f"Данные будут сохранены в файл: {OUTPUT_FILE}")
        dump_file = open(OUTPUT_FILE, 'w')
        
        print(f"Начинаю сбор данных в течение {DUMP_DURATION} секунд...")
        
        start_time = time.time()
        total_bytes_read = 0

        # 3. Цикл сбора данных
        while time.time() - start_time < DUMP_DURATION:
            if ser.in_waiting > 0:
                data_bytes = ser.read(ser.in_waiting)
                total_bytes_read += len(data_bytes)
                
                # Конвертируем в HEX и записываем в файл
                hex_string = ' '.join(f'{b:02X}' for b in data_bytes)
                dump_file.write(hex_string + ' ') # Добавляем пробел, чтобы данные не слипались
                
        print("\nСбор данных завершен.")
        print(f"Всего записано байт: {total_bytes_read}")

    except serial.SerialException as e:
        print(f"ОШИБКА: Не удалось открыть порт {PORT}. {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nПроизошла непредвиденная ошибка: {e}")
    finally:
        # 4. Гарантированно закрываем все ресурсы
        if ser and ser.is_open:
            ser.close()
            print("Порт закрыт.")
        if dump_file:
            dump_file.close()
            print(f"Файл {OUTPUT_FILE} сохранен.")

if __name__ == '__main__':
    main() 