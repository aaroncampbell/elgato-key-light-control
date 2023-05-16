#!/bin/python
import os
import sys
import json
import socket
import requests
import time
import argparse
import ipaddress
from zeroconf import ServiceBrowser, Zeroconf # for discovery
# from pprint import pprint # for debugging

config_file = os.path.expanduser('~/.config/elgato.control.json')
default_port = 9123 # Port to use when IP is specified without port
lights = [] # Global that holds list of light obects

class Light():
    def __init__(self, name, location) -> None:
        self.name = name
        self.location = location

    def get_status( self, status: str='' ) -> dict|int:
        """Get status from light using endpoint
        Status includes:
          on/off
          brightness
          temperature

        Args:
            status (str, optional): specific item to get from status [on, brigtness, temperature]. Defaults to All.

        Returns:
            dict|int: Dict of status results or int representing value of specified status
        """
        response = requests.get( f"http://{self.location}/elgato/lights" )
        # TODO: Should this be stored in object? It can get stale by being changed from elsewhere
        self.status = response.json()["lights"][0]

        if status: # If a specific status item was requested
            return self.status.get( status )

        return self.status

    def friendly_status( self ) -> dict:
        """Get status, convert it to friendly format, and return it

        Status includes:
          on/off shown as string
          brightness shown as numerical percent
          temperature shown as Kelvin

        Returns:
            dict: Light status made more user-friendly
        """
        status = self.get_status()
        status['on'] = 'on' if status['on'] else 'off'
        status['brightness'] = str( status['brightness'] ) + '%'
        status['temperature'] = str( temperature_to_kelvin( status['temperature'] ) ) + 'K'

        return status

    def set_status( self, on:str|bool=None, brightness:str|int=None, temperature:str|int=None, **_) -> bool:
        """Set the status for light using endpoint
        Status includes:
          on/off
          brightness
          temperature

        Args:
            on (str | bool, optional): On|Off
            brightness (str | int, optional): Brightness as a percent - 3-100.
            temperature (str | int, optional): temperature as Kelvin (2900-7000) or raw number (143-344 which is 1000000/Kelvin).

        Returns:
            bool: success
        """
        status = {}

        if not on is None: # If on was specified
            if not isinstance( on, bool ): # If it's not already bool
                on = on_off_to_bool( on ) # convert to bool
            status['on'] = 1 if on else 0 # Light expects value of 1 or 0

        # TODO: Validate brightness as int 3-100
        if not brightness is None: # If brightness was specified
            # Trim % sign if it's there
            if isinstance( brightness, str ) and brightness[-1] == '%':
                brightness = brightness[0:-1]
            status['brightness'] = brightness

        # TODO: Validate temperature to be 143-344 (2900-7000k)
        if not temperature is None: # If temperature was specified
            # Trim 'k' if it's there
            if isinstance( temperature, str ) and temperature[-1].lower() == 'k':
                temperature = temperature[0:-1]
            # If temperature is >= 2900 it's probably Kelvin - convert it
            if temperature >= 2900:
                temperature = kelvin_to_temperature( temperature )
            status['temperature'] = temperature

        if not status:
            print( "Nothing to set. Please specify on, brightness, and/or temperature. See '-h' for usage.\n" )
            return

        # Format status to send to light
        status = {"numberOfLights":1,"lights":[status]}
        response = requests.put( f"http://{self.location}/elgato/lights", json=status )

        return response.ok

    def get_info( self, info: str='' ) -> dict|str|list|int:
        """Get info from light using endpoint
        Info includes:
            productName: str
            hardwareBoardType: int
            hardwareRevision: int
            macAddress: str
            firmwareBuildNumber: int
            firmwareVersion: str
            serialNumber: str
            displayName: str
            features: list,
            wifi-info: dict
                ssid: str
                frequencyMHz: int
                rssi: int

        Args:
            info (str, optional): specific item to get from info. Defaults to All.

        Returns:
            dict|int: Dict of status results or dict|str|list|int representing value of specified info
        """
        response = requests.get( f"http://{self.location}/elgato/accessory-info" )
        self.info = response.json()

        if info: # If a specific info item was requested
            return self.info.get( info )

        return self.info

def light_to_json( obj:Light ) -> dict:
    """Takes a Light object and turns it to a simple dict for easy JSON encoding

    Passes through any object that's not a Light so it can be used as 'default'
    parameter value for json.dump/dumps

    Args:
        obj (Light): Light to be converted to dict

    Returns:
        dict: Simple dict representation of light - 'name' and 'light' (location)
    """
    # If 'light' is an element in the object, we assume it's a Light object
    if isinstance( obj, Light ): # If this is a Light
        # Change "location" to "light" and return as dict with only name
        # and location for storing as JSON
        return { 'name': obj.name, 'light': obj.location }

    # Default behavior for all other types
    return obj

