#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time
import sys

# --- НАСТРОЙКИ ---
# Укажите ваш UART порт
# Для Raspberry Pi это обычно '/dev/serial0' или '/dev/ttyAMA0'
PORT = '/dev/serial0'

# Укажите скорость (baudrate)
# Стандартная для CRSF - 400000, 416666 или 420000. 
# 416666 - часто используется для связи RX и FC.
BAUDRATE = 400000

# Размер байта (5, 6, 7 или 8)
BYTESIZE = serial.EIGHTBITS

# Контроль четности (NONE, EVEN, ODD, MARK, SPACE)
PARITY = serial.PARITY_NONE

# Количество стоп-бит (1, 1.5, 2)
STOPBITS = serial.STOPBITS_ONE

# Таймаут чтения в секундах (None - ждать вечно, 0 - неблокирующий, x - ждать x секунд)
TIMEOUT = 1

# Программный контроль потока
XONXOFF = False

# Аппаратный контроль потока (RTS/CTS)
RTSCTS = False

# Аппаратный контроль потока (DSR/DTR)
DSRDTR = False

# Таймаут записи в секундах
WRITE_TIMEOUT = None

# Межсимвольный таймаут
INTER_BYTE_TIMEOUT = None

# Эксклюзивный доступ (только для POSIX)
EXCLUSIVE = None


# --- КОНЕЦ НАСТРОЕК ---

def main():
    """
    Основная функция для чтения данных из UART и вывода в консоль.
    """
    ser = None  # Инициализируем переменную для serial порта
    try:
        # 1. Открываем serial порт
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
        print("Начинаем чтение данных. Нажмите Ctrl+C для выхода.")
        print("-" * 50)

        # 2. Бесконечный цикл для чтения данных
        while True:
            # Проверяем, есть ли данные в буфере UART
            if ser.in_waiting > 0:
                # Читаем все доступные байты
                data_bytes = ser.read(ser.in_waiting)
                
                # Конвертируем байты в строку HEX для удобного отображения
                hex_string = ' '.join(f'{b:02X}' for b in data_bytes)
                
                # Выводим полученные данные
                print(f"Получено {len(data_bytes)} байт: {hex_string}")
            
            # Небольшая задержка, чтобы не загружать процессор
            time.sleep(0.01)

    except serial.SerialException as e:
        # Обработка ошибок, если не удалось открыть порт
        print(f"ОШИБКА: Не удалось открыть порт {PORT}. {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        # Обработка нажатия Ctrl+C для чистого выхода
        print("\nПрограмма завершена пользователем.")
    except Exception as e:
        # Обработка других возможных ошибок
        print(f"\nПроизошла непредвиденная ошибка: {e}")
    finally:
        # 3. Гарантированно закрываем порт при выходе
        if ser and ser.is_open:
            ser.close()
            print("Порт закрыт.")

if __name__ == '__main__':
    main() 