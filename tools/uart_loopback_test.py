import serial
import time

PORT = '/dev/serial0'
BAUDRATE = 115200

try:
    with serial.Serial(PORT, BAUDRATE, timeout=1) as ser:
        
        byte_to_send = b'A'
        
        ser.write(byte_to_send)
        
        time.sleep(0.1) 

        data_received = ser.read(ser.in_waiting)

        print(f"Отправлено: {byte_to_send.decode()}")
        print(f"Получено:   {data_received.decode()}")

except Exception as e:
    print(f"Ошибка: {e}")