def light_from_json( dct:dict ) -> Light:
    """Takes dict representing light and returns a Light object for use in JSON decoding

    Passes through any dict that doesn't have a 'light' element so it can be
    used as 'object_hook' parameter value for json.load/loads

    Args:
        dct (dict): Simple dict representation of light - 'name' and 'light' (location)

    Returns:
        Light: Light created from data in dict
    """
    # If 'light' is an element in the dict, we assume it's a Light object
    if 'light' in dct:
        # Move "light" back to "location" and create Light object
        return Light( name=dct['name'], location=dct['light'] )

    # Default behavior for all other types
    return dct

class ElgatoListener():
    """Class listens for services being added, removed, or updated - used to locate lights
    """
    def __init__(self):
        self.lights = []

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"Service {name} updated")

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"Service {name} removed")

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        # Get info from found service
        info = zc.get_service_info(type_, name)

        # addresses seems to be a single item array of addresses stored in
        # binary network byte order. IP is pulled from the first item of the
        # array and converted to IPv4 using socket.inet_ntoa
        # Light is IP:Port
        light = Light( location=socket.inet_ntoa(info.addresses[0]) + ':' + str(info.port), name='' )

        # Pull light name from the displayName retrieved from the info enpoint
        light.name = light.get_info( "displayName" )

        # Append found light to lights array
        self.lights.append( light )

        # Announce that a light was found
        print( "%s found at: %s" % ( light.name, light.location ) )

def find_lights( interactive:bool=True ) -> list:
    """Listens for lights, saves the list into the config file, and returns the list

    Args:
        interactive (bool, optional): interactive prompts user to verify completion. Defaults to True.

    Returns:
        list: List of Light objects
    """
    print( "Finding Lights" )

    zeroconf = Zeroconf()
    listener = ElgatoListener()
    # Elgato lights can be found using '_elg._tcp.local.'
    ServiceBrowser(zeroconf, "_elg._tcp.local.", listener)

    try:
        count = 0
        # Keep looking until the user says we have found them all
        while (True):
            # Increment count
            count = count+1
            # Give our listener 5 seconds to locate lights
            time.sleep( 5 )

            if interactive:
                # Ask if we've found all the lights - defauls to yes
                done = input( f"Found {len( listener.lights )} lights, is that all of them? [Y/n] " ).lower()
                if  ( done in {'yes','y', 'ye', ''} ):
                    break
            elif len( listener.lights ) or count >= 3: # If not interactive, then end if we've found lights or have tried three times
                break

            # If they didn't say we found them all, let them know we're looking for more
            print( "Looking for more lights" )
    finally:
        zeroconf.close()

    # If we found lights, save them to the config file
    if listener.lights:
        with open( config_file, "w" ) as f:
            f.write( json.dumps( listener.lights, default=light_to_json, indent="\t" ) )

    # Return list of Light objects
    return listener.lights

def is_light_number( light_number:str ) -> bool:
    """Used to see if a specified light is actually a valid number from the list of lights

    Args:
        light_number (str): Number corresponding to a light in the list (index - 1)

    Returns:
        bool: True if it can represent a known light, False if not
    """
    try:
        light_number = int( light_number ) # See if the string is in an int
    except ValueError:
        return False # not an int, can't be a light number
    else:
        global lights
        # Return whether the number is between 1 & the number of lights we have
        return True if len( lights ) >= light_number and light_number > 0 else False

def maybe_load_lights_from_config():
    """If the lights global is empty, loads lights from the config file into into
    """
    global lights

    if not lights: # If global is empty
        try:
            with open( config_file ) as f:
                lights = json.load( f, object_hook=light_from_json )
        except:
            pass

def exit_with_help( error:str='' ):
    """Prints usage, then optional error string, then exits with a code of 1

    Args:
        error (str, optional): Error string to print below usage before exiting.
    """
    global parser
    parser.print_usage()
    if error:
        print( error )
    sys.exit(1)

