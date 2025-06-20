#!/usr/bin/env python3
import time

# --- Тест библиотеки RPi.GPIO ---
try:
    import RPi.GPIO as GPIO
    print("1. Библиотека RPi.GPIO импортирована успешно.")
    
    GPIO.setmode(GPIO.BCM)
    print("2. Режим GPIO.BCM установлен.")

    TEST_PIN = 24 # Любой свободный пин
    GPIO.setup(TEST_PIN, GPIO.OUT)
    print(f"3. Пин {TEST_PIN} успешно настроен как выход (OUT).")

    print("\n✅✅✅ ТЕСТ ПРОЙДЕН! Библиотека RPi.GPIO работает.")

except Exception as e:
    print("\n❌❌❌ ТЕСТ ПРОВАЛЕН!")
    print(f"   ОШИБКА: {e}")
    print("\n   Это подтверждает, что проблема в самой библиотеке RPi.GPIO, а не в коде проекта.")

finally:
    try:
        GPIO.cleanup()
        print("\nGPIO очищен.")
    except NameError:
        # Если импорт упал, GPIO не будет определен
        pass 