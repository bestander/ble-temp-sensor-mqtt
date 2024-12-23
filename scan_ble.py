import bluetooth
from micropython import const
import time
import socket
import json
from config import RUUVI_MAC, QINGPING_MAC

# BLE Constants
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)
_QINGPING_UUID = const(0xFDCD)
_RUUVI_COMPANY_ID = const(0x0499)

# Web server settings
HTTP_PORT = 8000

class BLESensorServer:
    def __init__(self):
        # Initialize BLE
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self.ble_irq)
        self.scanning = False
        
        # Store latest sensor data
        self.sensor_data = {
            'qingping': None,
            'ruuvi': None
        }
        
        # Initialize web server
        self.start_webserver()

    def start_webserver(self):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        addr = socket.getaddrinfo('0.0.0.0', HTTP_PORT)[0][-1]
        self.sock.bind(addr)
        self.sock.listen(1)
        print(f'Web server listening on port {HTTP_PORT}')

    def handle_web_request(self):
        try:
            cl, addr = self.sock.accept()
            request = cl.recv(1024).decode()
            
            response_data = None
            if 'GET /1' in request:  # Qingping endpoint
                response_data = self.sensor_data['qingping']
            elif 'GET /2' in request:  # Ruuvi endpoint
                response_data = self.sensor_data['ruuvi']
            
            if response_data:
                response = json.dumps(response_data)
                cl.send('HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n')
                cl.send(response)
            else:
                cl.send('HTTP/1.0 404 Not Found\r\n\r\n')
            
            cl.close()
        except Exception as e:
            print(f"Web server error: {e}")
            try:
                cl.close()
            except:
                pass

    def scan(self, duration_ms=5000):
        print("Starting BLE scan...")
        self.scanning = True
        self.ble.gap_scan(duration_ms, 30000, 30000)
        
        while self.scanning:
            self.handle_web_request()  # Handle web requests during scanning
            time.sleep_ms(100)

    def parse_qingping(self, service_data):
        try:
            if len(service_data) >= 14:
                temp_raw = int.from_bytes(service_data[10:12], 'little')
                temp = temp_raw / 10.0
                
                hum_raw = int.from_bytes(service_data[12:14], 'little')
                humidity = hum_raw / 10.0
                
                return {
                    'temperature': temp,
                    'humidity': humidity
                }
        except Exception as e:
            print(f"Error parsing Qingping data: {e}")
        return None

    def parse_ruuvi(self, mfg_data):
        try:
            if len(mfg_data) > 2 and mfg_data[2] == 0x05:
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
        except Exception as e:
            print(f"Error parsing Ruuvi data: {e}")
        return None

    def ble_irq(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            addr_str = ':'.join(['%02x' % i for i in addr])
            
            # Check for our specific devices
            if addr_str == QINGPING_MAC:
                i = 0
                while i < len(adv_data):
                    length = adv_data[i]
                    type_id = adv_data[i + 1]
                    if type_id == 0x16:  # Service Data
                        service_uuid = int.from_bytes(adv_data[i + 2:i + 4], 'little')
                        if service_uuid == _QINGPING_UUID:
                            parsed = self.parse_qingping(adv_data[i + 4:i + length + 1])
                            if parsed:
                                self.sensor_data['qingping'] = parsed
                                print(f"Updated Qingping data: {parsed}")
                    i += length + 1
                    
            elif addr_str == RUUVI_MAC:
                i = 0
                while i < len(adv_data):
                    length = adv_data[i]
                    type_id = adv_data[i + 1]
                    if type_id == 0xFF:  # Manufacturer Data
                        company_id = int.from_bytes(adv_data[i + 2:i + 4], 'little')
                        if company_id == _RUUVI_COMPANY_ID:
                            parsed = self.parse_ruuvi(adv_data[i + 2:i + length + 1])
                            if parsed:
                                self.sensor_data['ruuvi'] = parsed
                                print(f"Updated Ruuvi data: {parsed}")
                    i += length + 1

        elif event == _IRQ_SCAN_DONE:
            print("Scan complete, restarting...")
            # Restart scanning immediately
            self.ble.gap_scan(30000, 30000, 30000)

# Create server and start continuous operation
server = BLESensorServer()
while True:
    try:
        server.scan(30000)  # Scan for 30 seconds
    except Exception as e:
        print(f"Error in main loop: {e}")
        time.sleep(1)
