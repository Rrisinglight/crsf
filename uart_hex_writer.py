import serial
import time

PORT = '/dev/serial0'
BAUDRATE = 115200

def invert_byte(byte_val):
    """Инвертировать байт (XOR с 0xFF)"""
    return byte_val ^ 0xFF

try:
    with serial.Serial(PORT, BAUDRATE, timeout=1) as ser:
        print(f"Открыт порт {PORT} на скорости {BAUDRATE}")
        while True:
            for i in range(1, 17):  # от 1 до 16
                byte_to_send = (0x55).to_bytes(1, 'big')
                ser.write(byte_to_send)
                print(f"Отправлено: {byte_to_send.hex()}")
                time.sleep(0.5)

except KeyboardInterrupt:
    print("\nПрограмма завершена пользователем.")
except Exception as e:
    print(f"Ошибка: {e}") 