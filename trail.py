import ccxt
from coinbasepro import CoinbasePro
import config
import time
import datetime
import pandas as pd

# PLEASE CONFIGURE API DETAILS IN config.py

# To Do:
# 1. DONE? - Instead of usin a static amount of funds, create a function to read from a dataframe, check against current price, and update a "holding pen/hopper" with more ETH as new thresholds are crossed (https://stackoverflow.com/questions/42285806/how-to-pop-rows-from-a-dataframe)
# 2. DONE - Modify the stop loss to use a % rather than a static amount. E.g., 5% stop loss.
# 3. DONE? - Modify the logging output to specify how much is currently in the hopper (e.g., ETH to trade: 0.5, 0.75, etc.)
# 4. DONE - Adjust script so it only initializes the stop loss once a threshold is first hit
# 5. Need to allow script to continue running after a sell, right now it simply exits
# 6. Figure out how to persist the exit strategy table and make adjustments based on what thresholsd have been hit.
# 6a. 	Right now every time the script runs it resets the thresholds. Instead, it should update the threshold information to remove cases that have been added to the hopper and/or sold.
# 7. Set up actual logging output to a logfile. Print timestamps for each message. Hopper updates, stop loss updates, etc should all be logged to the system for tracking purposes.
# 8. Error handling? e.g., ccxt.base.errors.InsufficientFunds: coinbasepro Insufficient funds
# 9. Prepare to dockerize the script


# Other Notes:
# 1. The script can only add one chunk of coins per interval when the price exceeds a threshold (or multiple). Debate whether we want it to add all of the available funds up to a specific price when multiple thresholds are crossed at once?

class StopTrail():

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
		#print('Init: ' + str(self.stoploss_initialized))
		self.df, self.hopper = self.initialize_hopper()
		self.stoploss_initialized = False
		#print('Init: ' + str(self.stoploss_initialized))

	def initialize_stop(self):
		self.stoploss_initialized = True
		price = self.coinbasepro.get_price(self.market)
		#print('initialize stop status: ' + str(self.stoploss_initialized))
		if self.type == "buy":
			self.stoploss = (price + (price * self.stopsize))
			print('Stop loss initialized at: ' + str(self.stoploss))
			return self.stoploss, self.stoploss_initialized
		else:
			self.stoploss = (price - (price * self.stopsize))
			print('Stop loss initialized at: ' + str(self.stoploss))
			return self.stoploss, self.stoploss_initialized

	def update_stop(self):
		#print('update_stop() :' + str(self.stoploss_initialized))
		if self.stoploss_initialized is True:
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
				#print('Update Hopper stoploss status: ' + str(self.stoploss_initialized) )
				if self.stoploss_initialized == False:
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
		ts = time.time()
		st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
		print("---------------------")
		print(st)
		print("Trail type: %s" % self.type)
		print("Market: %s" % self.market)
		print("Available to sell: %s" % self.hopper)
		if self.stoploss_initialized is True:
			print("Stop loss: %s" % self.stoploss)
		else:
			print('Stop loss: N/A')
		print("Trailing stop: %s percent" % (self.stopsize*100))
		print("Last price: %.8f" % price)
		print("---------------------")

	def run(self):
		self.running = True
		while (self.running):
			self.print_status()
			self.update_stop()
			self.update_hopper()
			time.sleep(self.interval)
