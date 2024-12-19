# Temperature Monitor with Raspberry Pi Pico W

This project uses a Raspberry Pi Pico W to read temperature data from Qingping and Ruuvi Tag sensors via Bluetooth Low Energy (BLE) and expose it to HomeKit through Homebridge.

## Hardware Requirements
- Raspberry Pi Pico W
- Qingping Temperature/Humidity Sensor
- Ruuvi Tag (Data Format 5)

## Software Requirements
- MicroPython for Raspberry Pi Pico W
- Homebridge
- homebridge-http-temperature plugin

## Features
- BLE scanning for both Qingping and Ruuvi Tag data
- Temperature and humidity monitoring for both sensors
- Additional pressure monitoring for Ruuvi Tag
- Web server with separate endpoints for each sensor
- LED status indicators:
  - 1 second blink: Server running normally
  - 0.5 second blink: New temperature data received
- HomeKit integration via Homebridge

## Files
- `main.py`: Main program that handles BLE scanning and web server
- `config.py`: Configuration file for WiFi and sensor MAC addresses
- `scan_ble.py`: Utility script to scan and identify BLE devices

## Setup Instructions

### 1. Pico W Setup
1. Flash MicroPython to your Pico W
2. Copy `main.py` and `config.py` to the Pico W
3. Update the settings in `config.py`:
   ```python
   QINGPING_MAC = 'your_qingping_mac_here'  # Your Qingping sensor MAC address
   RUUVI_MAC = 'your_ruuvi_mac_here'        # Your Ruuvi Tag MAC address
   WIFI_SSID = 'your_wifi_name'             # Your WiFi network name
   WIFI_PASSWORD = 'your_wifi_pass'          # Your WiFi password
   ```

### 2. Finding Your Sensors
1. Use `scan_ble.py` to find your sensors' MAC addresses:
   ```bash
   mpremote run scan_ble.py
   ```
2. Look for devices with service UUID 0xFDCD (Qingping) and manufacturer ID 0x0499 (Ruuvi)
3. Note the MAC addresses and update `config.py`

### 3. Homebridge Setup
1. Install the homebridge-http-temperature-humidity plugin
2. Add this to your Homebridge config for each sensor:
   ```json
   {
       "accessories": [
                {
            "accessory": "HttpTemphum",
            "name": "QingPing",
            "url": "http://YOUR_PICO_IP:8000/1",
            "http_method": "GET"
        },
        {
            "accessory": "HttpTemphum",
            "name": "Ruuvi tag",
            "url": "http://YOUR_PICO_IP:8000/2",
            "http_method": "GET"
        }          
       ]
   }
   ```

## How It Works
1. The Pico W connects to your WiFi network
2. It scans for BLE advertisements every minute
3. When data is received from either sensor, it's parsed and stored
4. A web server exposes the data via two endpoints:
   - `/1`: Qingping sensor data (temperature, humidity)
   - `/2`: Ruuvi Tag data (temperature, humidity, pressure)
5. Homebridge polls these endpoints and updates HomeKit
6. LED indicates system status:
   - Slow blink = Server running
   - Fast blink = New data received

## API Endpoints
- Qingping Sensor: `http://PICO_IP:8000/1`
  ```json
  {
      "temperature": 23.5,
      "humidity": 45.2
  }
  ```
- Ruuvi Tag: `http://PICO_IP:8000/2`
  ```json
  {
      "temperature": 23.5,
      "humidity": 45.2,
      "pressure": 1013.2
  }
  ```

## Troubleshooting
- LED not blinking: Check power and code upload
- No BLE data: Verify sensor MAC addresses
- No web server: Check WiFi credentials
- No HomeKit data: Verify Homebridge configuration

## Credits
- Uses MicroPython BLE and networking libraries
- Integrates with Homebridge for HomeKit support
- Supports Qingping and Ruuvi Tag BLE protocols