# Temperature Monitor with Raspberry Pi Pico W

This project uses a Raspberry Pi Pico W to read temperature data from Qingping and Ruuvi Tag sensors via Bluetooth Low Energy (BLE) and publishes the data via MQTT for Home Assistant integration, as well as exposing it through a web server for Homebridge/HomeKit.

## Hardware Requirements
- Raspberry Pi Pico W
- Qingping Temperature/Humidity Sensor
- Ruuvi Tag (Data Format 5)

## Software Requirements
- MicroPython for Raspberry Pi Pico W
- MQTT Broker (e.g., Mosquitto)
- Home Assistant (optional)
- Homebridge (optional)
- homebridge-http-temperature plugin (optional)

## Features
- BLE scanning for both Qingping and Ruuvi Tag data
- Temperature and humidity monitoring for both sensors
- Additional pressure monitoring for Ruuvi Tag
- MQTT publishing for Home Assistant integration
- Web server with separate endpoints for each sensor (Homebridge compatibility)
- LED status indicators:
  - 1 second blink: Server running normally
  - 0.5 second blink: New temperature data received
- HomeKit integration via Homebridge (optional)
- Home Assistant integration via MQTT

## Files
- `main.py`: Main program that handles BLE scanning, MQTT publishing, and web server
- `config.py`: Configuration file for WiFi, sensor MAC addresses, and MQTT settings
- `scan_ble.py`: Utility script to scan and identify BLE devices
- `lib/umqtt/`: MQTT client library for MicroPython

## Setup Instructions

### 1. Pico W Setup
1. Flash MicroPython to your Pico W
2. Copy `main.py`, `config.py`, and the `lib/` folder to the Pico W
3. Update the settings in `config.py`:
   ```python
   QINGPING_MAC = 'your_qingping_mac_here'  # Your Qingping sensor MAC address
   RUUVI_MAC = 'your_ruuvi_mac_here'        # Your Ruuvi Tag MAC address
   WIFI_SSID = 'your_wifi_name'             # Your WiFi network name
   WIFI_PASSWORD = 'your_wifi_pass'          # Your WiFi password
   
   # MQTT Configuration
   MQTT_BROKER = 'your_mqtt_broker_ip'      # Your MQTT broker IP address
   MQTT_PORT = 1883
   MQTT_USERNAME = 'pico_mqtt'              # MQTT username
   MQTT_PASSWORD = 'your_mqtt_password'     # MQTT password
   ```

### 2. Finding Your Sensors
1. Use `scan_ble.py` to find your sensors' MAC addresses:
   ```bash
   mpremote run scan_ble.py
   ```
2. Look for devices with service UUID 0xFDCD (Qingping) and manufacturer ID 0x0499 (Ruuvi)
3. Note the MAC addresses and update `config.py`

### 3. MQTT Broker Setup
1. Install and configure an MQTT broker (e.g., Mosquitto)
2. Create a user account for the Pico W:
   ```yaml
   logins:
     - username: pico_mqtt
       password: your_mqtt_password
   ```
3. Update the MQTT settings in `config.py` to match your broker configuration

### 4. Home Assistant Setup (Optional)
The sensors will automatically appear in Home Assistant when MQTT discovery is enabled. The data is published to:
- Qingping: `homeassistant/sensor/qingping`
- Ruuvi Tag: `homeassistant/sensor/ruuvi`

### 5. Homebridge Setup (Optional)
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
2. It connects to your MQTT broker for data publishing
3. It scans for BLE advertisements continuously
4. When data is received from either sensor, it's parsed and:
   - Published to MQTT topics for Home Assistant
   - Stored locally for web server access
5. A web server exposes the data via two endpoints:
   - `/1`: Qingping sensor data (temperature, humidity)
   - `/2`: Ruuvi Tag data (temperature, humidity, pressure)
6. Homebridge polls these endpoints and updates HomeKit (if configured)
7. LED indicates system status:
   - Slow blink = Server running
   - Fast blink = New data received

## API Endpoints

### Web Server Endpoints (for Homebridge)
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

### MQTT Topics (for Home Assistant)
- Qingping data: `homeassistant/sensor/qingping`
- Ruuvi Tag data: `homeassistant/sensor/ruuvi`

Data format includes temperature, humidity, and pressure (Ruuvi only) with appropriate Home Assistant discovery configuration.

## Troubleshooting
- LED not blinking: Check power and code upload
- No BLE data: Verify sensor MAC addresses in `config.py`
- No web server: Check WiFi credentials in `config.py`
- No HomeKit data: Verify Homebridge configuration
- MQTT connection failed: Check MQTT broker settings and credentials
- "Not authorised" MQTT error: Verify username/password match broker configuration
- No Home Assistant discovery: Check MQTT broker connection and topic names

## Credits
- Uses MicroPython BLE and networking libraries
- MQTT functionality via umqtt.simple library
- Integrates with Home Assistant via MQTT discovery
- Integrates with Homebridge for HomeKit support
- Supports Qingping and Ruuvi Tag BLE protocols