# Elgato Key Light Control
A simple Python script that allows you to control your Elgato Key Lights from the command line. I bind several of the commands to keyboard shortcuts to make it even easier.

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

### List
List lights - the numbers shown can be used to [specify lights](#specifying-lights)
```bash
elgato list    # List lights
```

**Sample Output**
```
[1] Aaron Desk Right (192.168.1.107:9123)
[2] Aaron Desk Left (192.168.1.108:9123)
```

### Specifying Lights
Specifying lights is supported by all commands that control or query lights (not find/search)
```bash
# Turn on light #1 as seen in `elgato list`
elgato on --light 1
# Turn on light #1 & 3 as seen in `elgato list`
elgato on --light 1 --light 3
# Turn on light at 192.168.1.107:9123
elgato on --light 192.168.1.107:9123
# Turn on light at 192.168.1.107:9123 (port assumed not detected)
elgato on --light 192.168.1.107
# Turn on light #1 as seen in `elgato list` & light at 192.168.1.107:9123
elgato on --light 1 --light 192.168.1.107:9123
```

### Set
Set the on/off status, brightness, and/or temperature for all lights

**Args**
```bash
--light LIGHT    Light to target as number (from elgato set list) or IP:PORT. Can include multiple times.
-o ON|OFF        Whether to set the light(s) on or off
--on             Same as "-o on"
--off            Same as "-o off"
-b               Brightness for light - percentage from 3 to 100
--brightness     Same as -b
-t               Temperature for light - Kelvin from 2900k - 7000k (increments of 50)
--temperature    Same as -t
```

> **Note**
> The temperature is specified in Kelvin from 2900 to 7000, but internally is represented by a whole number from 143-344. The conversion is done by rounding (1,000,000 / Kelvin) to a whole number.

**Examples**
```bash
# Usage: elgato set [ -o ON on|off ] [ -b BRIGHTNESS 3-100 ] [ -t TEMPERATURE 2900-7000k ]"
elgato set -o on                # Turn on all lights
elgato set --off                # Turn off all lights
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
> The temperature is specified internally as a number from 143-344, and this is what is adjusted by 5. To calculate Kelvin use (1,000,000 / Temperature) and usually round the nearest 50.

### Get Light Statuses
Get Status for all lights
```bash
elgato status
```

Returns a list of lights, showing the location (IP:port) of each and a JSON representation of the settings for each
```
Status for Aaron Desk Right:
{
    "on": "on",
    "brightness": "18%",
    "temperature": "3400K"
}

Status for light at 192.168.1.108:9123:
{
    "on": "on",
    "brightness": "22%",
    "temperature": "3450K"
}
```

### Get Light Statuses
Get Status for all lights
```bash
elgato info
```

Returns a list of lights, showing a JSON representation of the info for each
```
Info for Aaron Desk Right:
{
    "productName": "Elgato Key Light Air",
    "hardwareBoardType": 200,
    "hardwareRevision": 1,
    "macAddress": "00:00:00:00:00:00",
    "firmwareBuildNumber": 218,
    "firmwareVersion": "1.0.3",
    "serialNumber": "XX00X0X00000",
    "displayName": "Aaron Desk Right",
    "features": [
        "lights"
    ],
    "wifi-info": {
        "ssid": "Campbell",
        "frequencyMHz": 2400,
        "rssi": -40
    }
}

Info for Aaron Desk Left:
{
    "productName": "Elgato Key Light Air",
    "hardwareBoardType": 200,
    "hardwareRevision": 1,
    "macAddress": "00:00:00:00:00:00",
    "firmwareBuildNumber": 218,
    "firmwareVersion": "1.0.3",
    "serialNumber": "XX00X0X00000",
    "displayName": "Aaron Desk Left",
    "features": [
        "lights"
    ],
    "wifi-info": {
        "ssid": "Campbell",
        "frequencyMHz": 2400,
        "rssi": -40
    }
}
```

### Find
Find lights - once found they are stored in `~/.config/elgato.control.json`
You do not have to run this before using this script, it will run in non-interactive mode if no lights are in the config file. If you add or remove lights from your network, you can run this to refresh the config file.
```bash
elgato find    # Search for lights and store them in config file
```
