# Elgato Key Light Control
A simple Bash script that allows you to control your Elgato Key Lights from the command line. I bind several of the commands to keyboard shortcuts to make it even easier.

## Introduction
The Elgato [Key Light](https://www.elgato.com/en/key-light) and [Key Light Air](https://www.elgato.com/en/key-light-air) are edge-lit LED video lights that are popular with live streamers ... and people that do a lot of video calls (🙋). They're IoT devices and are normally controlled with Elgato's 'Control Center' app or through one of the Stream Deck devices (also manufactered by Elgato). Unfortunately, linux support is sorely lacking (non-existant from Elgato), but they can be controlled by directly interfacing with the lights' built-in API which I found thanks to [@adamesch](https://github.com/adamesch/) and their [Elgato Key Light API](https://github.com/adamesch/elgato-key-light-api/) repo.

## Usage

### On/Off/Toggle
Turn on, off, or toggle all lights
```bash
elgato on      # Turn on all lights
elgato off     # Turn off all lights
elgato toggle  # Turn all currently on lights off and all currently off lights on
```

### Set
Set the on/off status, brightness, and/or temperature for all lights

**Args**
```
-o   Specify the on or off status for all lights (on|off)
-b   Specify the brightness for all lights (3-100)
-t   Specify the temperature for all lights (2900-7000k)
```

> **Note**  
> The temperature is specified in Kelvin from 2900 to 7000, but internally is represented by a whole number from 143-344. The conversion is done by rounding (1,000,000 / Kelvin) to a whole number.

**Examples**
```bash
# Usage: elgato set [ -o ON on|off ] [ -b BRIGHTNESS 3-100 ] [ -t TEMPERATURE 2900-7000k ]"
elgato set -o on                # Turn on all lights
elgato set -b 28                # Set brightness to 28 on all lights
elgato set -t 3400              # Set temperature to 294 (3400K) on all lights
elgato set -b 28 -t 3400k       # Set brightness to 28 and temperature to 294 (3400K) on all lights
elgato set -o on -b 28 -t 3400  # Turn on all lights and set their brightness to 28 and temperature to 294 (3400K)
```

### Brighter/Dimmer
Adjust the brightness of all lights up or down by 5%
```bash
elgato brighter  # Make all lights 5% brighter
elgato dimmer    # Make all lights 5% dimmer
```

### Warmer/Cooler
Adjust the temperature of all lights up or down by 5
```bash
elgato warmer  # Make all lights warmer (higher internal number, lower Kelvin - see note)
elgato cooler  # Make all lights cooler (lower internal number, higher Kelvin - see note)
```
> **Note**  
> The temperature is specified as a number from 143-344. To calculate Kelvin use (1,000,000 / Temperature) and usually round the nearest 10 or 50 to match to most UIs.

### Get Light Statuses
Get Status for all lights
```bash
elgato status
```

Returns a list of lights, showing the location (IP:port) of each and a JSON representation of the settings for each
```
Status for light at 192.168.1.107:9123:
{
  "on": 1,
  "brightness": 28,
  "temperature": 294
}

Status for light at 192.168.1.108:9123:
{
  "on": 1,
  "brightness": 33,
  "temperature": 270
}
```
> **Note**  
> The temperature is specified as a number from 143-344. To calculate Kelvin use (1,000,000 / Temperature) and usually round the nearest 10 or 50 to match to most UIs.

### Get Light Statuses
Get Status for all lights
```bash
elgato info
```

Returns a list of lights, showing the location (IP:port) of each and a JSON representation of the info for each
```
Info for light at 192.168.1.107:9123:
{
  "productName": "Elgato Key Light Air",
  "hardwareBoardType": 200,
  "hardwareRevision": 1,
  "macAddress": "00:00:00:00:00:00",
  "firmwareBuildNumber": 218,
  "firmwareVersion": "1.0.3",
  "serialNumber": "XX00X0X00000",
  "displayName": "Desk Right",
  "features": [
    "lights"
  ],
  "wifi-info": {
    "ssid": "ssid_name",
    "frequencyMHz": 2400,
    "rssi": -29
  }
}

Status for light at 192.168.1.108:9123:
{
  "productName": "Elgato Key Light Air",
  "hardwareBoardType": 200,
  "hardwareRevision": 1,
  "macAddress": "00:00:00:00:00:00",
  "firmwareBuildNumber": 218,
  "firmwareVersion": "1.0.3",
  "serialNumber": "XX00X0X00000",
  "displayName": "Desk Left",
  "features": [
    "lights"
  ],
  "wifi-info": {
    "ssid": "ssid_name",
    "frequencyMHz": 2400,
    "rssi": -29
  }
}
```