def get_lights( requested_lights:list=[] ) -> list:
    """Gets a list of lights

    If requested_lights is specified, checks that they are possible lights
    Otherwise pulls lights from the config file, falling back to searching if
    there are none

    Args:
        requested_lights (list, optional): Lights to check and return. Defaults to [] which is "All".

    Returns:
        list: List of Light objects
    """
    global lights

    if requested_lights: # If requested lights were specified
        # Lights need to be loaded in order to support using light numbers as
        # shorthand. Since there's no way to know what order lights will return
        # in when searching, it only makes sense to reference them this way from
        # the config file where they can be seen using the `list` command
        maybe_load_lights_from_config()

        # Use enumerate to loop through requested_lights so we can modify each
        # item in the list to be a Light object as we validate it
        for i, light in enumerate( requested_lights ):
            if is_light_number( light ):
                # If this is a light number, replace the current item with the
                # specified one from the lights global
                requested_lights[i] = lights[int(light)-1]
            else:
                try:
                    if ':' in light: # If there's a ':' assume it's IP:PORT
                        ip, port = light.split( ':', 1 )
                    else:
                        # Assume the light was just an IP
                        ip = light
                        # If no port it specified then set it empty to fill later
                        port = ''

                    # If the IP is valid this will work. If not it will raise a ValueError
                    ip = ipaddress.ip_address( ip )

                    if not port: # if port is empty set it to the default port
                        global default_port
                        port = default_port
                    else:
                        # Enforce port to be numeric
                        try:
                            port = int( port )
                        except ValueError:
                            exit_with_help( f"Invalid port specified for light {light}" )

                    # We have a valid IP and Port so set current item to a light
                    # object using original specified string as name and setting
                    # light to IP:Port
                    requested_lights[i] = Light( name=light, location= ':'.join( [str(ip), str(port)] ) )
                except ValueError as e: # from ipaddress.ip_address() for invalid IP
                    exit_with_help( f"Invalid light specified: {light}" )

        # All requests lights could be valid, set the lights global to the specified list
        lights = requested_lights
        return lights # return requested lights
    else: # Lights weren't specified, default to all
        # Load lights from the config file into the global if it is empty
        maybe_load_lights_from_config()

        if lights: # If we have lights in the global, return them
            return lights

        # Find lights in non-interative mode
        lights = find_lights( False )

        return lights

def temperature_to_kelvin( temperature:int ) -> int:
    return 50 * round( 1000000 / temperature / 50 )

def kelvin_to_temperature( kelvin:int ) -> int:
    return round( 1000000 / kelvin )

def on_off_to_bool( string:str ) -> bool:
    """Converts a string representing on/off to bool

    Args:
        string (str): String representing on/off [on, off, 1, 0]

    Returns:
        bool: _description_
    """
    if isinstance( string, bool ): # If this is already boolean, return it
        return string
    if not isinstance( string, str ): # If it's not a string, then convert
        string = str( string )
    # Return True in cases of 'on' or '1'. Assume all others are off and return False
    return string.lower() == 'on' or string == '1'

def brightness_from_str( brightness:str ) -> int|bool:
    # If brightness is a string ending in '%', trim the '%'
    if isinstance( brightness, str ) and brightness[-1] == '%':
        brightness = brightness[0:-1]

    try:
        return int( brightness ) # Return brightness as an int
    except ValueError:
        return False # not an int, can't be a brightness


def is_valid_brightness( brightness:int ) -> bool:
    # If not already an int, enforce that
    if not isinstance( brightness, int ):
        brightness = brightness_from_str( brightness=brightness )

    # True if 3-100, False otherwise
    return not ( brightness > 100 or brightness < 3 )

def brightness_value( brightness_string:str ) -> int:
    if isinstance( brightness, int ):
        brightness = brightness_string # already an int, just use it
    else:
        # Normalize strings like '50' or '50%' to int
        brightness = brightness_from_str( brightness=brightness_string )

    if not is_valid_brightness( brightness ):
        raise argparse.ArgumentTypeError( "invalid brightness value: %r (valid is whole number 3-100)" % brightness_string )
    return brightness

def temperature_value( temperature_string:str ) -> int:
    # If the temperature ends in a k, strip it
    if temperature_string[-1].lower() == 'k':
        temperature_string = temperature_string[0:-1]
    temperature = int( temperature_string )
    if temperature > 7000 or temperature < 2900 or temperature % 50:
        raise argparse.ArgumentTypeError( "invalid temperature value: %r (valid is 2900-7000k in increments of 50)" % temperature_string )
    return temperature

