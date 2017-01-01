''' A Python module to talk to Netatmo's weather station API. '''

import datetime as dt
import logging
import os
import pprint
import requests
import sys
import yaml

logger = logging.getLogger(__name__)


class WeatherstationModule(object):

    def __init__(
            self,
            module_id,
            module_type,
            module_name,
            parent_id='',
            administrative={},
            dashboard_data={},
            station_name='',
            is_parent=False,
            is_child=False,
            has_co2=False,
            has_humidity=False,
            has_noise=False,
            has_pressure=False,
            has_temperature=False,
            has_rain=False,
            has_wind=False):
        self.module_id = module_id
        self.module_type = module_type
        self.module_name = module_name
        self.is_parent = is_parent
        self.station_name = station_name
        self.has_co2 = has_co2
        self.has_humidity = has_humidity
        self.has_noise = has_noise
        self.has_pressure = has_pressure
        self.has_temperature = has_temperature
        self.has_rain = has_rain
        self.has_wind = has_wind
        self.administrative = administrative
        self.dashboard_data = dashboard_data


class Weatherstation(object):

    ''' The weatherstation class. '''

    def __init__(self, configyaml, loglevel=None):
        ''' Initialise the object and set up the authentication tokens. '''
        numeric_level = getattr(logging, loglevel.upper(), None)
        logging.basicConfig(
            format='[%(asctime)s][%(levelname)s] %(message)s',
            level=numeric_level)
        with open(configyaml, "r") as stream:
            self.config = config = yaml.load(stream)
        self.response_cache = ''
        self._get_or_refresh_tokens()
        self.hierarchy = {}

    def _get_token(self):
        ''' Fetch a completely new token. '''
        payload = {
            'grant_type': 'password',
            'client_id': self.config['client_id'],
            'client_secret': self.config['client_secret'],
            'username': self.config['username'],
            'password': self.config['password'],
            'scope': 'read_station'}
        response = requests.post(
            'https://api.netatmo.net/oauth2/token',
            data=payload)
        if response.status_code != requests.codes.ok:
            logger.critical(
                'Could not fetch new token: %s',
                response.status_code)
            sys.exit()
        return response.json()

    def _refresh_token(self):
        ''' Current token is too old, refresh it. '''
        payload = {
            'grant_type': 'refresh_token',
            'client_id': self.config['client_id'],
            'client_secret': self.config['client_secret'],
            'refresh_token': self.config['refresh_token']
        }
        response = requests.post(
            'https://api.netatmo.net/oauth2/token',
            data=payload)
        return response.json()

    def _get_or_refresh_tokens(self):
        ''' Make sure the token store is populated with a fresh access token.'''
        haschanged = False
        store = {}
        tokenstore = self.config.get('tokenstore', 'tokenstore.yaml')

        if os.path.isfile(tokenstore):
            logger.debug('Reading stored tokens from \'%s\'.', tokenstore)
            stream = open(tokenstore, 'r')
            store = yaml.load(stream)

            self.config['access_token'] = store['access_token']
            self.config['refresh_token'] = store['refresh_token']
            self.config['expires_in'] = store['expires_in']

            lastupdate = dt.datetime.strptime(
                store['tokens_last_updated'],
                "%Y-%m-%dT%H:%M:%S.%f")
            diffsecs = (dt.datetime.utcnow() - lastupdate).total_seconds()
            logger.debug('Token is %i seconds old.', diffsecs)

            if diffsecs > store['expires_in']:
                logger.debug('Refreshing tokens.')
                newstore = self._refresh_token()
                logger.debug('Old access token: %s.', store['access_token'])
                logger.debug('New access token: %s.', newstore['access_token'])
                store['access_token'] = newstore['access_token']
                store['refresh_token'] = newstore['refresh_token']
                store['tokens_last_updated'] = dt.datetime.utcnow().isoformat()
                haschanged = True

        else:
            logger.debug('Fetching new tokens.')
            tokens = self._get_token()
            store['tokens_last_updated'] = dt.datetime.utcnow().isoformat()
            store['access_token'] = tokens['access_token']
            store['refresh_token'] = tokens['refresh_token']
            store['expires_in'] = tokens['expires_in']
            haschanged = True

        self.config['access_token'] = store['access_token']
        self.config['refresh_token'] = store['refresh_token']
        self.config['expires_in'] = store['expires_in']

        if haschanged:
            logger.debug('Writing token store to \'%s\'.', tokenstore)
            with open(tokenstore, 'w') as yaml_file:
                yaml_file.write(yaml.dump(store, default_flow_style=False))

    def _get_station_data(self):
        ''' Fetch the station data bundle from the API. '''
        payload = {
            'access_token': self.config['access_token']
        }
        if self.response_cache == '':
            response = requests.post(
                'https://api.netatmo.net/api/getstationsdata',
                data=payload)
            self.response_cache = response.json()
        else:
            logger.debug('Using cached response.')

        return self.response_cache

    def _has_data_type(self, types_available, wanted):
        if wanted in types_available:
            return True
        return False

    def list_stations(self):
        stationlist = {}
        stationdata = self._get_station_data()
        for station in stationdata['body']['devices']:
            station_id = station['_id']
            module_name = station['module_name']
            stationlist[station_id] = module_name

        return stationlist

    def list_modules(self, stationid=''):
        modulelist = {}
        stationdata = self._get_station_data()
        self.modules = {}
        for station in stationdata['body']['devices']:
            child_modules = []
            data_type = station['data_type']
            station_id = station['_id'],
            self.modules[station_id] = WeatherstationModule(
                is_parent=True,
                station_name=station['station_name'],
                module_id=station['_id'],
                module_name=station['module_name'],
                module_type=station['type'],
                administrative=stationdata['body']['user']['administrative'],
                dashboard_data=station['dashboard_data'],
                has_co2=self._has_data_type(data_type, 'CO2'),
                has_humidity=self._has_data_type(data_type, 'Humidity'),
                has_noise=self._has_data_type(data_type, 'Noise'),
                has_pressure=self._has_data_type(data_type, 'Pressure'),
                has_rain=self._has_data_type(data_type, 'Rain'),
                has_temperature=self._has_data_type(data_type, 'Temperature'),
                has_wind=self._has_data_type(data_type, 'Wind'),
            )
            for submodule in station['modules']:
                data_type = submodule['data_type']
                submodule_id = submodule['_id'],
                child_modules.append(submodule_id)
                self.modules[submodule_id] = WeatherstationModule(
                    is_child=True, module_id=submodule_id,
                    module_type=submodule['type'],
                    module_name=submodule['module_name'],
                    parent_id=station_id,
                    administrative=stationdata['body']['user']
                    ['administrative'],
                    dashboard_data=submodule['dashboard_data'],
                    has_co2=self._has_data_type(data_type, 'CO2'),
                    has_humidity=self._has_data_type(data_type, 'Humidity'),
                    has_noise=self._has_data_type(data_type, 'Noise'),
                    has_pressure=self._has_data_type(data_type, 'Pressure'),
                    has_rain=self._has_data_type(data_type, 'Rain'),
                    has_temperature=self._has_data_type(
                        data_type, 'Temperature'),
                    has_wind=self._has_data_type(data_type, 'Wind'),)

            self.hierarchy[station_id] = child_modules

        for module_id in self.modules:
            thismodule = self.modules[module_id]

            if thismodule.has_co2:
                co2 = -1
                if 'CO2' in thismodule.dashboard_data.keys():
                    co2 = thismodule.dashboard_data['CO2']
                thismodule.co2 = co2
                thismodule.co2_pretty = '%dppm' % co2

            if thismodule.has_humidity:
                humudity = -1
                if 'Humidity' in thismodule.dashboard_data.keys():
                    humidity = thismodule.dashboard_data['Humidity']
                thismodule.humidity = humidity
                thismodule.humidity_pretty = '%d%%' % humidity

            if thismodule.has_pressure:
                pressureunit = thismodule.administrative['pressureunit']
                pressure = thismodule.dashboard_data['Pressure']
                if pressureunit == 0:
                    thismodule.pressure = '{:.1f}'.format(pressure)
                    thismodule.pressure_pretty = '{:.1f}mbar'.format(pressure)
                if pressureunit == 1:
                    pressure = pressure * 0.0295301
                    thismodule.pressure = '{:.1f}'.format(pressure)
                    thismodule.pressure_pretty = '{:.1f}inHg'.format(pressure)
                if pressureunit == 2:
                    pressure = pressure * 0.75006375541921
                    thismodule.pressure = '{:.1f}'.format(pressure)
                    thismodule.pressure_pretty = '{:.1f}mmHg'.format(pressure)

            if thismodule.has_temperature:
                unit = thismodule.administrative['unit']
                temperature = thismodule.dashboard_data['Temperature']
                if unit == 0:
                    thismodule.temperature = temperature
                    thismodule.temperature_pretty = '{:.1f}\u2103'.format(
                        temperature)
                if unit == 1:
                    temperature = temperature * 1.8 + 32
                    thismodule.temperature = temperature
                    thismodule.temperature_pretty = '{:.1f}\u2109'.format(
                        temperature)


ws = Weatherstation(
    configyaml=r'c:\python\pynetatmo\settings.yaml',
    loglevel='debug')
ws.list_modules('')

# for station in ws.hierarchy:
#    print('- %s' % (ws.modules[station].station_name))
#    print('-- %s' % (ws.modules[station].module_name))
#    for submodule in ws.hierarchy[station]:
#        print('--- %s' % (ws.modules[submodule].module_name))


#_get_or_refresh_token(ws)
