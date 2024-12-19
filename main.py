import network
import socket
import time
import json
from machine import Pin, Timer
import bluetooth
from micropython import const
from config import *

# LED setup
led = Pin("LED", Pin.OUT)
led_state = False

# BLE Scanner setup
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)

# Ruuvi tag settings
RUUVI_DATA_FORMAT = 5  # Ruuvi uses data format 5

# HTTP server settings
HTTP_PORT = 8000

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
global_scanner = None  # Global variable to store scanner instance

class BLEScanner:
    def __init__(self):
        print("Initializing BLE Scanner...")
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self.ble_irq)
        self.latest_data = None
        print("BLE Scanner initialized and active")
        
    def ble_irq(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            addr = ':'.join(['%02x' % i for i in addr])
            if addr.lower() == RUUVI_MAC.lower():
                print(f"Found Ruuvi tag! Raw data: {adv_data.hex()}")
                self.parse_ruuvi_data(adv_data)
                # Change to fast blinking when data received
                timer.init(period=500, mode=Timer.PERIODIC, callback=blink_timer)
        elif event == _IRQ_SCAN_DONE:
            print("Scan complete")
            # Return to normal blinking after scan
            timer.init(period=1000, mode=Timer.PERIODIC, callback=blink_timer)
    
    def parse_ruuvi_data(self, data):
        print(f"Parsing data: {data.hex()}")
        try:
            # Looking for Ruuvi manufacturer data
            i = 0
            while i < len(data):
                length = data[i]
                if i + 1 < len(data):
                    type_id = data[i + 1]
                    if type_id == 0xFF:  # Manufacturer Specific Data
                        mfg_data = data[i + 2:i + length + 1]
                        if mfg_data[0:2] == b'\x99\x04':  # Ruuvi manufacturer ID
                            print("Found Ruuvi manufacturer data")
                            if mfg_data[2] == RUUVI_DATA_FORMAT:
                                print("Found data format 5")
                                # Format 5 parsing
                                temp = int.from_bytes(mfg_data[3:5], 'big') * 0.005
                                # Convert to signed value if necessary
                                if temp > 32767:
                                    temp -= 65536
                                humidity = int.from_bytes(mfg_data[5:7], 'big') * 0.0025
                                pressure = int.from_bytes(mfg_data[7:9], 'big') + 50000
                                
                                self.latest_data = {
                                    'temperature': temp,
                                    'humidity': humidity,
                                    'pressure': pressure / 100
                                }
                                print(f"Parsed data: {self.latest_data}")
                                return
                i += length + 1
            print("No Ruuvi data found in packet")
        except Exception as e:
            print(f"Error parsing data: {e}")
    
    def start_scan(self):
        print("Starting BLE scan...")
        self.ble.gap_scan(10000, 30000, 30000)

def connect_wifi():
    print("Connecting to WiFi...")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    
    # Wait for connection
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

def start_webserver(ip, scanner):
    print("Starting web server...")
    addr = socket.getaddrinfo(ip, HTTP_PORT)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        s.bind(addr)
        s.listen(1)
        print(f'Listening on http://{ip}:{HTTP_PORT}')
        
        # Initialize LED state
        led.value(0)  # Start with LED off
        
        while True:
            try:
                # Handle web requests
                cl, addr = s.accept()
                request = cl.recv(1024).decode()
                
                if 'GET' in request:
                    response = {
                        'temperature': scanner.latest_data['temperature'] if scanner.latest_data else None,
                        'humidity': scanner.latest_data['humidity'] if scanner.latest_data else None,
                        'pressure': scanner.latest_data['pressure'] if scanner.latest_data else None
                    }
                    
                    response_json = json.dumps(response)
                    response_str = f'HTTP/1.0 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(response_json)}\r\nAccess-Control-Allow-Origin: *\r\n\r\n{response_json}'
                    
                    cl.send(response_str.encode())
                
                cl.close()
                
            except Exception as e:
                print('Error in connection handler:', e)
                try:
                    cl.close()
                except:
                    pass
                time.sleep(0.1)
    finally:
        timer.deinit()  # Clean up timer when done
        s.close()
        print("Server socket closed")

def ble_scan_timer(timer):
    print("Starting periodic BLE scan...")
    global global_scanner
    if global_scanner:
        global_scanner.start_scan()

def main():
    print("Starting main program...")
    try:
        # Initialize BLE scanner first
        global global_scanner
        global_scanner = BLEScanner()
        print("Starting initial BLE scan...")
        global_scanner.start_scan()
        time.sleep(1)  # Give time for initial scan
        
        # Setup periodic BLE scanning
        ble_timer.init(period=30000, mode=Timer.PERIODIC, callback=ble_scan_timer)
        
        # Then connect to WiFi and start web server
        ip = connect_wifi()
        start_webserver(ip, global_scanner)
    except KeyboardInterrupt:
        print("Program terminated by user")
    except Exception as e:
        print(f"Error in main: {e}")
        raise e
    finally:
        ble_timer.deinit()  # Clean up BLE timer

if __name__ == '__main__':
    print("Program starting...")
    main()