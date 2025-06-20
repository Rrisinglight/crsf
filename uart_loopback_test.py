import serial
import time

# --- Настройки ---
PORT = '/dev/serial0'
BAUDRATE = 115200
# -----------------

# Перед запуском замкните TX и RX на указанном порту

try:
    with serial.Serial(PORT, BAUDRATE, timeout=1) as ser:
        
        # Данные для отправки
        data_to_send = b'echo_test'
        
        # 1. Отправка (Эхо)
        ser.write(data_to_send)
        
        # Небольшая пауза для прохождения сигнала
        time.sleep(0.1) 
        
        # 2. Чтение
        data_received = ser.read(ser.in_waiting)

        # 3. Два принта
        print(f"Отправлено: {data_to_send}")
        print(f"Получено:   {data_received}")

except Exception as e:
    print(f"Ошибка: {e}")