import datetime as dt
import json
import logging
import os
import pprint
import requests
import yaml

logger = logging.getLogger(__name__)


class Weatherstation(object):

    def __init__(self, configyaml, loglevel=None):
        numeric_level = getattr(logging, loglevel.upper(), None)
        logging.basicConfig(
            format='[%(asctime)s][%(levelname)s] %(message)s',
            level=numeric_level)
        with open(configyaml, "r") as stream:
            self.config = config = yaml.load(stream)
        self._get_or_refresh_tokens()

    def _get_token(self):
        payload = {
            'grant_type': 'password',
            'client_id': self.config['client_id'],
            'client_secret': self.config['client_secret'],
            'username': self.config['username'],
            'password': self.config['password'],
            'scope': 'read_station'}
        r = requests.post(
            'https://api.netatmo.net/oauth2/token',
            data=payload)
        return r.json()

    def _refresh_token(self):
        payload = {
            'grant_type': 'refresh_token',
            'client_id': self.config['client_id'],
            'client_secret': self.config['client_secret'],
            'refresh_token': self.config['refresh_token']
        }
        r = requests.post(
            'https://api.netatmo.net/oauth2/token',
            data=payload)
        return r.json()

    def _get_or_refresh_tokens(self):
        haschanged = False
        store = {}
        tokenstore = self.config['tokenstore']

        if os.path.isfile(tokenstore):
            logger.debug('Reading stored tokens from \'%s\'.' % (tokenstore))
            stream = open(tokenstore, 'r')
            store = yaml.load(stream)

            self.config['access_token'] = store['access_token']
            self.config['refresh_token'] = store['refresh_token']
            self.config['expires_in'] = store['expires_in']

            lastupdate = dt.datetime.strptime(
                store['tokens_last_updated'],
                "%Y-%m-%dT%H:%M:%S.%f")
            diffsecs = (dt.datetime.utcnow() - lastupdate).total_seconds()
            logger.debug('Token is %i seconds old.' % (diffsecs))

            if diffsecs > store['expires_in']:
                logger.debug('Refreshing tokens.')
                refresh_token = store['refresh_token']
                newstore = self._refresh_token()
                logger.debug('Old access token: %s.' % (store['access_token']))
                logger.debug(
                    'New access token: %s.' %
                    (newstore['access_token']))
                store['access_token'] = newstore['access_token']
                store['refresh_token'] = newstore['refresh_token']
                store['tokens_last_updated'] = dt.datetime.utcnow().isoformat()
                haschanged = True

        else:
            self.__debug('Fetching new tokens.')
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
            logger.debug('Writing token store to \'%s\'.' % (tokenstore))
            with open(tokenstore, 'w') as yaml_file:
                yaml_file.write(yaml.dump(store, default_flow_style=False))

ws = Weatherstation(
    configyaml=r'c:\python\pynetatmo\settings.yaml',
    loglevel='debug')
print(dir(ws))
#_get_or_refresh_token(ws)
