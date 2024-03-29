import ccxt
import config
import datetime
import logging
import time
import pandas as pd
import sqlite3 as sl
from src.coinbasepro import CoinbasePro
from src.definitions import LOG_DIR
from src.helper import get_logger, send_sns, Config

logger = get_logger(__file__)

class StopTrail():

	def __init__(self, market, type, stopsize, interval, split):

		logger.warning('Initializing bot...')
		logger.warning('RUNNING IN TEST MODE')

		# establish a connection with exchange
		self.coinbasepro = CoinbasePro(
			api_key=Config.get_value('live_api','api_key'),
			api_secret=Config.get_value('live_api','api_secret'),
			password=Config.get_value('live_api','password')
		)
		
		# set our variables
		self.market = market
		self.type = type
		self.stopsize = stopsize
		self.interval = interval
		self.split = split
		self.running = False
		self.tracked_price = self.coinbasepro.get_price(self.market)
		self.tracked_balance = self.coinbasepro.get_balance(self.market.split("/")[1])
		
		if self.split == 1:
			logger.warning('Running in single coin mode: %s' % self.market)
		else:
			logger.warning('Running in multiple coin mode (%s)' % self.split)

		# open db connection and check for a persisted stoploss value
		self.con = sl.connect("exit_strategy.db")
		self.cursor = self.con.cursor()
		self.cursor.execute("SELECT * FROM stoploss;")
		first_row = self.cursor.fetchone()
		self.cursor.close()
		stop_value = first_row[1]
		if stop_value != None:
			logger.warn('Stoploss already set at: %.2f' % stop_value)
			self.stoploss = float(first_row[1])
			self.stoploss_initialized = True
		else:
			logger.info('No stoploss currently set')
			self.stoploss_initialized = False
		self.hopper = self.initialize_hopper()

			
	def __del__(self):
		logger.warning('Program has exited')
		self.close_db()


	def __exit__(self, exc_type, exc_value, traceback): 
		logger.info('Inside __exit__') 
		logger.warning('Program has exited.')
		self.close_db()

		
	def close_db(self):
		if self.con:
			 self.con.commit()
			 self.con.close()
			 logger.info('Database closed')
			

	def initialize_hopper(self):
		if self.type == "sell":
			self.cursor = self.con.cursor()
			self.cursor.execute("SELECT * FROM hopper ;")
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
		if self.type == 'sell':
			self.cursor = self.con.cursor()
			self.cursor.execute("SELECT Count(*) from thresholds WHERE threshold_hit = 'N';")
			result = self.cursor.fetchone()
			self.cursor.close()
			remaining_rows = result[0]
			#logger.info('Thresholds remaining: ' + str(remaining_rows))

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
						logger.warn('Thresholds remaining: %s' % (int(remaining_rows)-1))
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


	def initialize_stop(self):
		#If stoploss is already set retrieve that value from the stoploss table. If not, set the stoploss from the market price.
		self.stoploss_initialized = True
		self.tracked_price = self.price
		
		if self.type == "buy":

			lower_threshold = self.price_at_deposit - (self.price_at_deposit * self.stopsize)
			self.stoploss = self.price_at_deposit
			logger.warn('Price has dropped at least %.2f%% from deposit price and hit our lower threshold of %.2f' % ((self.stopsize*100), lower_threshold))

			# write the stoploss value to the stoploss table
			self.cursor = self.con.cursor()
			self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
			logger.warn('Stop loss initialized at deposit price: %.2f' % self.stoploss)
			self.cursor.close()
			self.con.commit()
				
			return self.stoploss, self.stoploss_initialized, self.tracked_price


		elif self.type == "sell": 
			
			self.stoploss = (self.price - (self.price * self.stopsize)) 
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
					logger.warn('New high observed: %.2f' % self.price)
					self.tracked_price = self.price

				if (self.price - (self.price * self.stopsize)) > self.stoploss:
					self.stoploss = (self.price - (self.price * self.stopsize))
					self.cursor = self.con.cursor()
					self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
					self.cursor.close()
					self.con.commit()
					logger.warn("Raised stop loss to %.2f" % (self.stoploss))

				elif self.price <= self.stoploss:
					self.execute_sell()

			elif self.type == "buy":
				if self.price < self.tracked_price:
					logger.warn('New low observed: %.2f' % self.price)
					self.tracked_price = self.price

				# enter logic to track current balance, if no balance, don't update the stoploss. Wait for us to deposit some USD. 	
				if self.balance > 1:

					if (self.price + (self.price * self.stopsize)) < self.stoploss:
						self.stoploss = (self.price + (self.price * self.stopsize))
						self.cursor = self.con.cursor()
						self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
						self.cursor.close()
						self.con.commit()
						logger.warn("Lowered stop loss to %.2f" % self.stoploss)

					elif self.price >= self.stoploss:
						self.execute_buy()

				else: 
					logger.warn('No USD available. Waiting for deposit.')
		else:
			logger.info('No stoploss yet initialized. Waiting.')


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

		#else:
			#logger.info('No kill switch functionality needed - we havent sold anything yet') #We should think about whether we want a kill switch on our first threshold?

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
				# logger.info(fetch_order)
				# logger.info('id: %s' % id)
				# logger.info('size: %s' % size)
				# logger.info('price: %s' % price)
				# logger.info('status: %s' % status)
				# logger.info('done_reason: %s' % done_reason)
				if status == 'done' and done_reason == 'filled': #verify what a successful order looks like
					filled, sell_value, fee = fetch_order['amount'], fetch_order['cost'], fetch_order['fee']['cost']
					pending = False
					logger.warn("Sell order executed and filled successfully.")
					logger.warn("Sold %.6f %s for %.2f %s. Fees: %.2f" % (filled, self.market.split("/")[0], sell_value, self.market.split("/")[1], fee))
				elif status == 'done' and done_reason == 'cancelled':
					pending = False
					logger.warn('Sell order was canceled by exchange.')
					self.run() #if order was canceled, we want to exit this current function and restart our check_price loop to try again. 
				else:	
					time.sleep(2)
					#if status is anything other than 'closed' or 'done', we want to 
					#then wait like 2-3 seconds, check again?

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

		except Exception as e:
			logger.exception('%s | %s' % (error_message, e))
			raise


	def execute_buy(self):
		amount = ((self.coin_hopper / self.price) * 0.995)
		price = 1000000
		error_message = 'Failed to execute buy order'

		try: 
			logger.warn("ORDER: Buy triggered | Price: %.2f | Stop loss: %.2f" % (self.price, self.stoploss))
			logger.warn("ORDER: Executing market order (BUY) of ~%.4f %s at %.2f %s for %.2f %s" % (amount, self.market.split("/")[0], self.price, self.market.split("/")[1], (self.coin_hopper), self.market.split("/")[1]))
			#buy_order = self.coinbasepro.buy(self.market, amount, price) #buy with our entire available_funds for the coin (set super high limit price, effectively market sell)

			#logger.info('sell order json: %s' % buy_order)
			# id = buy_order['info']['id']
			# pending = True
			# fetch_order = self.coinbasepro.get_order(id)
			# size, price, status, done_reason = fetch_order['info']['size'], fetch_order['price'], fetch_order['info']['status'], fetch_order['info']['done_reason']
			# # while pending:
			# 	if status == 'done' and done_reason == 'filled':
			# 		filled, sell_value, fee, filled_price = fetch_order['amount'], fetch_order['cost'], fetch_order['fee']['cost'], (float(fetch_order['info']['executed_value']) / float(fetch_order['info']['filled_size']))
			# 		pending = False
			# 		logger.warn("ORDER: Buy order executed and filled successfully.")
			# 		message = "ORDER: Bought %.6f %s at %.2f for %.2f %s. Fees: %.2f" % (filled, self.market.split("/")[0], filled_price, sell_value, self.market.split("/")[1], fee)
			# 		send_sns(message)
			# 		logger.warn("ORDER: Bought %.6f %s at %.2f for %.2f %s. Fees: %.2f" % (filled, self.market.split("/")[0], filled_price, sell_value, self.market.split("/")[1], fee))

			# update win_tracker, add to the # of buys in the table, add to # of wins if it's a win
			# output whether buy was a win, display % of buys that are wins
			self.cursor = self.con.cursor()
			self.cursor.execute("SELECT * FROM win_tracker;")
			data = self.cursor.fetchone()
			self.cursor.close()
			price_at_deposit = data[1]
			buy_count = data[3]
			win_count = data[4]
			logger.warn('price_at_deposit: %.2f' % price_at_deposit)
			logger.warn('price_at_buy: %.2f' % self.price)

			diff = self.price - price_at_deposit
			percent_diff = 100 * (abs(diff) / price_at_deposit)

			if self.price < price_at_deposit:
				win_count += 1
				logger.warn("RESULT (WIN): bought %.2f lower than at deposit time! +%.2f%%" % (diff, percent_diff))
					
			else:
				logger.warn("RESULT (LOSS): bought %.2f higher than at deposit time. -%.2f%%" % (diff, percent_diff))

			buy_count += 1
			win_percent = (win_count / buy_count) * 100
			logger.warn("TESTING: Win percentage is %i / %i = %.2f%%" % (win_count, buy_count, win_percent))

			query = "UPDATE win_tracker SET price_at_buy = ?, buy_count = ?, win_count = ?"
			query_data = (self.price, buy_count, win_count)
			self.cursor = self.con.cursor()
			self.cursor.execute(query, query_data)
			self.cursor.close()
			self.con.commit()

				# elif status == 'done' and done_reason == 'canceled':
				# 	pending = False
				# 	logger.warn('Buy order was canceled by exchange.')
				# 	self.run()
				# else:	
				# 	logger.info('waiting')
				# 	time.sleep(2)


			# reset stoploss after executing buy
			error_message = 'Failed to update exit_strategy.db after executing sell order'
			self.stoploss = None
			self.cursor = self.con.cursor()
			self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
			self.cursor.close()
			self.stoploss_initialized = False
			logger.warn("Reset Stoploss: " + str(self.stoploss))

			# reset coin_hopper after executing buy
			error_message = 'Failed to update exit_strategy.db after executing sell order'
			self.cursor = self.con.cursor()
			self.cursor.execute("REPLACE INTO available_funds (id, account_balance, coin_hopper) VALUES (?, ?, ?)", (1, self.balance, 0))
			self.coin_hopper = 0
			logger.warn("Reset coin_hopper: " + str(self.coin_hopper))
			time.sleep(10)
			self.get_price()

			logger.warn('PRICE: Market price at time of deposit: %.2f' % self.price)
			self.cursor = self.con.cursor()
			self.cursor.execute("UPDATE win_tracker SET price_at_deposit = %.2f" % self.price)
			self.cursor.close()
			self.con.commit()

		
		except ccxt.AuthenticationError as e:
			logger.error('Failed to execute sell order | Authentication error | %s' % str(e))
			raise
		except ccxt.InsufficientFunds as e:
			logger.error('Failed to execute sell order  | Insufficient funds | %s' % str(e))
			raise
		except ccxt.BadRequest as e:
			logger.error('Failed to execute sell order  | Bad request| %s' % str(e))
			raise
		except ccxt.NetworkError as e:
			logger.error('Failed to execute sell order  | Network error | %s' % e)

		except Exception as e:
			logger.error('%s | %s' % (error_message, e))
			raise


	def dca_buy_logic(self):

		self.cursor = self.con.cursor()
		self.cursor.execute("SELECT * FROM win_tracker;")
		data = self.cursor.fetchone()
		self.cursor.close()

		price_at_deposit = data[1]
		upper_threshold = price_at_deposit + (price_at_deposit * self.stopsize)
		lower_threshold = price_at_deposit - (price_at_deposit * self.stopsize)

		if self.price > upper_threshold:
			logger.warn('Price has risen %.2f%% from deposit price and hit our upper threshold of %.2f' % ((self.stopsize*100), upper_threshold))
			self.stoploss = upper_threshold
			self.execute_buy()

		elif self.price <= lower_threshold:
			#logger.info('price is lower than threshold (verify)')
			try:	
				# initialize a stoploss, if one is not already initialized 
				# stoploss needs to be initialized at the deposit price
				if self.stoploss_initialized == False:
					self.initialize_stop()
			except Exception as e:
					('Failed to initialize_stop() | %s' % e)

		else:
			if self.stoploss_initialized == False:
				logger.info('Price is still within our starting range of +/- %.2f%% from deposit price (%.2f to %.2f). Taking no action.' % ((self.stopsize*100), upper_threshold, lower_threshold))
			


	def print_status(self):
		logger.info('test: stoploss_initialized = %s' % self.stoploss_initialized)

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


	def get_price(self):
		try:
			# self.price = self.coinbasepro.get_price(self.market)
			### TURN ONTO TEST PRICE MANUALLY
			self.price = float(input('TEST PRICE: ')) #<-- this allows us to manually enter a TEST PRICE to validate script
			return self.price
		except Exception as e:
			logging.error(e)
			# if there is a network error, this will sleep for 5 seconds


	def get_balance(self):
			# get coinbase balance
			#self.balance = self.coinbasepro.get_balance(self.market.split("/")[1])
		try:
			self.balance = 150

			# if self.balance > 50: # need some threshold of account balance - otherwise we should wait for more funds. What's the minimum USD buy?
			# get last_known_balance from the available_funds table
			self.cursor = self.con.cursor()
			self.cursor.execute("SELECT * FROM available_funds;")
			first_row = self.cursor.fetchone()
			self.cursor.close()
			last_known_account_balance = first_row[1]
			self.coin_hopper = first_row[2]

			# take the difference between the coinbase balance and the last_known_account_balance
			difference = self.balance - last_known_account_balance

			self.print_status()

			if difference > 0:
				# split the newly deposited USD and allocate to the coin_hopper
				split_deposit = difference / self.split #e.g., if 1 coin, difference == difference, if 2 coins difference == difference/2
				self.coin_hopper += split_deposit

				# replace the last known account balance with the balance from coinbase
				self.cursor = self.con.cursor()
				self.cursor.execute("REPLACE INTO available_funds (id, account_balance, coin_hopper) VALUES (?, ?, ?)", (1, self.balance, self.coin_hopper))
				self.cursor.close()
				self.con.commit()
				logger.warn("DEPOSIT: %.2f USD was just added to account balance. New total: %.2f" % (difference, self.balance))
				if self.split > 1:
					logger.warn('DEPOSIT: Dividing deposit into %s even allocations of %.2f.' % (self.split, split_deposit))
				logger.warn('DEPOSIT: Total funds now available to purchase %s: %.4f %s' % (self.market.split("/")[0], self.coin_hopper, self.market.split("/")[1]))
				
				#update the price at deposit for the win tracker
				logger.warn('PRICE: Market price at time of deposit: %.2f' % self.price)
				self.cursor = self.con.cursor()
				self.price_at_deposit = self.price
				self.cursor.execute("UPDATE win_tracker SET price_at_deposit = %.2f" % self.price)
				self.cursor.close()
				self.con.commit()

				return self.price_at_deposit

			elif difference < 0: 
				# do nothing with the coin hopper
				# update the last known account balance to reflect balance in coinbase
				# self.cursor = self.con.cursor()
				# self.cursor.execute("REPLACE INTO available_funds (id, account_balance, coin_hopper) VALUES (?, ?, ?)", (1, self.balance, self.coin_hopper))
				# self.cursor.close()
				# self.con.commit()
				logger.warn("UPDATE: %.2f USD was just removed from account balance. New total: %.2f" % (abs(difference), self.balance))

			#elif difference == 0:
				#logger.info('No new deposit.')

			if self.coin_hopper > 50:
				self.dca_buy_logic()

			else:
				logger.info('Allocated funds (%.2f) for %s too low to satisfy minumum order size requirements. Waiting for additional deposit before initializing stop loss.' % (self.coin_hopper, self.market.split("/")[0]))

			return self.balance, self.coin_hopper

		except Exception as e:
			logging.exception(e)


	def run(self):
		self.running = True
		while (self.running):
			if self.type == "sell":
				if self.get_price():
					self.print_status()
					self.update_stop()
					self.update_hopper()
			elif self.type == "buy":
				if self.get_price():
						self.get_balance()
						self.update_stop()
			time.sleep(self.interval)