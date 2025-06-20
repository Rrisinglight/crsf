import serial
import time

PORT = '/dev/serial0'
BAUDRATE = 115200

try:
    with serial.Serial(PORT, BAUDRATE, timeout=1) as ser:
        
        data_to_send = b'echo_test'
        
        ser.write(data_to_send)
        
        time.sleep(0.1) 

        data_received = ser.read(ser.in_waiting)

        print(f"Отправлено: {data_to_send}")
        print(f"Получено:   {data_received}")

except Exception as e:
    print(f"Ошибка: {e}")