def command_toggle( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        light.set_status( on=( not on_off_to_bool( light.get_status( 'on' ) ) ) )

def command_on( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        light.set_status( on=True )

def command_off( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        light.set_status( on=False )

def command_status( args ):
    lights = get_lights( args['lights'] )
    for light in lights:
        print( f"Status for {light.name}:" )
        print( json.dumps( light.friendly_status(), default=light_to_json, indent=4 ) )

def command_info( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        print( f"Info for {light.name}:" )
        print( json.dumps( light.get_info(), default=light_to_json, indent=4 ) )

def command_brighter( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        light.set_status( brightness=( light.get_status( 'brightness' ) + 5 ) )

def command_dimmer( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        light.set_status( brightness=( light.get_status( 'brightness' ) - 5 ) )

def command_warmer( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        light.set_status( temperature=( light.get_status( 'temperature' ) + 5 ) )

def command_cooler( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        light.set_status( temperature=( light.get_status( 'temperature' ) - 5 ) )

def command_set( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        light.set_status( **args)

def command_list( args ):
    lights = get_lights( args['lights'] )

    for index, light in enumerate( lights ):
        print( f"[{index+1}] {light.name} ({light.location})" )

def command_test( args ):
    lights = get_lights( args['lights'] )
    test = [ -1, 0, 1, 3, 100, 123, '3', '100', 'abc' ]

    for brightness in test:
        valid = is_valid_brightness( brightness )
        print( f"Testing '{brightness}', result: {valid}" )

parser = argparse.ArgumentParser( description='Control Elgato Lights.' )
subparsers = parser.add_subparsers( title='commands', metavar='Use -h or --help with any command for command-specific help' )

parent_parser = argparse.ArgumentParser(add_help=False)
parent_parser.add_argument( '--light', dest='lights', action='append', metavar='LIGHT', help='Light to target as number (from %(prog)s list) or IP:PORT. Can include multiple times.' )

parser_find = subparsers.add_parser('find', aliases=['search'], help='Find lights' )
parser_find.set_defaults( func=find_lights )

parser_list = subparsers.add_parser('list', help='List lights', parents=[parent_parser] )
parser_list.set_defaults( func=command_list )

parser_toggle = subparsers.add_parser('toggle', help='Toggle lights on or off', parents=[parent_parser] )
parser_toggle.set_defaults( func=command_toggle )

parser_on = subparsers.add_parser('on', help='Turn lights on', parents=[parent_parser] )
parser_on.set_defaults( func=command_on )

parser_off = subparsers.add_parser('off', help='Turn lights off', parents=[parent_parser] )
parser_off.set_defaults( func=command_off )

parser_status = subparsers.add_parser('status', help='Check the status of lights', parents=[parent_parser] )
parser_status.set_defaults( func=command_status )

parser_info = subparsers.add_parser('info', help='Get info on lights', parents=[parent_parser] )
parser_info.set_defaults( func=command_info )

parser_brighter = subparsers.add_parser('brighter', help='Make lights brighter', parents=[parent_parser] )
parser_brighter.set_defaults( func=command_brighter )

parser_dimmer = subparsers.add_parser('dimmer', help='Make lights dimmer', parents=[parent_parser] )
parser_dimmer.set_defaults( func=command_dimmer )

parser_warmer = subparsers.add_parser('warmer', help='Adjust temperature of lights warmer', parents=[parent_parser] )
parser_warmer.set_defaults( func=command_warmer )

parser_cooler = subparsers.add_parser('cooler', help='Adjust temperature of lights cooler', parents=[parent_parser] )
parser_cooler.set_defaults( func=command_cooler )

parser_set = subparsers.add_parser('set', help='Set status for lights, including on/off, brightness, and temperature', parents=[parent_parser])
parser_set.set_defaults( func=command_set )
on_off_group = parser_set.add_mutually_exclusive_group()
on_off_group.add_argument( '-o', dest='on', type=on_off_to_bool, help='Whether to set the light(s) on or off', metavar='ON|OFF')
on_off_group.add_argument('--on', action='store_true', dest='on')
on_off_group.add_argument('--off', action='store_false', dest='on')
parser_set.add_argument( '-b', '--brightness', type=brightness_value, help='Brightness for light - percentage from 3 to 100', metavar="3-100")
parser_set.add_argument( '-t', '--temperature', type=temperature_value, help='Temperature for light - Kelvin from 2900k - 7000k (increments of 50)', metavar="2900-7000k (increments of 50)")

parser.add_argument( '--version', action='version', version='%(prog)s 0.0.1' )

parser_test = subparsers.add_parser('test', help='For Testing', parents=[parent_parser] )
parser_test.set_defaults( func=command_test )


args = parser.parse_args()

if hasattr( args, 'func' ) and callable( args.func ):
    args.func( vars( args ) )
    sys.exit()

# If no function was found to process, show help
parser.print_help()
