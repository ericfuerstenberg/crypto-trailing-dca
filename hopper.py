import ccxt
import config
import datetime
import logging
import time
import pandas as pd
import sqlite3 as sl
from coinbasepro import CoinbasePro
from crypto_bot_definitions import LOG_DIR
from helper import get_logger, send_sns, Config
from database import Database

logger = get_logger(__file__)

class Hopper():

    stoploss_initialized = False

    def __init__():
        database = Database()

        hopper_amount = get_amount()

        if hopper_amount > 0:
            logger.warn('Hopper already set at: %.4f' % hopper_amount)
        else:
            logger.info('No hopper previously set. Starting at 0.')
            

    def get_amount():
        hopper_amount = database.get_hopper_amount()
        return hopper_amount

	def reset():
		#dump hopper values from db


	def __del__(self):
		message = ('Program has exited: %s.' % self.market)
		send_sns(message)
		logger.warning(message)
		database.terminate()

	def __exit__(self, exc_type, exc_value, traceback): 
		logger.info('Inside __exit__') 
		logger.warning('Program has exited.')
		database.terminate()
