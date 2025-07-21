import network

import time
from machine import Pin, Timer
import bluetooth
from micropython import const
from umqtt.simple import MQTTClient
from config import WIFI_SSID, WIFI_PASSWORD, QINGPING_MAC, RUUVI_MAC, MQTT_BROKER, MQTT_USERNAME, MQTT_PASSWORD, MQTT_PORT

# LED setup
led = Pin("LED", Pin.OUT)
led_state = False

# BLE Scanner setup
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)
_QINGPING_UUID = const(0xFDCD)
_RUUVI_COMPANY_ID = const(0x0499)

# MQTT settings
MQTT_CLIENT_ID = "pico_ble_scanner"
MQTT_QINGPING_TOPIC = "homeassistant/sensor/qingping"
MQTT_RUUVI_TOPIC = "homeassistant/sensor/ruuvi"

# Timer for LED blinking
def blink_timer(timer):
    global led_state
    led_state = not led_state
    led.value(led_state)

# Create timer for LED blinking
timer = Timer()
timer.init(period=1000, mode=Timer.PERIODIC, callback=blink_timer)

# Add a second timer for BLE scanning
ble_timer = Timer()
global_scanner = None

class BLEScanner:
    def __init__(self):
        print("Initializing BLE Scanner...")
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self.ble_irq)
        self.mqtt_client = None
        self.mqtt_connected = False
        self.connect_mqtt()
        self.devices_seen_this_scan = set()  # Track devices seen during current scan
        print("BLE Scanner initialized and active")

    def connect_mqtt(self):
        """Connect or reconnect to MQTT broker with retry logic"""
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                print(f"Attempting MQTT connection (attempt {retry_count + 1}/{max_retries})...")
                self.mqtt_client = MQTTClient(
                    MQTT_CLIENT_ID,
                    MQTT_BROKER,
                    port=MQTT_PORT,
                    user=MQTT_USERNAME,
                    password=MQTT_PASSWORD
                )
                self.mqtt_client.connect()
                self.mqtt_connected = True
                print("Connected to MQTT broker")
                return True
            except Exception as e:
                retry_count += 1
                print(f"MQTT connection failed: {e}")
                if retry_count < max_retries:
                    print(f"Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    print("Max MQTT connection retries reached")
                    self.mqtt_connected = False
                    return False

    def publish_mqtt(self, topic, payload):
        """Publish to MQTT with automatic reconnection"""
        if not self.mqtt_connected:
            print("MQTT not connected, attempting reconnection...")
            if not self.connect_mqtt():
                print("Failed to reconnect to MQTT, skipping publish")
                return False
        
        try:
            self.mqtt_client.publish(topic, payload)
            return True
        except Exception as e:
            print(f"MQTT publish failed: {e}")
            self.mqtt_connected = False
            # Try to reconnect and publish again
            if self.connect_mqtt():
                try:
                    self.mqtt_client.publish(topic, payload)
                    return True
                except Exception as e2:
                    print(f"MQTT publish failed after reconnection: {e2}")
                    return False
            return False

    def ble_irq(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            addr_str = ':'.join(['%02x' % i for i in addr])

            # Skip if we've already seen this device in this scan
            if addr_str in self.devices_seen_this_scan:
                return

            if addr_str == QINGPING_MAC:
                self.devices_seen_this_scan.add(addr_str)  # Mark as seen
                qingping_data = self.parse_qingping_data(adv_data)
                if qingping_data:
                    import json
                    payload = json.dumps(qingping_data)
                    if self.publish_mqtt(MQTT_QINGPING_TOPIC, payload):
                        print("Published Qingping data:", payload)
                        timer.init(period=500, mode=Timer.PERIODIC, callback=blink_timer)
                    else:
                        print("Failed to publish Qingping data")

            elif addr_str == RUUVI_MAC:
                self.devices_seen_this_scan.add(addr_str)  # Mark as seen
                ruuvi_data = self.parse_ruuvi_data(adv_data)
                if ruuvi_data:
                    import json
                    payload = json.dumps(ruuvi_data)
                    if self.publish_mqtt(MQTT_RUUVI_TOPIC, payload):
                        print("Published Ruuvi data:", payload)
                        timer.init(period=500, mode=Timer.PERIODIC, callback=blink_timer)
                    else:
                        print("Failed to publish Ruuvi data")

        elif event == _IRQ_SCAN_DONE:
            print("Scan complete")
            self.devices_seen_this_scan.clear()  # Clear the set for next scan
            timer.init(period=1000, mode=Timer.PERIODIC, callback=blink_timer)

    def parse_qingping_data(self, adv_data):
        i = 0
        while i < len(adv_data):
            length = adv_data[i]
            if i + 1 < len(adv_data):
                type_id = adv_data[i + 1]
                if type_id == 0x16:  # Service Data
                    service_uuid = int.from_bytes(adv_data[i + 2:i + 4], 'little')
                    if service_uuid == _QINGPING_UUID:
                        service_data = adv_data[i + 4:i + length + 1]
                        if len(service_data) >= 14:
                            temp_raw = int.from_bytes(service_data[10:12], 'little')
                            temp = temp_raw / 10.0
                            hum_raw = int.from_bytes(service_data[12:14], 'little')
                            humidity = hum_raw / 10.0
                            return {
                                'temperature': temp,
                                'humidity': humidity
                            }
            i += length + 1
        return None

    def parse_ruuvi_data(self, adv_data):
        i = 0
        while i < len(adv_data):
            length = adv_data[i]
            if i + 1 < len(adv_data):
                type_id = adv_data[i + 1]
                if type_id == 0xFF:  # Manufacturer Data
                    company_id = int.from_bytes(adv_data[i + 2:i + 4], 'little')
                    if company_id == _RUUVI_COMPANY_ID:
                        mfg_data = adv_data[i + 2:i + length + 1]
                        if len(mfg_data) > 2 and mfg_data[2] == 0x05:  # Data format 5
                            temp_raw = int.from_bytes(mfg_data[3:5], 'big', True)
                            temp = temp_raw * 0.005
                            hum_raw = int.from_bytes(mfg_data[5:7], 'big')
                            humidity = hum_raw * 0.0025
                            pressure_raw = int.from_bytes(mfg_data[7:9], 'big')
                            pressure = (pressure_raw + 50000) / 100
                            return {
                                'temperature': round(temp, 2),
                                'humidity': round(humidity, 2),
                                'pressure': round(pressure, 2)
                            }
            i += length + 1
        return None

    def start_scan(self):
        print("Starting BLE scan...")
        self.ble.gap_scan(10000, 30000, 30000)

    def cleanup(self):
        """Clean up MQTT connection"""
        if self.mqtt_connected and self.mqtt_client:
            try:
                self.mqtt_client.disconnect()
                print("MQTT disconnected cleanly")
            except:
                pass
            self.mqtt_connected = False

def connect_wifi():
    print("Connecting to WiFi...")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    max_wait = 10
    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        max_wait -= 1
        print('Waiting for connection...')
        time.sleep(1)

    if wlan.status() != 3:
        raise RuntimeError('Network connection failed')
    else:
        print('Connected')
        status = wlan.ifconfig()
        print('IP:', status[0])
        return status[0]

def ble_scan_timer(timer):
    print("Starting periodic BLE scan...")
    global global_scanner
    if global_scanner:
        global_scanner.start_scan()

def main():
    print("Starting main program...")
    try:
        # Initialize BLE scanner
        global global_scanner
        global_scanner = BLEScanner()
        print("Starting initial BLE scan...")
        global_scanner.start_scan()
        time.sleep(1)  # Give time for initial scan

        # Setup periodic BLE scanning
        ble_timer.init(period=60000, mode=Timer.PERIODIC, callback=ble_scan_timer)

        # Keep program running
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("Program terminated by user")
    except Exception as e:
        print(f"Error in main: {e}")
        raise e
    finally:
        if global_scanner:
            global_scanner.cleanup()  # Clean up MQTT connection
        ble_timer.deinit()  # Clean up BLE timer
        timer.deinit()  # Clean up LED timer

if __name__ == '__main__':
    print("Program starting...")
    connect_wifi()  # Connect to WiFi first
    main()