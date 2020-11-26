import ccxt
import config
import datetime
import logging
import time
import pandas as pd
import sqlite3 as sl
from coinbasepro import CoinbasePro
from crypto_bot_definitions import LOG_DIR
from helper import get_logger, Config

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
# 7. DONE - Set up actual logging output to a logfile. Print timestamps for each message. Hopper updates, stop loss updates, etc should all be logged to the system for tracking purposes.
# 8. IN PROGRESS - Error handling? e.g., ccxt.base.errors.InsufficientFunds: coinbasepro Insufficient funds. What if DB update fails and hopper doesn't reset?
# 9. IN PROGRESS - Port over to aws instance, prepare to dockerize the script - or create a systemd service to ensure it's consistently running
# 9a. 	DONE - Secure ec2 instance - https://aws.amazon.com/premiumsupport/knowledge-center/ec2-ssh-best-practices/
# 10. DONE - Improve testability - comment out the check_price call and have script ask for a manual price entry to test against?

# 11. Validate that orders go through & complete - order validation, etc. (don't want to empty hopper if sell failed)
# 12. Create helper function to publish messages to an SNS topic when critical events happen (e.g., hopper/stoploss updates, sells execute, errors occur, etc) - then you can recieve email alerts
# 13. DONE - Build logic so that it won't execute a sell if the current price is lower than a previous stoploss that we've sold - KILL SWITCH!
# 13a. 	PASS ON THIS - Do we want a killswitch on our first threshold? This is not currently implemented. 
# 14. Neuter the script (comment out the execute_sell() function) and then test it in production. 
# 15. DONE - Figure out the character limits for different values from coinbase, cleanup the digits on our logging output so it's more readable. 
# 15a. 	ANSWER: Bitcoin, Bitcoin Cash, Litecoin and Ethereum values will have 8 decimal points and fiat currencies will have two.
# 16. 


