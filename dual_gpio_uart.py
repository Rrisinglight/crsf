#!/usr/bin/env python3
"""
Контроллер UART с раздельным управлением RX/TX через два GPIO
с использованием библиотеки gpiod для современных Raspberry Pi.
"""

import serial
import time
import threading
from typing import Optional, Callable
import gpiod
import logging

class DualGPIO_UART:
    """
    Класс для работы с UART, где направление RX и TX
    контролируется двумя отдельными GPIO пинами через gpiod.
    """

    DIRECTION_SWITCH_DELAY = 0.00005 # 50мкс задержка на переключение направления

    def __init__(self, port: str, baudrate: int, tx_en_pin: int, rx_en_pin: int, chip_name: str = "gpiochip0", invert: bool = False):
        self.port = port
        self.baudrate = baudrate
        self.tx_en_pin = tx_en_pin
        self.rx_en_pin = rx_en_pin
        self.chip_name = chip_name # На RPi5 обычно 'gpiochip0' (pinctrl-rp1)
        self.invert = invert

        self.ser: Optional[serial.Serial] = None
        self.chip: Optional[gpiod.Chip] = None
        self.tx_line: Optional[gpiod.Line] = None
        self.rx_line: Optional[gpiod.Line] = None

        self.is_running = False
        self._reader_thread: Optional[threading.Thread] = None
        self._data_callback: Optional[Callable[[bytes], None]] = None
        self._lock = threading.Lock()
        
        # Настраиваем логирование
        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)


    def _setup_gpio(self):
        """Настройка GPIO с использованием gpiod."""
        try:
            self.chip = gpiod.Chip(self.chip_name)
            self.tx_line = self.chip.get_line(self.tx_en_pin)
            self.rx_line = self.chip.get_line(self.rx_en_pin)
            
            self.tx_line.request(consumer="uart_tx_en", type=gpiod.LINE_REQ_DIR_OUT, default_vals=[0])
            self.rx_line.request(consumer="uart_rx_en", type=gpiod.LINE_REQ_DIR_OUT, default_vals=[1]) # RX enabled by default
            self.logger.info(f"GPIO пины {self.tx_en_pin} и {self.rx_en_pin} на чипе {self.chip_name} настроены.")
        except Exception as e:
            self.logger.error(f"Ошибка настройки GPIO через gpiod: {e}")
            self.logger.error(f"Убедитесь, что вы используете правильное имя чипа (для вашей системы это, вероятно, '{self.chip_name}').")
            self.logger.error("Доступные чипы можно посмотреть командой: gpiodetect")
            raise

    def set_data_callback(self, callback: Callable[[bytes], None]):
        """Устанавливает функцию обратного вызова для принятых данных."""
        self._data_callback = callback

    def start(self):
        """Открывает порт и запускает поток чтения."""
        if self.is_running:
            return
        
        self._setup_gpio()
        
        self.logger.info(f"Открытие UART порта {self.port} с управлением через gpiod...")
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.01)
        except serial.SerialException as e:
            self.logger.error(f"Ошибка открытия порта {self.port}: {e}")
            raise

        self.is_running = True
        self._set_direction_rx() # Set to receive by default
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
        self.logger.info("UART запущен.")

    def stop(self):
        """Останавливает поток чтения и закрывает порт."""
        if not self.is_running:
            return

        self.is_running = False
        if self._reader_thread:
            self._reader_thread.join()
        
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.logger.info("UART порт закрыт.")

        if self.tx_line:
            self.tx_line.release()
        if self.rx_line:
            self.rx_line.release()
        if self.chip:
            self.chip.close()
        self.logger.info("GPIO ресурсы освобождены.")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def _set_direction_tx(self):
        """Настраивает GPIO для передачи."""
        self.rx_line.set_value(0)
        self.tx_line.set_value(1)

    def _set_direction_rx(self):
        """Настраивает GPIO для приема."""
        self.tx_line.set_value(0)
        self.rx_line.set_value(1)

    def send(self, data: bytes) -> bool:
        """Отправляет данные в UART."""
        if not self.ser or not self.is_running:
            return False
        
        with self._lock:
            self._set_direction_tx()
            time.sleep(self.DIRECTION_SWITCH_DELAY)
            try:
                write_data = data
                if self.invert:
                    write_data = bytes(b ^ 0xFF for b in data)
                self.ser.write(write_data)
                self.ser.flush()
                time.sleep((len(write_data) * 10.0 / self.baudrate) + self.DIRECTION_SWITCH_DELAY)
            except serial.SerialException as e:
                self.logger.error(f"Ошибка записи в UART: {e}")
                return False
            finally:
                self._set_direction_rx()
        return True

    def _read_loop(self):
        """Основной цикл чтения данных из порта."""
        while self.is_running:
            try:
                if self.ser and self.ser.is_open and self.ser.in_waiting > 0:
                    with self._lock:
                        # Убедимся, что мы в режиме приема.
                        # Это может быть избыточно, но надежно.
                        self._set_direction_rx()
                        data = self.ser.read(self.ser.in_waiting)
                    
                    if data:
                        if self.invert:
                            data = bytes(b ^ 0xFF for b in data)

                        if self._data_callback:
                            try:
                                self._data_callback(data)
                            except Exception as e:
                                self.logger.error(f"Ошибка в callback: {e}")
            except serial.SerialException as e:
                self.logger.error(f"Критическая ошибка порта: {e}")
                self.is_running = False
                break
            except Exception as e:
                self.logger.error(f"Неожиданная ошибка в цикле чтения: {e}")

            time.sleep(0.001)

    @property
    def is_open(self) -> bool:
        """Проверяет, открыт ли порт."""
        return self.ser and self.ser.is_open if self.is_running else False