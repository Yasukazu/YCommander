#  _  __  
# | |/ /___ ___ _ __  ___ _ _ ®
# | ' </ -_) -_) '_ \/ -_) '_|
# |_|\_\___\___| .__/\___|_|
#              |_|            
#
# Keeper Commander 
# Contact: ops@keepersecurity.com
#

from urllib.parse import urlparse, urlunparse
import logging
import json
from pprint import pformat
from json import JSONDecodeError
from base64 import urlsafe_b64decode
from typing import Dict, Optional
from .error import OSException, RecordError, DecodeError
from . import CONFIG_FILENAME  # in __init__.py
# from .config import config_filename

LAST_RECORD_UID = 'last_record_uid'
LAST_SHARED_FOLDER_UID = 'last_shared_folder_uid'
LAST_FOLDER_UID = 'last_folder_uid'
LAST_TEAM_UID = 'last_team_uid'

logger = logging.getLogger(__file__)

KEEPER_SERVER_URL = 'https://keepersecurity.com/api/v2/'
DEFAULT_LOCALE = 'en_US'

class RestApiContext:
    def __init__(self, server=KEEPER_SERVER_URL, locale=DEFAULT_LOCALE, device_id=None):
        self.server_base = server
        self.transmission_key = None
        self.__server_key_id = 1
        self.locale = locale
        self.__device_id = device_id
        self.__store_server_key = False

    def __get_server_base(self):
        return self.__server_base

    def __set_server_base(self, value):
        p = urlparse(value)
        self.__server_base = urlunparse((p.scheme, p.netloc, '/api/rest/', None, None, None))

    def __get_server_key_id(self):
        return self.__server_key_id

    def __set_server_key_id(self, key_id):
        self.__server_key_id = key_id
        self.__store_server_key = True

    def __get_device_id(self):
        return self.__device_id

    def __set_device_id(self, device_id):
        self.__device_id = device_id
        self.__store_server_key = True

    def __get_store_server_key(self):
        return self.__store_server_key

    server_base = property(__get_server_base, __set_server_base)
    device_id = property(__get_device_id, __set_device_id)
    server_key_id = property(__get_server_key_id, __set_server_key_id)
    store_server_key = property(__get_store_server_key)


class NoDupDict(dict):
    def add(self, k, v):
        if k in self:
            raise ValueError(f"{k} is duplicating!")
        self[k] = v

CONFIG_KEY_SET = {'user', 'server', 'password', 'timedelay', 'mfa_token', 'mfa_type',
            'commands', 'plugins', 'debug', 'batch_mode', 'device_id'}