# Considerations:
# 1. MINIMAL CONCERN (assuming exit thresholds are spaced logically) - The script can only add one chunk of coins per interval when the price exceeds a threshold (or multiple). Debate whether we want it to add all of the available funds up to a specific price when multiple thresholds are crossed at once?
# 2. MINIMAL CONCERN - It seems prone to effects of short-term spikes. E.g., price spikes up 200-300 USD and then it drops back down immediately, but our stoploss is pulled up higher than we'd want. Could take like an average of the price over the last 3 seconds? Dunno. It doesn't need to be perfect though.
# 3. DECIDED AGAINST THIS - Maybe we should initialize the first stoploss at the threshold price? Then we can start walking the threshold up once the potential new stoploss [(current price - (current price * stop percent))] is higher than our threshold? Otherwise stoploss = threshold price. That we we won't sell lower than the threshold. 
# 3a. DECIDED AGAINST THIS - Then also maybe we should update the stoploss to tbe the next threshold value if threshold is hit but we haven't moved up to the next stoploss value? Avoid situation where we increase hopper but our stoploss is still set at an earlier threshold value?
# 4. Decide on a restart strategy for the bot - do we want the systemd service to run constantly? To restart when it crashes? To restart only on reboot? etc. Think about implications. 


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
			

	def initialize_stop(self):

		self.stoploss_initialized = True
		self.tracked_price = self.price
		
		#if the stoploss is set in the table, grab that value, if not, set the stoploss from the market price
		if self.type == "buy":
			self.stoploss = (self.price + (self.price * self.stopsize))
			self.cursor = self.con.cursor()
			self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
			logger.warn('Stop loss initialized at: ' + str(self.stoploss))
			self.cursor.close()
			self.con.commit()
			
			return self.stoploss, self.stoploss_initialized, self.tracked_price
		
		else: 
			self.stoploss = (self.price - (self.price * self.stopsize)) # this sets our first stoploss below our initial threshold value, will be less likely to get stopped out
			self.cursor = self.con.cursor()
			self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
			logger.warn('Stop loss initialized at: ' + str(self.stoploss))
			self.cursor.close()
			self.con.commit()
		
			return self.stoploss, self.stoploss_initialized, self.tracked_price


	def update_stop(self):
		if self.stoploss_initialized is True:
			
			if self.type == "sell":
				if self.price > self.tracked_price:
					logger.warn('New high observed: %.2f' % self.price) # we may not need this - already returning this information when we update the stoploss
					self.tracked_price = self.price

				if (self.price - (self.price * self.stopsize)) > self.stoploss:
					self.stoploss = (self.price - (self.price * self.stopsize))
					self.cursor = self.con.cursor()
					self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
					self.cursor.close()
					self.con.commit()
					logger.warn("Updated stop loss to %.4f" % (self.stoploss))

				elif self.price <= self.stoploss:
					self.execute_sell()

			elif self.type == "buy":
				if self.price < self.tracked_price:
					logger.warn('New low observed: %.2f' % self.price)

				# enter logic to track current balance, if no balance, don't update the stoploss. Wait for us to deposit some USD. 	
				if (self.price + self.stopsize) < self.stoploss:
					self.stoploss = self.price + self.stopsize
					self.cursor = self.con.cursor()
					self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
					self.cursor.close()
					self.con.commit()
					logger.warn("Updated stop loss to %.8f" % self.stoploss)

				elif self.price >= self.stoploss:
					#self.running = False
					balance = self.coinbasepro.get_balance(self.market.split("/")[1])
					amount = (balance / self.price) * 0.999 # 0.10% maker/taker fee without BNB
					self.coinbasepro.buy(self.market, amount, self.price) # need to move this to an execute_buy() function
					logger.warn("Buy triggered | Price: %.8f | Stop loss: %.8f" % (self.price, self.stoploss))

		else:
			logger.info('No stoploss yet initialized. Waiting.')


	def execute_sell(self):

		# first, do a table lookup to find the most recent sold_at price
		self.cursor = self.con.cursor()
		last_threshold_sold_at = self.cursor.execute("SELECT * FROM thresholds WHERE threshold_hit = 'Y' and sold_at is not null;").fetchall()
		self.cursor.close()

		if last_threshold_sold_at:
			last_sold_at_price = last_threshold_sold_at[-1][4]
			# logger.info('current price: %s' % str(self.price))
			# logger.info('last sold price: %s' % str(last_sold_at_price))

			killswitch = self.price < last_sold_at_price
			logger.info('Killswitch: ' + str(killswitch))

			#kill switch logic here (if current price is lower than most recent sold_at price, do not execute a sell!)
			if killswitch:
				logger.warn('KILL SWITCH TRIGGERED!!!')
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

				self.run() #restart our loop. Don't execute sell. Instead, check prices again, etc. 


			else: #do I need an else here?
				logger.info('THIS IS A SAFE SELL, NO KILLSWITCH TRIGGERED')

		else:
			print('No kill switch functionality needed - we havent sold anything yet') #We should think about whether we want a kill switch on our first threshold?

		try:
			# sell_complete = ""
			logger.warn("Sell triggered | Current price: %.2f | Stop loss: %.8f" % (self.price, self.stoploss))
			error_message = 'Failed to execute sell order'
			logger.warn("Attempting to sell %s %s at %.2f for %.2f %s" % (self.hopper, self.market.split("/")[0], self.price, (self.price*self.hopper), self.market.split("/")[1]))
			self.coinbasepro.sell(self.market, self.hopper)
			#sell_complete = self.coinbasepro.sell(self.market, self.hopper)
			logger.warn("Sell successful") # we need to call coinbase and get the exact value of the sell, use the order id

			# if sell_complete returns a 200 from coinbase: #trying to make sure that the database doesn't get updated unless a sell was actually executed, i.e. we have a value in sell_complete
			# 	print('sell_complete = TRUE - YES')
			# if it doesn't return a 200

			# reset hopper after executing sell
			error_message = 'Failed to update exit_strategy.db after executing sell order'
			self.cursor = self.con.cursor()
			self.cursor.execute("REPLACE INTO hopper (id, amount) VALUES (1, 0)")
			self.hopper = 0

			# reset stoploss after executing sell
			self.stoploss = None
			self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
			self.stoploss_initialized = False

			# add sell price to sold_at column for all rows included in the current hopper
			self.cursor.execute("UPDATE thresholds SET sold_at = %.2f WHERE threshold_hit = 'Y' AND sold_at is null" % self.price)
			logger.info("Updated sold_at column(s)!")

			self.cursor.close()
			self.con.commit()

			logger.warn("Reset Hopper: " + str(self.hopper))
			logger.warn("Reset Stoploss: " + str(self.stoploss))

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
			
			if self.price >= threshold:
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
		logger.info("---------------------")
		logger.info("Trail type: %s" % self.type)
		logger.info("Market: %s" % self.market)
		logger.info("Available to sell: %.4f" % self.hopper)
		if self.stoploss_initialized is True:
			logger.info("Stop loss: %s" % self.stoploss)
		else:
			logger.info('Stop loss: N/A')
		logger.info("Trailing stop: %s percent" % (self.stopsize*100))
		logger.info("Last price: %.2f" % self.price)
		logger.info("---------------------")


	def get_price(self):
		try:
			self.price = self.coinbasepro.get_price(self.market)
			#self.price = float(input('TEST PRICE: ')) #<-- this allows us to manually enter a TEST PRICE to validate script
			return self.price
		except Exception as e:
			logging.error(e)
			# if there is a network error, this will sleep for 5 seconds

	def run(self):
		self.running = True
		while (self.running):
			if self.get_price():
				self.print_status()
				self.update_stop()
				self.update_hopper()
			time.sleep(self.interval)