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
lights = []

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

        # addresses seems to be a single item array of addresses stored in binary network byte order
        # IP is pulled from the first item of the array, converted to IPv4 using socket.inet_ntoa
        # Light is IP:Port
        light = socket.inet_ntoa(info.addresses[0]) + ':' + str(info.port)

        light_name = get_light_info( light, "displayName" )
        # light object includes name and "light" stored as IP:Port
        # print("IP tpye: %s, Port type: %s" % (type( socket.inet_ntoa(info.addresses[0]) ), type(info.port)) )
        # light={ "name": info.get_name(), "light": light}

        # Append found light to lights array
        self.lights.append( { "name": light_name, "light": light} )

        # Announce that a light was found
        print( "%s found at: %s" % (light_name, light))

def find_lights( interactive:bool=True ):
    print( "Finding Lights" )

    # from zeroconf import ZeroconfServiceTypes
    # print('\n'.join(ZeroconfServiceTypes.find()))

    zeroconf = Zeroconf()
    listener = ElgatoListener()
    browser = ServiceBrowser(zeroconf, "_elg._tcp.local.", listener)
    # browser = ServiceBrowser(zeroconf, "_alexa._tcp.local.", listener)
    # browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)
    # browser = ServiceBrowser(zeroconf, "_googlecast._tcp.local.", listener)
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
            f.write( json.dumps( listener.lights, indent="\t" ) )

    return listener.lights

def is_light_number( light_number:str ) -> bool:
    try:
        light_number = int( light_number )
    except ValueError:
        return False # not an int, can't be a light number
    else:
        global lights
        return True if len( lights ) >= light_number and light_number > 0 else False

def maybe_load_lights_from_config():
    global lights

    if not lights:
        try:
            with open( config_file ) as f:
                lights = json.load(f)
        except:
            pass

def exit_with_help( error:str='' ):
    global parser
    parser.print_usage()
    if error:
        print( error )
    sys.exit(1)

def get_lights( requested_lights:list=[]):
    global lights

    if requested_lights:
        maybe_load_lights_from_config()

        for i, light in enumerate( requested_lights ):
            if is_light_number( light ):
                requested_lights[i] = lights[int(light)-1]
            else:
                try:
                    if ':' in light:
                        ip, port = light.split( ':', 1 )
                    else:
                        ip = light
                        port = ''

                    ip = ipaddress.ip_address( ip )

                    if not port:
                        global default_port
                        port = default_port
                    else:
                        # Enforce port to be numeric
                        try:
                            port = int( port )
                        except ValueError:
                            exit_with_help( f"Invalid port specified for light {light}" )

                    requested_lights[i] = { 'name': light, 'light': ':'.join( [str(ip), str(port)] ) }
                except ValueError as e:
                    exit_with_help( f"Invalid light specified: {light}" )

        lights = requested_lights

    if lights:
        return lights

    try:
        with open( config_file ) as f:
            lights = json.load(f)
    except (FileNotFoundError, ValueError) as e:
        # Find lights in non-interative mode
        lights = find_lights( False )

    return lights

def get_light_status( light: str, status: str='' ) -> str:
    response = requests.get( f"http://{get_light_location( light )}/elgato/lights" )
    light_status = response.json()
    light_status = light_status["lights"][0]

    if status:
        light_status = light_status.get( status )

    return light_status

def set_light_status( light, args ):

    status = {}

    if not args.get('on') is None:
        if not isinstance( args['on'], bool ):
            args['on'] = on_off_to_bool( args['on'] )
        status['on'] = 1 if args['on'] else 0

    if not args.get('brightness') is None:
        if isinstance( args['brightness'], str ) and args['brightness'][-1] == '%':
            args['brightness'] = args['brightness'][0:-1]
        status['brightness'] = args['brightness']

    if not args.get('temperature') is None:
        if isinstance( args['temperature'], str ) and args['temperature'][-1].lower() == 'k':
            args['temperature'] = args['temperature'][0:-1]
        if args['temperature'] >= 2900:
            args['temperature'] = kelvin_to_temperature( args['temperature'] )
        status['temperature'] = args['temperature']

    if not status:
        print( "Nothing to set. Please specify on, brightness, and/or temperature. See '-h' for usage.\n" )
        return

    # Format status to send to light
    status = {"numberOfLights":1,"lights":[status]}
    response = requests.put( f"http://{get_light_location( light )}/elgato/lights", json=status )

    return response.ok