class KeeperParams:
    """ Global storage of data during the session """

    def __init__(self,  config_filename: str=CONFIG_FILENAME, config: Optional[Dict[str, str]]=None,
                 server: str=KEEPER_SERVER_URL, device_id: Optional[str] = None):
        '''

        @param config_filename: JSON format file of default CONFIG_FILENAME name
        @param config: Dict keys: 'user', 'password', 'locale'
        @param server:
        @param device_id:
        '''
        self.config_filename = config_filename
        self.config = config or {}
        self.auth_verifier = None
        self.__server = server
        self.user = self.config.get('user')
        self.password = self.config.get('password')
        self.mfa_token = ''
        self.mfa_type = 'device_token'
        self.commands = []
        self.plugins = []
        self.session_token = None
        self.salt = None
        self.iterations = 0
        self.data_key = None
        self.rsa_key = None
        self.revision = 0
        self.record_cache = {}
        self.meta_data_cache = {}
        self.shared_folder_cache = {}
        self.team_cache = {}
        self.subfolder_cache = {}
        self.subfolder_record_cache = {}
        self.non_shared_data_cache = {}
        self.root_folder = None
        self.current_folder = None
        self.folder_cache = {}
        self.debug = False
        self.timedelay = 0
        self.sync_data = False  # initially not True : 2019-12-15
        self.license = None
        self.settings = None
        self.enforcements = None
        self.enterprise = None
        self.prepare_commands = False
        self.batch_mode = False
        try:
            o_locale = self.config['locale']
            logger.info(f"Locale for RestApiContext is set to {o_locale} from config.")
        except KeyError:
            o_locale = 'en_US'
            logger.info(f"Locale for RestApiContext is set to 'en_US' as default.")
        self.__rest_context = RestApiContext(server=server, device_id=device_id, locale=o_locale)
        self.pending_share_requests = set()
        self.environment_variables = {}
        self.record_history = {}        # type: dict[str, (list[dict], int)]
        self.event_queue = []
        self.last_record_table = None  #last list command result

    def clear_session(self):
        self.auth_verifier = ''
        self.user = ''
        self.password = ''
        self.mfa_type = 'device_token'
        self.mfa_token = ''
        self.commands.clear()
        self.session_token = None
        self.salt = None
        self.iterations = 0
        self.data_key = None
        self.rsa_key = None
        self.revision = 0
        self.record_cache.clear()
        self.meta_data_cache.clear()
        self.shared_folder_cache.clear()
        self.team_cache.clear()
        self.subfolder_cache .clear()
        self.subfolder_record_cache.clear()
        self.non_shared_data_cache.clear()
        if self.folder_cache:
            self.folder_cache.clear()

        self.root_folder = None
        self.current_folder = None
        self.sync_data = True
        self.license = None
        self.settings = None
        self.enforcements = None
        self.enterprise = None
        self.prepare_commands = True
        self.batch_mode = False
        self.pending_share_requests.clear()
        self.environment_variables.clear()
        self.record_history.clear()
        self.event_queue.clear()
        self.last_record_table = None

    def __get_rest_context(self):
        return self.__rest_context

    def __get_server(self):
        return self.__server

    def __set_server(self, value):
        self.__server = value
        self.__rest_context.server_base = value

    def queue_audit_event(self, name, **kwargs):
        # type: (str, dict) -> None
        if self.license and 'account_type' in self.license:
            if self.license['account_type'] == 2:
                self.event_queue.append({
                    'audit_event_type': name,
                    'inputs': {x:[kwargs[x]] for x in kwargs if x in {'record_uid', 'file_format', 'attachment_id', 'to_username'}}
                })

    server = property(__get_server, __set_server)
    rest_context = property(__get_rest_context)

    def __get_locale(self):
        return self.__get_rest_context().locale
    locale = property(__get_locale)


    def get_modified_timestamp(self, record_uid: str) -> float:
      """get modified timestamp from cache in params
      might cause AttributeError or KeyError"""
      try:
        current_rec = self.record_cache[record_uid]
        ts = current_rec['client_modified_time']
      except KeyError as k:
          raise RecordError(f"No {k} key exists!") from KeyError
      except AttributeError as a:
          raise RecordError(f"No {a} attribute exists!") from AttributeError
      if not ts:
          raise RecordError(f"Client modified timestamp is null!")
      return ts

    def set_params_from_config_file(self, config_filename: str = CONFIG_FILENAME, replace_self=False):
        '''set params from config file
            if no config_filename:str is given, then use 'config.json'
            Raises InpurError or OSException if any error occurs.
        '''
        # key_set = {'user', 'server', 'password', 'timedelay', 'mfa_token', 'mfa_type',
        #     'commands', 'plugins', 'debug', 'batch_mode', 'device_id'}
        config: Optional[Dict[str, str]] = None
        try:  # pick up keys from self.config[key] to self.key
            with open(config_filename) as config_file:
                config = json.load(config_file)
                json_set = config.keys()
                for key in CONFIG_KEY_SET:
                    if key in json_set:
                        if key == 'debug':
                            logging.getLogger().setLevel(logging.DEBUG)
                            logger.info(f"Global logging level is set as DEBUG.")
                        elif key == 'commands':
                            self.commands.extend(config[key])
                            logger.info(f"Command list is added: {pformat(config[key])}.")
                        elif key == 'device_id':
                            self.rest_context.device_id = urlsafe_b64decode(config['device_id'] + '==')
                            logger.info(f"Device ID is set.")
                        else:
                            setattr(self, key, config[key])  # lower()                 
                            logger.info(f"Key:{key} = Config:{config[key]} is set.")
                for key in json_set:
                    if key not in CONFIG_KEY_SET:
                        logger.info(f"{key} in {config_filename} is ignored.")
        except JSONDecodeError as err:  # msg, doc, pos:
            emsg = f"Error: Unable to parse: {err.doc} ; at {err.pos} ; in JSON file: {config_filename}"
            logger.error(f"msg:{err.msg}, doc:{err.doc}, pos:{err.pos}. {emsg}")
            raise DecodeError(emsg) from JSONDecodeError
        except FileNotFoundError as e:
            msg = f"{e.strerror}: Error: Unable to access config file: {config_filename}"
            logger.info(msg)
            # raise OSException(msg) from OSError
        if not config:
            return
        if replace_self:
            self.config_filename = config_filename
            self.config = config
        return config

    def set_params_from_config_dict(self, config: Dict[str, str]):
        '''

        @param config:
        @return:
        '''
        key_set = {'user', 'server', 'password', 'timedelay', 'mfa_token', 'mfa_type',
                   'commands', 'plugins', 'debug', 'batch_mode', 'device_id'}
        for key in key_set:
            # if key in config:
                if key == 'debug' and config.get(key):
                    self.debug = config[key]
                    logging.getLogger().setLevel(logging.DEBUG)
                    logging.info("Global logging level is set as DEBUG.")
                elif key == 'commands' and config.get(key):
                    self.commands.extend(config[key])
                    logger.info(f"Command list is added: {pformat(config[key])}.")
                elif key == 'device_id' and config.get(key):
                    self.rest_context.device_id = urlsafe_b64decode(config['device_id'] + '==')
                    logger.info(f"Device ID is set.")
                else:
                    if config.get(key):
                        setattr(self, key, config[key])
                        logger.info(f"Key:{key} = Config:{config[key]} is set.")
        for key in config:
            if key not in key_set:
                logger.info(f"{key} in config dict. is ignored.")