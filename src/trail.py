import ccxt
from coinbasepro import CoinbasePro
import config
import time
import datetime
import pandas as pd
import sqlite3 as sl
import logging
from crypto_bot_definitions import LOG_DIR
from helper import get_logger, Config

# PLEASE CONFIGURE API DETAILS IN config.py

# To Do:
# 1. DONE? - Instead of usin a static amount of funds, create a function to read from a dataframe, check against current price, and update a "holding pen/hopper" with more ETH as new thresholds are crossed (https://stackoverflow.com/questions/42285806/how-to-pop-rows-from-a-dataframe)
# 2. DONE - Modify the stop loss to use a % rather than a static amount. E.g., 5% stop loss.
# 3. DONE? - Modify the logging output to specify how much is currently in the hopper (e.g., ETH to trade: 0.5, 0.75, etc.)
# 4. DONE - Adjust script so it only initializes the stop loss once a threshold is first hit
# 5. Need to allow script to continue running after a sell, right now it simply exits
# 6. DONE - Persist the exit strategy table and make adjustments based on what thresholsd have been hit.
# 6b. 	DONE Should persist a Hit Threshold Y/N for each line/row - then look for the first threshold that hasn't been hit
# 7. DONE - Persist the hopper data in another table in the sqlite db. initialize_hopper() and update_hopper() should read from this table.
# 7a. 	DONE When hopper changes, insert the new value into the database.
# 7. Set up actual logging output to a logfile. Print timestamps for each message. Hopper updates, stop loss updates, etc should all be logged to the system for tracking purposes.
# 8. Error handling? e.g., ccxt.base.errors.InsufficientFunds: coinbasepro Insufficient funds. What id DB update fails and hopper doesn't reset?
# 9. Port over to aws instance, prepare to dockerize the script - or create a systemd service to ensure it's consistently running
# 10. Improve testability - comment out the check_price call and have script ask for a manual price entry to test against?
# 11. Guardrails around thresholds and selling below threshold price points we've already sold at??
# 12. Validate that orders go through & complete - order validation, etc. (don't want to empty hopper if sell failed)
# 13. DONE (did this in the script, no need for db table) - Create a "price" table to track the highs. For each market price check, compare against the table of known prices. Update the table when a new high price is seen and then return this new high price to the logger output (New high price observed: PRICE).



# Other Notes:
# 1. The script can only add one chunk of coins per interval when the price exceeds a threshold (or multiple). Debate whether we want it to add all of the available funds up to a specific price when multiple thresholds are crossed at once?
# 2. It seems prone to effects of short-term spikes. E.g., price spikes up 200-300 USD and then it drops back down immediately, but our stoploss is pulled up higher than we'd want. Could take like an average of the price over the last 3 seconds? Dunno. It doesn't need to be perfect though.
#3. DONE - Maybe we should initialize the first stoploss at the threshold price? Then we can start walking the threshold up once the potential new stoploss [(current price - (current price * stop percent))] is higher than our threshold? Otherwise stoploss = threshold price. That we we won't sell lower than the threshold. 
# 3a. Then also maybe we should update the stoploss to tbe the next threshold value if threshold is hit but we haven't moved up to the next stoploss value? Avoid situation where we increase hopper but our stoploss is still set at an earlier threshold value?

logger = get_logger(__file__)

