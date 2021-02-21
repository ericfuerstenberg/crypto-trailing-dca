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

class Stoploss():

    stoploss_initialized = False

    def __init__():

        database = Database()
        stop_value = database.get_stoploss()

		self.tracked_price = self.coinbasepro.get_price(self.market)

		if stop_value != None:
			logger.warn('Stoploss already set at: %.2f' % stop_value)
			self.stoploss = float(first_row[1])
			self.stoploss_initialized = True
            
		else:
			logger.info('No stoploss currently set')
			self.stoploss_initialized = False


    def is_initialized():
        #


	def increment(self, price, tracked_price):
		if self.stoploss_initialized is True:
			
			if self.type == "sell":
				if price > self.tracked_price:
					return True

				else: 
					return False

			# elif self.type == "buy":
			# 	if self.price < self.tracked_price:
			# 		return True

			# 	else: 
			# 		return False


	def update():
		logger.warn('New high observed: %.2f' % self.price)
		self.tracked_price = self.price

		if (self.price - (self.price * self.stopsize)) > self.stoploss:
			self.stoploss = (self.price - (self.price * self.stopsize))
			self.cursor = self.con.cursor()
			self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
			self.cursor.close()
			self.con.commit()
			logger.warn("Raised stop loss to %.2f" % (self.stoploss))

			return stoploss, tracked_price


	def reset():
		#dump stoploss values from db

	def __del__(self):
		message = ('Program has exited: %s.' % self.market)
		send_sns(message)
		logger.warning(message)
		database.terminate()

	def __exit__(self, exc_type, exc_value, traceback): 
		logger.info('Inside __exit__') 
		logger.warning('Program has exited.')
		database.terminate()
