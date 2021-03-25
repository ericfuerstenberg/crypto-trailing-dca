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
from stoploss import Stoploss

logger = get_logger(__file__)

class Sell():

	def __init__(self, market, stopsize, interval, split):

		logger.warning('Initializing bot...')

		# establish a connection with exchange
		self.coinbasepro = CoinbasePro(
			api_key=Config.get_value('api','api_key'),
			api_secret=Config.get_value('api','api_secret'),
			password=Config.get_value('api','password')
		)
		
		# set our variables
		self.market = market
		self.stopsize = stopsize
		self.interval = interval
		self.split = split

		self.tracked_price = self.coinbasepro.get_price(self.market)
		self.tracked_balance = self.coinbasepro.get_balance(self.market.split("/")[1])
		self.running = False

		if self.split == 1:
			logger.warning('Running in single coin mode: %s' % self.market)
		else:
			logger.warning('Running in multiple coin mode (%s)' % self.split)

        stoploss = Stoploss()
        hopper = Hopper()


	def __del__(self):
		message = ('Program has exited: %s.' % self.market)
		send_sns(message)
		logger.warning(message)

	def __exit__(self, exc_type, exc_value, traceback): 
		logger.info('Inside __exit__') 
		logger.warning('Program has exited.')


	def set_prices(self):
		try:
			self.price = self.coinbasepro.get_price(self.market)

			### TURN ONTO TEST PRICE MANUALLY
			#self.price = float(input('TEST PRICE: ')) #<-- this allows us to manually enter a TEST PRICE to validate script

			if self.price > self.tracked_price:
				logger.warn('New high observed: %.2f' % self.price)
				self.tracked_price = self.price			

			return True

		except Exception as e:
			logging.error(e)


	def execute_sell(self):
		# first, do a table lookup to find the most recent sold_at price
		self.cursor = self.con.cursor()
		last_threshold_sold_at = self.cursor.execute("SELECT * FROM thresholds WHERE threshold_hit = 'Y' and sold_at is not null;").fetchall()
		self.cursor.close()

		if last_threshold_sold_at:
			last_sold_at_price = last_threshold_sold_at[-1][4]

			killswitch = self.price < last_sold_at_price
			logger.info('Killswitch: ' + str(killswitch))

			#kill switch logic here (if current price is lower than most recent sold_at price, do not execute a sell!)
			if killswitch:
				logger.warn('DANGER: POSSIBLE FLASH CRASH!!!')
				logger.warn('Current market price %s is significantly below the last price we sold at: %s.' % (str(self.price), str(last_sold_at_price)))
				logger.warn('The bot will not execute a sell under these conditions. Resetting and waiting for next price data from the exchange.')
				# reset hopper
				self.cursor = self.con.cursor()
				self.cursor.execute("REPLACE INTO hopper (id, amount) VALUES (1, 0)")
				self.cursor.close()
				self.hopper = 0
				logger.warn("Reset Hopper: " + str(self.hopper))
				# reset stoploss
				self.stoploss = None
				self.cursor = self.con.cursor()
				self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
				self.cursor.close()
				self.stoploss_initialized = False
				logger.warn("Reset Stoploss: " + str(self.stoploss))
				# reset threshold - find rows where threshold = Y but there is no sold_at value
				self.cursor = self.con.cursor()
				self.cursor.execute("UPDATE thresholds SET threshold_hit = 'N' WHERE threshold_hit = 'Y' AND sold_at is null")
				self.cursor.close()
				self.con.commit()
 				# restart our loop. Don't execute sell. Instead, check prices again, etc. 
				self.run()

			else: 
				logger.info('THIS IS A SAFE SELL, NO KILLSWITCH TRIGGERED')


		# execute sell order, verify that sell posts and completes, then reset hopper, stoploss, and sold_at values
		try:
			logger.warn("Sell triggered | Current price: %.2f | Stop loss: %.2f" % (self.price, self.stoploss))
			logger.warn("Attempting to sell %s %s at %.2f for %.2f %s" % (self.hopper, self.market.split("/")[0], self.price, (self.price*self.hopper), self.market.split("/")[1]))
			error_message = 'Failed to execute sell order'

			sell_order = self.coinbasepro.sell(self.market, self.hopper)
			id = sell_order['info']['id']
			pending = True
			fetch_order = self.coinbasepro.get_order(id)
			size, price, status, done_reason = fetch_order['info']['size'], fetch_order['price'], fetch_order['info']['status'], fetch_order['info']['done_reason']

			while pending:
				if status == 'done' and done_reason == 'filled': 
					filled, sell_value, fee = fetch_order['amount'], fetch_order['cost'], fetch_order['fee']['cost']
					pending = False
					logger.warn("Sell order executed and filled successfully.")
					logger.warn("Sold %.6f %s for %.2f %s. Fees: %.2f" % (filled, self.market.split("/")[0], sell_value, self.market.split("/")[1], fee))
				elif status == 'done' and done_reason == 'cancelled':
					pending = False
					logger.warn('Sell order was canceled by exchange.')
					self.run() #if order was canceled, we want to exit this current function and restart our check_price loop to try again. 
				else:	
					time.sleep(2) #if status is anything other than 'closed' or 'done', we want to sleep the script and recheck

			# reset hopper after executing sell
			error_message = 'Failed to update exit_strategy.db after executing sell order'
			self.cursor = self.con.cursor()
			self.cursor.execute("REPLACE INTO hopper (id, amount) VALUES (1, 0)")
			self.hopper = 0
			logger.warn("Reset Hopper: " + str(self.hopper))

			# reset stoploss after executing sell
			self.stoploss = None
			self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
			self.stoploss_initialized = False
			logger.warn("Reset Stoploss: " + str(self.stoploss))

			# add sell price to sold_at column for all rows included in the current hopper
			self.cursor.execute("UPDATE thresholds SET sold_at = %.2f WHERE threshold_hit = 'Y' AND sold_at is null" % self.price)
			logger.info("Updated sold_at column(s)!")
			self.cursor.close()
			self.con.commit()

		except ccxt.AuthenticationError as e:
			logger.exception('Failed to execute sell order | AUTHENTICATION ERROR | %s' % str(e))
			raise
		except ccxt.InsufficientFunds as e:
			logger.exception('Failed to execute sell order  | INSUFFICIENT FUNDS | %s' % str(e))
			raise
		except ccxt.BadRequest as e:
			logger.exception('Failed to execute sell order  | BAD REQUEST | %s' % str(e))
			raise
		except ccxt.NetworkError as e:
			logger.exception('Failed to execute sell order  | NETWORK ERROR | %s' % e)
			#raise ### we should not raise the exception here, we should let the script continue, which will result in a loop of network errors until it succeeds.
		except Exception as e:
			logger.exception('%s | %s' % (error_message, e))
			raise

	def print_status(self):
		logger.info("---------------------")
		logger.info("Trail type: %s" % self.type)
		logger.info("Market: %s" % self.market)

		if self.type == "sell":
			logger.info("Available to sell: %.4f %s" % (self.hopper, self.market.split("/")[0]))
		else: 
			logger.info("Total USD balance: $%.2f" % self.balance)
			if self.balance > 50:
				logger.info("%s available to purchase %s: $%.2f" % (self.market.split("/")[1], self.market.split("/")[0], self.coin_hopper))

		if self.stoploss_initialized is True:
			logger.info("Stop loss: %.2f" % self.stoploss)
		else:
			logger.info('Stop loss: N/A')

		logger.info("Trailing stop: %.2f percent" % (self.stopsize*100))
		logger.info("Last price: %.2f" % self.price)
		logger.info("---------------------")


	def run(self):
		self.running = True
		while (self.running):
            if self.set_prices():
                self.print_status()
				if stoploss.increment(self.price):
					stoploss.update()
                if hopper.increment(self.price):
					hopper.update()
				
			time.sleep(self.interval)


