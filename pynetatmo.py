from datetime import datetime
from os import path
from pprint import pprint
from requests import post

import json
import yaml


class Weatherstation(object):

    def __init__(self, configyaml, debug=False):
        stream = open(configyaml, 'r')
        config = yaml.load(stream)
        self.configyaml = configyaml
        self.config = {}
        self.config['username'] = config['username']
        self.config['password'] = config['password']
        self.config['client_id'] = config['client_id']
        self.config['client_secret'] = config['client_secret']
        self.config['tokenstore'] = config['tokenstore']
        self.debug = debug
        self.__get_or_refresh_tokens()

    def __debug(self, message):
        if self.debug:
            now = datetime.utcnow().isoformat()
            print('[%s] %s' % (now, message))

    def __get_token(self):
        payload = {
            'grant_type': 'password',
            'client_id': self.config['client_id'],
            'client_secret': self.config['client_secret'],
            'username': self.config['username'],
            'password': self.config['password'],
            'scope': 'read_station'}
        r = post(
            'https://api.netatmo.net/oauth2/token',
            data=payload)
        return r.json()

    def __refresh_token(self):
        payload = {
            'grant_type': 'refresh_token',
            'client_id': self.config['client_id'],
            'client_secret': self.config['client_secret'],
            'refresh_token': self.config['refresh_token']
        }
        r = post(
            'https://api.netatmo.net/oauth2/token',
            data=payload)
        return r.json()

    def __get_or_refresh_tokens(self):
        haschanged = False
        store = {}
        tokenstore = self.config['tokenstore']

        if path.isfile(tokenstore):
            self.__debug('Reading stored tokens from \'%s\'.' % (tokenstore))
            stream = open(tokenstore, 'r')
            store = yaml.load(stream)

            self.config['access_token'] = store['access_token']
            self.config['refresh_token'] = store['refresh_token']
            self.config['expires_in'] = store['expires_in']

            lastupdate = datetime.strptime(
                store['tokens_last_updated'],
                "%Y-%m-%dT%H:%M:%S.%f")
            diffsecs = (datetime.utcnow() - lastupdate).total_seconds()
            self.__debug('Token is %i seconds old.' % (diffsecs))

            if diffsecs > store['expires_in']:
                self.__debug('Refreshing tokens.')
                refresh_token = store['refresh_token']
                newstore = self.__refresh_token()
                self.__debug('Old access token: %s.' % (store['access_token']))
                self.__debug(
                    'New access token: %s.' %
                    (newstore['access_token']))
                store['access_token'] = newstore['access_token']
                store['refresh_token'] = newstore['refresh_token']
                store['tokens_last_updated'] = datetime.utcnow().isoformat()
                haschanged = True

        else:
            self.__debug('Fetching new tokens.')
            tokens = self.__get_token()
            store['tokens_last_updated'] = datetime.utcnow().isoformat()
            store['access_token'] = tokens['access_token']
            store['refresh_token'] = tokens['refresh_token']
            store['expires_in'] = tokens['expires_in']
            haschanged = True

        self.config['access_token'] = store['access_token']
        self.config['refresh_token'] = store['refresh_token']
        self.config['expires_in'] = store['expires_in']

        if haschanged:
            self.__debug('Writing token store to \'%s\'.' % (tokenstore))
            with open(tokenstore, 'w') as yaml_file:
                yaml_file.write(yaml.dump(store, default_flow_style=False))

ws = Weatherstation(
    configyaml=r'c:\python\pynetatmo\settings.yaml',
    debug=True)
print(dir(ws))
#_get_or_refresh_token(ws)
