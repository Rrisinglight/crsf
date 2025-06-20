#!/usr/bin/env python3
"""
Контроллер UART с раздельным управлением RX/TX через два GPIO
с использованием библиотеки gpiod для современных Raspberry Pi.
"""

import serial
import time
import threading
from typing import Optional
import gpiod

class DualGPIO_UART:
    """
    Класс для работы с UART, где направление RX и TX
    контролируется двумя отдельными GPIO пинами через gpiod.
    """

    def __init__(self, port: str, baudrate: int, tx_en_pin: int, rx_en_pin: int, chip_name: str = "gpiochip4"):
        self.port = port
        self.baudrate = baudrate
        self.tx_en_pin = tx_en_pin
        self.rx_en_pin = rx_en_pin
        self.chip_name = chip_name # На RPi5 обычно 'gpiochip4' для внешних пинов

        self.ser: Optional[serial.Serial] = None
        self.chip: Optional[gpiod.Chip] = None
        self.tx_line: Optional[gpiod.Line] = None
        self.rx_line: Optional[gpiod.Line] = None

        self.is_running = False
        self._reader_thread: Optional[threading.Thread] = None
        self._data_callback = None
        self._lock = threading.Lock()

    def _setup_gpio(self):
        """Настройка GPIO с использованием gpiod."""
        try:
            self.chip = gpiod.Chip(self.chip_name)
            self.tx_line = self.chip.get_line(self.tx_en_pin)
            self.rx_line = self.chip.get_line(self.rx_en_pin)
            
            self.tx_line.request(consumer="uart_tx_en", type=gpiod.LINE_REQ_DIR_OUT, default_vals=[0])
            self.rx_line.request(consumer="uart_rx_en", type=gpiod.LINE_REQ_DIR_OUT, default_vals=[0])
            print(f"GPIO пины {self.tx_en_pin} и {self.rx_en_pin} на чипе {self.chip_name} настроены.")
        except Exception as e:
            print(f"Ошибка настройки GPIO через gpiod: {e}")
            print("Убедитесь, что вы используете правильное имя чипа (на RPi 5 это gpiochip4).")
            print("Доступные чипы можно посмотреть командой: ls /dev/gpiochip*")
            raise

    def set_data_callback(self, callback):
        """Устанавливает функцию обратного вызова для принятых данных."""
        self._data_callback = callback

    def start(self):
        """Открывает порт и запускает поток чтения."""
        if self.is_running:
            return
        
        self._setup_gpio()
        
        print(f"Открытие UART порта {self.port} с управлением через gpiod...")
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.01)
        except serial.SerialException as e:
            print(f"Ошибка открытия порта {self.port}: {e}")
            raise

        self.is_running = True
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
        print("UART запущен.")

    def stop(self):
        """Останавливает поток чтения и закрывает порт."""
        if not self.is_running:
            return

        self.is_running = False
        if self._reader_thread:
            self._reader_thread.join()
        
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("UART порт закрыт.")

        if self.tx_line:
            self.tx_line.release()
        if self.rx_line:
            self.rx_line.release()
        if self.chip:
            self.chip.close()
        print("GPIO ресурсы освобождены.")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def _set_direction_tx(self):
        """Настраивает GPIO для передачи."""
        self.rx_line.set_value(0)
        self.tx_line.set_value(1)
        time.sleep(0.001)

    def _set_direction_rx(self):
        """Настраивает GPIO для приема."""
        self.tx_line.set_value(0)
        self.rx_line.set_value(1)
        time.sleep(0.001)

    def send(self, data: bytes) -> bool:
        """Отправляет данные в UART."""
        if not self.ser or not self.is_running:
            return False
        
        with self._lock:
            self._set_direction_tx()
            try:
                self.ser.write(data)
                self.ser.flush() # Ждем завершения передачи
            except serial.SerialException as e:
                print(f"Ошибка записи в UART: {e}")
                return False
            finally:
                # После отправки всегда переключаемся обратно в режим приема
                self._set_direction_rx()
        return True

    def _read_loop(self):
        """Основной цикл чтения данных из порта."""
        # Устанавливаем начальное состояние на прием
        self._set_direction_rx()

        while self.is_running:
            try:
                # Читаем данные, если они есть
                if self.ser and self.ser.in_waiting > 0:
                    with self._lock:
                        # Временно выключаем приемник, чтобы избежать эха от своих же данных
                        # если схема это предполагает. Для большинства схем это не нужно.
                        # Если нужно, можно добавить GPIO.output(self.rx_en_pin, GPIO.LOW)
                        
                        data = self.ser.read(self.ser.in_waiting)
                        
                        # Возвращаем приемник в активное состояние
                        # GPIO.output(self.rx_en_pin, GPIO.HIGH)

                    if data and self._data_callback:
                        try:
                            self._data_callback(data)
                        except Exception as e:
                            print(f"Ошибка в callback: {e}")
            except serial.SerialException as e:
                print(f"Критическая ошибка порта: {e}")
                self.is_running = False
                break
            except Exception as e:
                print(f"Неожиданная ошибка в цикле чтения: {e}")

            time.sleep(0.005) # Небольшая пауза, чтобы не грузить процессор 