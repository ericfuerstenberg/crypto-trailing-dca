import ccxt
from coinbasepro import CoinbasePro
import config
import time
import pandas as pd

# PLEASE CONFIGURE API DETAILS IN config.py

# To Do:
# 1. DONE? - Instead of usin a static amount of funds, create a function to read from a dataframe, check against current price, and update a "holding pen/hopper" with more ETH as new thresholds are crossed (https://stackoverflow.com/questions/42285806/how-to-pop-rows-from-a-dataframe)
# 2. DONE - Modify the stop loss to use a % rather than a static amount. E.g., 5% stop loss.
# 3. DONE? - Modify the logging output to specify how much is currently in the hopper (e.g., ETH to trade: 0.5, 0.75, etc.)
# 4. Adjust script so it only initializes the stop loss once a threshold is first hit
# 5. Set up actual logging output to a logfile. Print timestamps for each message. Hopper updates, stop loss updates, etc should all be logged separately for tracking purposes.
# 6. Error handling? e.g., ccxt.base.errors.InsufficientFunds: coinbasepro Insufficient funds
# 7. Prepare to dockerize the script

class StopTrail():

	print('starting StopTrail')
	stoploss_initialized = False # can't get this variable to update from functions below. Why? I know it's not looping back up here.. it's just not updating below.

	def __init__(self, market, type, stopsize, interval):
		self.coinbasepro = CoinbasePro(
			api_key=config.API_DETAILS['API_KEY'],
			api_secret=config.API_DETAILS['API_SECRET'],
			password=config.API_DETAILS['PASSWORD']
		)
		self.market = market
		self.type = type
		self.stopsize = stopsize
		self.interval = interval
		self.running = False
		#self.stopinit = StopTrail.stoploss_initialized
		print('Init: ' + str(StopTrail.stoploss_initialized))
		self.df, self.hopper = self.initialize_hopper()

	def initialize_stop(self):
		global stoploss_initialized
		#global self.stopinit
		price = self.coinbasepro.get_price(self.market)
		stoploss_initialized = True
		print('initialize stop status: ' + str(StopTrail.stoploss_initialized))
		if self.type == "buy":
			self.stoploss = (price + (price * self.stopsize))
			print('Stop loss initialized at: ' + str(self.stoploss))
			return self.stoploss, stoploss_initialized
		else:
			self.stoploss = (price - (price * self.stopsize))
			print('Stop loss initialized at: ' + str(self.stoploss))
			return self.stoploss, stoploss_initialized
		# print('Stop loss initialized at: ' + str(self.stoploss))
		# stoploss_initialized = True
		# print('initialize stop status 2: ' + str(stoploss_initialized))
		# return stoploss_initialized
		# self.stopinit = True
		# return self.stopinit

	def update_stop(self):
		if StopTrail.stoploss_initialized is True:
			price = self.coinbasepro.get_price(self.market)
			if self.type == "sell":
				if (price - (price * self.stopsize)) > self.stoploss:
					self.stoploss = (price - (price * self.stopsize))
					print("New high observed: Updating stop loss to %.8f" % self.stoploss)
				elif price <= self.stoploss:
					self.running = False
					#amount = self.coinbasepro.get_balance(self.market.split("/")[0]) # would need to update this to read amount from the 'holding pen/hopper' 
					amount = self.hopper
					price = self.coinbasepro.get_price(self.market)
					self.coinbasepro.sell(self.market, amount, price)
					print("Sell triggered | Price: %.8f | Stop loss: %.8f" % (price, self.stoploss))
					print("Sold %.8f %s for %.8f %s" % (amount, self.market.split("/")[0], (price*amount), self.market.split("/")[1]))
			elif self.type == "buy":
				if (price + self.stopsize) < self.stoploss:
					self.stoploss = price + self.stopsize
					print("New low observed: Updating stop loss to %.8f" % self.stoploss)
				elif price >= self.stoploss:
					self.running = False
					balance = self.coinbasepro.get_balance(self.market.split("/")[1])
					price = self.coinbasepro.get_price(self.market)
					amount = (balance / price) * 0.999 # 0.10% maker/taker fee without BNB
					self.coinbasepro.buy(self.market, amount, price)
					print("Buy triggered | Price: %.8f | Stop loss: %.8f" % (price, self.stoploss))
		else:
			print('No stoploss yet initialized. Waiting.')

	def initialize_hopper(self):
		# set the base dataframe here and initialize the empty hopper
		df = pd.DataFrame(data=config.EXIT_STRATEGY['DATA'])
		self.hopper = 0
		return df, self.hopper


	def update_hopper(self):
		# create a function that watches the current price and if it meets the threshold set in the dataframe, move the specified amount of ETH from the dataframe to the hopper
		# self.update_hopper()
		# hopper should contain a running tally of the "released" ETH that can be used during the next trade 
		#    price  amount
		# 0  18190    0.05
		# 1  18200    0.09
		# 2  18202    0.10

		price = self.coinbasepro.get_price(self.market)
		total_rows = len(self.df.index)

		if total_rows > 0:
			if price >= self.df.iloc[0]['price']:
				self.df,first_row = self.df.drop(self.df.head(1).index),self.df.head(1)
				amount = first_row.iloc[0]['amount']
				threshold = first_row.iloc[0]['price']
				print('Hit our threshold at ' + str(threshold) + '. Adding ' + str(amount) + ' to hopper.')
				print('Update Hopper stoploss status: ' + str(StopTrail.stoploss_initialized) )
				if StopTrail.stoploss_initialized == False:
					 self.initialize_stop()
				self.hopper += amount
				print('Hopper: ' + str(self.hopper))
			else:
				threshold = self.df.iloc[0]['price']
				print('Price has not yet met the next threshold of ' + str(threshold))
		else:
			print('No more values to add to hopper.')

		return self.hopper


	def print_status(self):
		price = self.coinbasepro.get_price(self.market)
		print("---------------------")
		print("Trail type: %s" % self.type)
		print("Market: %s" % self.market)
		print("Available to sell: %s" % self.hopper)
		print("Last price: %.8f" % price)
		if StopTrail.stoploss_initialized is True:
			print("Stop loss: %s" % self.stoploss)
		else:
			print('Stop loss: N/A')
		print("Trailing stop: %s percent" % (self.stopsize*100))
		print("---------------------")


	def run(self):
		self.running = True
		while (self.running):
			self.print_status()
			self.update_hopper()
			self.update_stop()
			time.sleep(self.interval)

	# def run_once(f):
	# 	def wrapper(*args, **kwargs):
	# 		if not wrapper.has_run:
	# 			wrapper.has_run = True
	# 			return f(*args, **kwargs)
	# 	wrapper.has_run = False
	# 	return wrapper