#!/usr/bin/env python3
"""
Half-Duplex UART управление через SN74LVC1T45
"""

import time
import serial
import threading
from typing import Callable, Optional
try:
    import RPi.GPIO as GPIO
except ImportError:
    # Заглушка для разработки на не-Pi системах
    class MockGPIO:
        BCM = "BCM"
        OUT = "OUT" 
        HIGH = 1
        LOW = 0
        def setmode(self, mode): pass
        def setup(self, pin, mode): pass
        def output(self, pin, value): pass
        def cleanup(self): pass
    GPIO = MockGPIO()

class HalfDuplexUART:
    def __init__(self, port: str, baudrate: int = 416666, dir_pin: int = 18, 
                 tx_timeout: float = 0.001, rx_timeout: float = 0.010):
        """
        Инициализация Half-Duplex UART
        
        Args:
            port: UART порт (/dev/serial0)
            baudrate: Скорость UART (416666 для CRSF)
            dir_pin: GPIO пин для управления направлением SN74LVC1T45
            tx_timeout: Время ожидания после передачи перед переключением в RX
            rx_timeout: Время ожидания в RX режиме
        """
        self.port = port
        self.baudrate = baudrate
        self.dir_pin = dir_pin
        self.tx_timeout = tx_timeout
        self.rx_timeout = rx_timeout
        
        self.serial = None
        self.is_tx_mode = False
        self.is_running = False
        self.rx_callback: Optional[Callable[[bytes], None]] = None
        
        # Настройка GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.dir_pin, GPIO.OUT)
        self._set_rx_mode()
        
        # Поток для чтения
        self.rx_thread = None
        self.thread_lock = threading.Lock()
        
    def start(self):
        """Запуск UART"""
        if self.is_running:
            return
            
        self.serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.001  # Короткий timeout для неблокирующего чтения
        )
        
        self.is_running = True
        self.rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self.rx_thread.start()
        
    def stop(self):
        """Остановка UART"""
        self.is_running = False
        
        if self.rx_thread:
            self.rx_thread.join(timeout=1.0)
            
        if self.serial:
            self.serial.close()
            self.serial = None
            
        GPIO.cleanup()
        
    def set_rx_callback(self, callback: Callable[[bytes], None]):
        """Устанавливает callback для получения данных"""
        self.rx_callback = callback
        
    def _set_tx_mode(self):
        """Переключение в режим передачи (DIR = HIGH)"""
        if not self.is_tx_mode:
            GPIO.output(self.dir_pin, GPIO.HIGH)
            self.is_tx_mode = True
            time.sleep(0.0001)  # Короткая задержка на переключение
            
    def _set_rx_mode(self):
        """Переключение в режим приема (DIR = LOW)"""
        if self.is_tx_mode:
            GPIO.output(self.dir_pin, GPIO.LOW)
            self.is_tx_mode = False
            time.sleep(0.0001)  # Короткая задержка на переключение
            
    def send(self, data: bytes) -> bool:
        """
        Отправка данных
        
        Args:
            data: Данные для отправки
            
        Returns:
            True если отправка успешна
        """
        if not self.serial or not self.is_running:
            return False
            
        with self.thread_lock:
            try:
                # Переключаемся в TX режим
                self._set_tx_mode()
                
                # Очищаем буферы
                self.serial.reset_input_buffer()
                self.serial.reset_output_buffer()
                
                # Отправляем данные
                self.serial.write(data)
                self.serial.flush()
                
                # Ждем завершения передачи
                time.sleep(self.tx_timeout)
                
                # Переключаемся обратно в RX режим
                self._set_rx_mode()
                
                return True
                
            except Exception as e:
                print(f"Ошибка отправки UART: {e}")
                self._set_rx_mode()
                return False
                
    def _rx_loop(self):
        """Основной цикл чтения данных"""
        while self.is_running:
            try:
                if not self.is_tx_mode and self.serial and self.serial.in_waiting > 0:
                    data = self.serial.read(self.serial.in_waiting)
                    if data and self.rx_callback:
                        self.rx_callback(data)
                        
                time.sleep(0.001)  # Короткая пауза
                
            except Exception as e:
                if self.is_running:  # Только логируем ошибки если еще работаем
                    print(f"Ошибка чтения UART: {e}")
                    time.sleep(0.01)
                    
    def __enter__(self):
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

class UARTBridge:
    """Базовый класс для UART моста"""
    
    def __init__(self, port: str, baudrate: int = 416666, dir_pin: int = 18):
        self.uart = HalfDuplexUART(port, baudrate, dir_pin)
        self.is_running = False
        
    def start(self):
        """Запуск моста"""
        self.uart.set_rx_callback(self._on_uart_data)
        self.uart.start()
        self.is_running = True
        
    def stop(self):
        """Остановка моста"""
        self.is_running = False
        self.uart.stop()
        
    def send_to_uart(self, data: bytes) -> bool:
        """Отправка данных в UART"""
        return self.uart.send(data)
        
    def _on_uart_data(self, data: bytes):
        """Обработчик данных от UART (переопределить в наследниках)"""
        pass
        
    def __enter__(self):
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()