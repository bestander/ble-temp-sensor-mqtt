# Ruuvi Tag Temperature Monitor with Raspberry Pi Pico W

This project uses a Raspberry Pi Pico W to read temperature data from a Ruuvi Tag via Bluetooth Low Energy (BLE) and expose it to HomeKit through Homebridge.

## Hardware Requirements
- Raspberry Pi Pico W
- Ruuvi Tag (Data Format 5)

## Software Requirements
- MicroPython for Raspberry Pi Pico W
- Homebridge
- homebridge-http-temperature plugin

## Features
- BLE scanning for Ruuvi Tag data
- Temperature, humidity, and pressure monitoring
- Web server for data access
- LED status indicators:
  - 1 second blink: Server running normally
  - 0.5 second blink: New temperature data received
- HomeKit integration via Homebridge

## Setup Instructions

### 1. Pico W Setup
1. Flash MicroPython to your Pico W
2. Copy both `main.py` and `config.py` to the Pico W
3. Update the settings in `config.py`:
   ```python
   RUUVI_MAC = 'your_ruuvi_mac_here'  # Your Ruuvi Tag MAC address
   WIFI_SSID = 'your_wifi_name'        # Your WiFi network name
   WIFI_PASSWORD = 'your_wifi_pass'    # Your WiFi password
   ```

### 2. Homebridge Setup
1. Install the homebridge-http-temperature plugin
2. Add this to your Homebridge config:
   ```json
   {
       "accessories": [
           {
               "accessory": "HttpTemperature",
               "name": "Ruuvi Tag",
               "getUrl": "http://YOUR_PICO_IP:8000",
               "httpMethod": "GET",
               "temperatureKey": "temperature",
               "humidity": true,
               "humidityKey": "humidity",
               "updateInterval": 60000
           }
       ]
   }
   ```

## How It Works
1. The Pico W connects to your WiFi network
2. It continuously scans for BLE advertisements from your Ruuvi Tag
3. When data is received, it parses the temperature, humidity, and pressure
4. A web server exposes this data via HTTP
5. Homebridge polls this endpoint and updates HomeKit
6. LED indicates system status:
   - Slow blink = Server running
   - Fast blink = New data received

## API Endpoint
- URL: `http://PICO_IP:8000`
- Method: GET
- Response Format:
  ```json
  {
      "temperature": 23.5,
      "humidity": 45.2,
      "pressure": 1013.2
  }
  ```

## Troubleshooting
- LED not blinking: Check power and code upload
- No BLE data: Verify Ruuvi Tag MAC address
- No web server: Check WiFi credentials
- No HomeKit data: Verify Homebridge configuration

## Credits
- Based on Ruuvi Tag Data Format 5 specification
- Uses MicroPython BLE and networking libraries
- Integrates with Homebridge for HomeKit support 