def get_light_info( light: str, info: str='' ) -> str:
    response = requests.get( f"http://{get_light_location( light )}/elgato/accessory-info" )
    light_info = response.json()

    if info:
        light_info = light_info.get( info )

    return light_info

def friendly_status( status:dict ) -> dict:
    status['on'] = 'on' if status['on'] else 'off'
    status['brightness'] = str( status['brightness'] ) + '%'
    status['temperature'] = str( temperature_to_kelvin( status['temperature'] ) ) + 'K'

    return status

def get_light_location( light ) -> str:
    if isinstance( light, str ):
        return light
    if isinstance( light, dict ):
        return light['light']
    if isinstance( light, object):
        return light.light

def temperature_to_kelvin( temperature:int ) -> int:
    return 50 * round( 1000000 / temperature / 50 )

def kelvin_to_temperature( kelvin:int ) -> int:
    return round( 1000000 / kelvin )

def on_off_to_bool( string:str ) -> bool:
    if not isinstance( string, str ):
        string = str( string )
    return string.lower() == 'on' or string == '1'

def resolve_to_on_off( string:str ) -> bool:
    string = string.lower()
    if string == '1':
        return 'on'
    elif string == '0':
        return 'off'
    return string

def brightness_value( brightness_string:str ) -> int:
    brightness = int( brightness_string )
    if brightness > 100 or brightness < 3:
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
        set_light_status( light, { 'on': 0 if on_off_to_bool( get_light_status( light, 'on' ) ) else 1 } )

def command_on( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        set_light_status( light, { 'on': True } )

def command_off( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        set_light_status( light, { 'on': False } )

def command_status( args ):
    lights = get_lights( args['lights'] )
    for light in lights:
        print( f"Status for {light['name']}:" )
        print( json.dumps( friendly_status( get_light_status( light["light"] ) ), indent=4 ) )

def command_info( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        print( f"Info for {light['name']}:" )
        print( json.dumps( get_light_info( light["light"] ), indent=4 ) )

def command_brighter( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        set_light_status( light, { 'brightness': get_light_status( light, 'brightness' )+5 } )

def command_dimmer( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        set_light_status( light, { 'brightness': get_light_status( light, 'brightness' )-5 } )

def command_warmer( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        set_light_status( light, { 'temperature': get_light_status( light, 'temperature' )+5 } )

def command_cooler( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        set_light_status( light, { 'temperature': get_light_status( light, 'temperature' )-5 } )

def command_set( args ):
    lights = get_lights( args['lights'] )

    for light in lights:
        set_light_status( light, args)

def command_list( args ):
    lights = get_lights( args['lights'] )

    for index, light in enumerate( lights ):
        print( f"[{index+1}] {light['name']} ({light['light']})" )

parser = argparse.ArgumentParser( description='Control Elgato Lights.' )
subparsers = parser.add_subparsers( title='commands', metavar='Use -h or --help with any command for command-specific help' )

parent_parser = argparse.ArgumentParser(add_help=False)
parent_parser.add_argument( '--light', dest='lights', action='append', metavar='LIGHT', help='Light to target as number (from %(prog)s list) or IP:PORT. Can include multiple times.' )

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

parser_set = subparsers.add_parser('set', help='Set status for lights, including on/off, brightness, and temperature')
parser_set.set_defaults( func=command_set )
on_off_group = parser_set.add_mutually_exclusive_group()
on_off_group.add_argument( '-o', dest='on', type=on_off_to_bool, help='Whether to set the light(s) on or off', metavar='ON|OFF')
on_off_group.add_argument('--on', action='store_true', dest='on')
on_off_group.add_argument('--off', action='store_false', dest='on')
parser_set.add_argument( '-b', '--brightness', type=brightness_value, help='Brightness for light - percentage from 3 to 100', metavar="3-100")
parser_set.add_argument( '-t', '--temperature', type=temperature_value, help='Temperature for light - Kelvin from 2900k - 7000k (increments of 50)', metavar="2900-7000k (increments of 50)")

parser.add_argument( '--version', action='version', version='%(prog)s 0.0.1' )

args = parser.parse_args()

if hasattr( args, 'func' ) and callable( args.func ):
    args.func( vars( args ) )
    sys.exit()

# If no function was found to process, show help
parser.print_help()