class StopTrail():

	def __init__(self, market, type, stopsize, interval):

		logger.warning('Initializing bot...')

		self.coinbasepro = CoinbasePro(
			api_key=Config.get_value('api','api_key'),
			api_secret=Config.get_value('api','api_secret'),
			password=Config.get_value('api','password')
		)
		
		self.market = market
		self.type = type
		self.stopsize = stopsize
		self.interval = interval
		self.running = False
		self.tracked_price = self.coinbasepro.get_price(self.market)
		
		#Open db connection and check for a persisted stoploss value
		self.con = sl.connect("exit_strategy.db")
		self.cursor = self.con.cursor()
		self.cursor.execute("SELECT * FROM stoploss;")
		first_row = self.cursor.fetchone()
		self.cursor.close()
		stop_value = first_row[1]
		if stop_value != None:
			logger.warn('Stoploss already set at: %.4f' % stop_value)
			self.stoploss = float(first_row[1])
			self.stoploss_initialized = True
		else:
			logger.info('No stoploss currently set')
			self.stoploss_initialized = False

		self.hopper = self.initialize_hopper()
			
	def __del__(self):
		logger.info('Inside __del__') 
		logger.info('Deconstructing StopTrail() safely')
		logger.warning('Program has exited.')
		self.close_db()

	def __exit__(self, exc_type, exc_value, traceback): 
		logger.info('Inside __exit__') 
		logger.info('Execution type:', exc_type) 
		logger.info('Execution value:', exc_value) 
		logger.info('Traceback:', traceback) 
		logger.warning('Program has exited.')
		self.close_db()

		
	def close_db(self):
		if self.con:
			 self.con.commit()
			 self.con.close()
			 logger.info('Database closed')
			
	#def initialize_stop(self, threshold):
	def initialize_stop(self):
		# TO DO: decide if you want to init the stoploss at your threshold or below your first threshold

		self.stoploss_initialized = True
		price = self.coinbasepro.get_price(self.market)
		self.tracked_price = price
		
		#if the stoploss is set in the table, grab that value, if not, set the stoploss from the market price
		if self.type == "buy":
			self.stoploss = (price + (price * self.stopsize))
			#self.stoploss = threshold 
			self.cursor = self.con.cursor()
			self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
			logger.warn('Stop loss initialized at: ' + str(self.stoploss))
			self.cursor.close()
			self.con.commit()
			
			return self.stoploss, self.stoploss_initialized, self.tracked_price
		
		else: 
			self.stoploss = (price - (price * self.stopsize)) # this sets our first stoploss below our initial threshold value, will be less likely to get stopped out
			#self.stoploss = threshold #set out first stoploss at our initial threshold, to ensure we don't sell below this value
			self.cursor = self.con.cursor()
			self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
			logger.warn('Stop loss initialized at: ' + str(self.stoploss))
			self.cursor.close()
			self.con.commit()
		
			return self.stoploss, self.stoploss_initialized, self.tracked_price


	def update_stop(self):
		if self.stoploss_initialized is True:
			price = self.coinbasepro.get_price(self.market)
			
			if self.type == "sell":
				if price > self.tracked_price:
					logger.warn('New high observed: %.2f' % price)
					self.tracked_price = price
				# logger.info(price - (price * self.stopsize))
				# logger.info(self.stoploss)
				if (price - (price * self.stopsize)) > self.stoploss:
					self.stoploss = (price - (price * self.stopsize))
					self.cursor = self.con.cursor()
					self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
					self.cursor.close()
					self.con.commit()
					logger.warn("New high observed: %.2f | Updated stop loss to %.4f" % (price, self.stoploss))

				# trying to add logic to update stoploss to the new threshold if it's hit before our stoploss gap is closed
				# elif threshold > self.stoploss: 
				# 	self.stoploss = (price - (price * self.stopsize))
				# 	self.cursor = self.con.cursor()
				# 	self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
				# 	self.cursor.close()
				# 	self.con.commit()
				# 	logger.warn("Hit our new threshold at %.2f | Updated stop loss to %.4f" % (threshold, self.stoploss))

				elif price <= self.stoploss:
					self.execute_sell()

			elif self.type == "buy":
				if price < self.tracked_price:
					logger.warn('New low observed: %.2f' % price)
				if (price + self.stopsize) < self.stoploss:
					self.stoploss = price + self.stopsize
					self.cursor = self.con.cursor()
					self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
					self.cursor.close()
					self.con.commit()
					logger.warn("New low observed: Updating stop loss to %.8f" % self.stoploss)

				elif price >= self.stoploss:
					self.running = False
					balance = self.coinbasepro.get_balance(self.market.split("/")[1])
					price = self.coinbasepro.get_price(self.market)
					amount = (balance / price) * 0.999 # 0.10% maker/taker fee without BNB
					self.coinbasepro.buy(self.market, amount, price)
					logger.warn("Buy triggered | Price: %.8f | Stop loss: %.8f" % (price, self.stoploss))
		else:
			logger.info('No stoploss yet initialized. Waiting.')


	def execute_sell(self):
		price = self.coinbasepro.get_price(self.market)
		try:
			logger.warn("Sell triggered | Current price: %.2f | Stop loss: %.8f" % (price, self.stoploss))
			self.coinbasepro.sell(self.market, self.hopper)
			logger.warn("Sold %.8f %s at %.8f for %.8f %s" % (self.hopper, self.market.split("/")[0], price, (price*self.hopper), self.market.split("/")[1]))
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
			raise #consider retrying for a network error? Resetting the stop loss? Think about how to protect ourselves from the exchange going down temporarily.	
		except Exception as e:
			logger.exception('Failed to execute sell order | %s' % e)
			raise

		try:	
			self.cursor = self.con.cursor()
			# reset hopper after executing sell
			self.cursor.execute("REPLACE INTO hopper (id, amount) VALUES (1, 0)")
			self.hopper = 0
			# reset stoploss after executing sell
			self.stoploss = None
			self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
			self.stoploss_initialized = False
			self.cursor.close()
			self.con.commit()
			logger.warn("Reset Hopper: " + str(self.hopper))
			logger.warn("Reset Stoploss: " + str(self.stoploss))
		except Exception as e:
			logger.exception('Failed to update exit_strategy.db after executing sell order | %s' % e)
			raise
	

	def initialize_hopper(self):
		self.cursor = self.con.cursor()
		self.cursor.execute("SELECT * FROM HOPPER;")
		first_row = self.cursor.fetchone()
		self.cursor.close()
		hopper_amount = first_row[1]
		if hopper_amount > 0:
			logger.warn('Hopper already set at: %.4f' % hopper_amount)
		else:
			logger.info('No hopper previously set. Starting at 0.')
		self.hopper = hopper_amount
		return self.hopper


	def update_hopper(self):
		price = self.coinbasepro.get_price(self.market)
		self.cursor = self.con.cursor()
		self.cursor.execute("SELECT Count(*) from thresholds WHERE threshold_hit = 'N';")
		result = self.cursor.fetchone()
		self.cursor.close()
		remaining_rows = result[0]
		logger.info('Thresholds remaining: ' + str(remaining_rows))

		if remaining_rows > 0:
			self.cursor = self.con.cursor()
			self.cursor.execute("SELECT * FROM thresholds WHERE threshold_hit = 'N';")
			first_row = self.cursor.fetchone()
			self.cursor.close()
			threshold = first_row[1]
			exit_amount = first_row[2]
			
			if price >= threshold:
				try:
					# update our threshold table to indicate that a new threshold has been hit
					row_id = str(first_row[0])
					self.cursor = self.con.cursor()
					self.cursor.execute("UPDATE thresholds SET threshold_hit = 'Y' WHERE id = ?", (row_id))
					self.cursor.close()
					self.con.commit()
				except Exception as e:
					logger.exception('Failed to update exit_strategy.db threshold table | %s' % e)
					
				try:	
					# initialize a stoploss, if one is not already initialized
					if self.stoploss_initialized == False:
						#self.initialize_stop(threshold)
						self.initialize_stop()
				except Exception as e:
					logger.exception('Failed to initialize_stop() | %s' % e)

				try:	
					# write the new hopper value to the hopper table
					logger.warn('Hit our threshold at ' + str(threshold) + '. Adding ' + str(exit_amount) + ' to hopper.')
					self.hopper += exit_amount
					self.cursor = self.con.cursor()
					self.cursor.execute("REPLACE INTO hopper (id, amount) VALUES (?, ?)", (1, self.hopper))
					logger.warn('New hopper total: %.4f' % self.hopper)
					# check to see if we have any remaining thesholds, if so, output the next threshold value
					self.cursor.execute("SELECT Count(*) from thresholds WHERE threshold_hit = 'N';")
					result = self.cursor.fetchone()
					remaining_rows = result[0]
					if remaining_rows > 0:
						self.cursor.execute("SELECT * FROM thresholds WHERE threshold_hit = 'N';")
						first_row = self.cursor.fetchone()
						self.cursor.close()
						next_threshold = first_row[1]
						self.cursor.close()
						self.con.commit()
						logger.warn('Next threshold at: %.2f' % next_threshold)
					else:
						logger.warn('Final threshold hit.')
						self.cursor.close()

				except Exception as e:
					logger.exception('Failed to update hopper | %s' % e)
					raise #think about what we want to do when we can't update the hopper.. should we exit the script? 
				
			else:
				logger.info('Price has not yet met the next threshold of ' + str(threshold))

		else:
			logger.info('No more values to add to hopper.')
			threshold = None

		return self.hopper, threshold

	def print_status(self):
		price = self.coinbasepro.get_price(self.market)
		logger.info("---------------------")
		logger.info("Trail type: %s" % self.type)
		logger.info("Market: %s" % self.market)
		logger.info("Available to sell: %.4f" % self.hopper)
		if self.stoploss_initialized is True:
			logger.info("Stop loss: %s" % self.stoploss)
		else:
			logger.info('Stop loss: N/A')
		logger.info("Trailing stop: %s percent" % (self.stopsize*100))
		logger.info("Last price: %.2f" % price)
		logger.info("---------------------")

	def run(self):
		self.running = True
		while (self.running):
			self.print_status()
			self.update_stop()
			self.update_hopper()
			time.sleep(self.interval)