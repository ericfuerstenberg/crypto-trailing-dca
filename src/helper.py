from configparser import ConfigParser
import smtplib
import logging
import boto3
import math
from logging import config
from definitions import CONF_DIR

__LOGGER_CONF_FILE = CONF_DIR + "/logger.ini"
__SETTINGS_CONF_FILE = CONF_DIR + "/settings.ini"

class Config(ConfigParser):

    """
    'Config' class inherits (a sub-class of) 'ConfigParser' python module. It initializes default settings which will be
    used by other modules. This is done with an intention to avoid writing duplicate code.
    """

    __CONF_FILE = CONF_DIR + "/settings.ini"

    def __init__(self):
        ConfigParser.__init__(self)
        self.read(Config.__CONF_FILE)

    @classmethod
    def get_value(cls, section, key):
        """
        Return the value of key in a section defined in settings.ini.

        :param section: 'str' valid section in settings.ini.
        :param key: 'str' valid key for the section.
        :return: 'str' value of the key passed as an argument.
        """
        return cls.get(Config(), section, key)


def get_logger(file_name):
    """
    Creates a logger object which can utilized by all modules.
    IMP Setting: disable_existing_loggers=False
    :param file_name:
    :return:
    """
    logging.config.fileConfig(__LOGGER_CONF_FILE, disable_existing_loggers=False)
    name = file_name.split("/")[-1].split(".")[0]
    logger = logging.getLogger(name)
    return logger


def send_sns(message):
    sns = boto3.client(
        "sns",
        aws_access_key_id = Config.get_value('aws','aws_access_key_id'),
        aws_secret_access_key = Config.get_value('aws','aws_secret_access_key'),
        region_name = Config.get_value('aws','region_name')
    )

    sns.publish(
        PhoneNumber = Config.get_value('sns','phone_number'),
        Message = message
    )


def round_decimals_down(number:float, decimals:int=2):
    """
    Returns a value rounded down to a specific number of decimal places.
    """
    if not isinstance(decimals, int):
        raise TypeError("decimal places must be an integer")
    elif decimals < 0:
        raise ValueError("decimal places has to be 0 or more")
    elif decimals == 0:
        return math.floor(number)

    factor = 10 ** decimals
    return math.floor(number * factor) / factor

