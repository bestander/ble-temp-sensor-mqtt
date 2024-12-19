import network
import socket
import time
import json
from machine import Pin, Timer
import bluetooth
from micropython import const
from config import WIFI_SSID, WIFI_PASSWORD, QINGPING_MAC, RUUVI_MAC

# LED setup
led = Pin("LED", Pin.OUT)
led_state = False

# BLE Scanner setup
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)
_QINGPING_UUID = const(0xFDCD)
_RUUVI_COMPANY_ID = const(0x0499)

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
global_scanner = None

class BLEScanner:
    def __init__(self):
        print("Initializing BLE Scanner...")
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self.ble_irq)
        self.qingping_data = None
        self.ruuvi_data = None
        self.last_qingping_update = 0
        self.last_ruuvi_update = 0
        self.devices_seen_this_scan = set()  # Track devices seen during current scan
        print("BLE Scanner initialized and active")
        
    def ble_irq(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            addr_str = ':'.join(['%02x' % i for i in addr])
            
            # Skip if we've already seen this device in this scan
            if addr_str in self.devices_seen_this_scan:
                return
            
            if addr_str == QINGPING_MAC:
                self.devices_seen_this_scan.add(addr_str)  # Mark as seen
                self.parse_qingping_data(adv_data)
                print("Qingping data updated:", self.qingping_data)
                timer.init(period=500, mode=Timer.PERIODIC, callback=blink_timer)
            
            elif addr_str == RUUVI_MAC:
                self.devices_seen_this_scan.add(addr_str)  # Mark as seen
                self.parse_ruuvi_data(adv_data)
                print("Ruuvi data updated:", self.ruuvi_data)
                timer.init(period=500, mode=Timer.PERIODIC, callback=blink_timer)
                
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
                            
                            self.qingping_data = {
                                'temperature': temp,
                                'humidity': humidity
                            }
                            return
            i += length + 1

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
                            
                            self.ruuvi_data = {
                                'temperature': round(temp, 2),
                                'humidity': round(humidity, 2),
                                'pressure': round(pressure, 2)
                            }
                            return
            i += length + 1
    
    def start_scan(self):
        print("Starting BLE scan...")
        self.ble.gap_scan(10000, 30000, 30000)

def start_webserver(ip, scanner):
    print("Starting web server...")
    addr = socket.getaddrinfo(ip, HTTP_PORT)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        s.bind(addr)
        s.listen(1)
        print(f'Listening on http://{ip}:{HTTP_PORT}')
        
        while True:
            try:
                cl, addr = s.accept()
                request = cl.recv(1024).decode()
                
                response = None
                if 'GET /1' in request:  # Qingping endpoint
                    response = scanner.qingping_data
                elif 'GET /2' in request:  # Ruuvi endpoint
                    response = scanner.ruuvi_data
                
                if response:
                    response_json = json.dumps(response)
                    response_str = f'HTTP/1.0 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(response_json)}\r\nAccess-Control-Allow-Origin: *\r\n\r\n{response_json}'
                else:
                    response_str = 'HTTP/1.0 404 Not Found\r\n\r\n'
                
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
        timer.deinit()
        s.close()
        print("Server socket closed")

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
        # Initialize BLE scanner first
        global global_scanner
        global_scanner = BLEScanner()
        print("Starting initial BLE scan...")
        global_scanner.start_scan()
        time.sleep(1)  # Give time for initial scan
        
        # Setup periodic BLE scanning
        ble_timer.init(period=60000, mode=Timer.PERIODIC, callback=ble_scan_timer)
        
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