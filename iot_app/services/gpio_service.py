try:
    import RPi.GPIO as GPIO
    GPIO_IMPORT_OK = True
except Exception:
    GPIO_IMPORT_OK = False

    class _MockGPIO:
        BCM = "BCM"
        OUT = "OUT"
        IN = "IN"
        LOW = 0
        HIGH = 1

        @staticmethod
        def setmode(_mode):
            return None

        @staticmethod
        def setup(_pin, _mode, initial=None):
            return None

        @staticmethod
        def input(_pin):
            return 1

        @staticmethod
        def output(_pin, _value):
            return None

        @staticmethod
        def cleanup():
            return None

    GPIO = _MockGPIO()


class GPIOService:
    def __init__(self, config, state, logger):
        self.config = config
        self.state = state
        self.logger = logger

    def init_gpio(self):
        if not GPIO_IMPORT_OK:
            self.state.update(gpio_ready=False, gpio_error="RPi.GPIO not installed")
            return False

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.config.red_pin, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(self.config.green_pin, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(self.config.buzzer_pin, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(self.config.pir_pin, GPIO.IN)
            self.state.update(gpio_ready=True, gpio_error=None)
            return True
        except Exception as exc:
            self.state.update(gpio_ready=False, gpio_error=str(exc))
            self.logger.exception("GPIO init failed")
            return False

    def set_alert_outputs(self, active):
        if not self.state.snapshot()["gpio_ready"]:
            return
        state = GPIO.HIGH if active else GPIO.LOW
        try:
            GPIO.output(self.config.red_pin, state)
            GPIO.output(self.config.buzzer_pin, state)
        except Exception:
            self.logger.exception("GPIO output failed")

    def set_status_led(self, red_on=False, green_on=False):
        if not self.state.snapshot()["gpio_ready"]:
            return
        try:
            GPIO.output(self.config.red_pin, GPIO.HIGH if red_on else GPIO.LOW)
            GPIO.output(self.config.green_pin, GPIO.HIGH if green_on else GPIO.LOW)
        except Exception:
            self.logger.exception("GPIO LED output failed")

    def read_motion_sensor(self):
        if not self.state.snapshot()["gpio_ready"]:
            return True
        try:
            return GPIO.input(self.config.pir_pin) == GPIO.HIGH
        except Exception:
            self.logger.exception("GPIO input failed")
            return False

    def cleanup(self):
        try:
            GPIO.cleanup()
        except Exception:
            self.logger.exception("GPIO cleanup failed")
