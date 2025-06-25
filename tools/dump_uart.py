#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time
import sys

# --- НАСТРОЙКИ ---
PORT = '/dev/serial0'                # UART порт
BAUDRATE = 400000                    # Скорость (бод) для CRSF
BYTESIZE = serial.EIGHTBITS          # Размер байта (5, 6, 7 или 8)
PARITY = serial.PARITY_NONE          # Контроль четности (NONE, EVEN, ODD, MARK, SPACE)
STOPBITS = serial.STOPBITS_ONE       # Количество стоп-бит (1, 1.5, 2)
TIMEOUT = 0.01                       # Таймаут чтения в секундах (10 мс)
XONXOFF = False                      # Программный контроль потока
RTSCTS = False                       # Аппаратный контроль потока (RTS/CTS)
DSRDTR = False                       # Аппаратный контроль потока (DSR/DTR)
WRITE_TIMEOUT = None                 # Таймаут записи в секундах
INTER_BYTE_TIMEOUT = None            # Межсимвольный таймаут
EXCLUSIVE = None                     # Эксклюзивный доступ (только для POSIX)

DUMP_DURATION = 1                    # Длительность сбора данных в секундах
OUTPUT_FILE = 'uart_dump.txt'        # Файл для сохранения данных

def main():
    """
    Основная функция для сбора данных из UART в файл.
    """
    ser = None
    dump_file = None
    
    try:
        # Открываем serial порт
        print(f"Попытка подключения к {PORT} на скорости {BAUDRATE}...")
        ser = serial.Serial(
            port=PORT,
            baudrate=BAUDRATE,
            bytesize=BYTESIZE,
            parity=PARITY,
            stopbits=STOPBITS,
            timeout=TIMEOUT,
            xonxoff=XONXOFF,
            rtscts=RTSCTS,
            dsrdtr=DSRDTR,
            write_timeout=WRITE_TIMEOUT,
            inter_byte_timeout=INTER_BYTE_TIMEOUT,
            exclusive=EXCLUSIVE
        )
        print(f"Порт {ser.port} успешно открыт.")
        
        # Открываем файл для записи
        print(f"Данные будут сохранены в файл: {OUTPUT_FILE}")
        dump_file = open(OUTPUT_FILE, 'w')
        
        print(f"Начинаю сбор данных в течение {DUMP_DURATION} секунд...")
        
        total_bytes_read = 0

        # Цикл сбора данных
        # Используем блокирующее чтение с таймаутом для эффективности.
        # Это позволяет не нагружать CPU постоянными проверками.
        end_time = time.time() + DUMP_DURATION
        while time.time() < end_time:
            # Динамически уменьшаем таймаут, чтобы общее время не превысило DUMP_DURATION
            ser.timeout = max(0, end_time - time.time())
            
            # Читаем доступные данные (до 1024 байт за раз)
            data_bytes = ser.read(1024)
            
            if data_bytes:
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
        # Гарантированно закрываем все ресурсы
        if ser and ser.is_open:
            ser.close()
            print("Порт закрыт.")
        if dump_file:
            dump_file.close()
            print(f"Файл {OUTPUT_FILE} сохранен.")

if __name__ == '__main__':
    main() 