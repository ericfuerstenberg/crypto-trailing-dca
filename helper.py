from configparser import ConfigParser
import smtplib
import logging
from logging import config
from crypto_bot_definitions import CONF_DIR

__LOGGER_CONF_FILE = CONF_DIR + "/logger.ini"

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


# class Config(ConfigParser):

#     """
#     'Config' class inherits (a sub-class of) 'ConfigParser' python module. It initializes default settings which will be
#     used by other modules. This is done with an intention to avoid writing duplicate code.
#     """

#     __CONF_FILE = CONF_DIR + "/settings.ini"

#     def __init__(self):
#         ConfigParser.__init__(self)
#         self.read(Config.__CONF_FILE)

#     @classmethod
#     def get_value(cls, section, key):
#         """
#         Return the value of key in a section defined in settings.ini.

#         :param section: 'str' valid section in settings.ini.
#         :param key: 'str' valid key for the section.
#         :return: 'str' value of the key passed as an argument.
#         """
#         return cls.get(Config(), section, key)

