import ccxt
from binance import Binance
import config
import time

# PLEASE CONFIGURE API DETAILS IN config.py

# To Do:
# 1. Instead of usin a static amount of funds, create a function to read from a dataframe, check against current price, and update a "holding pen/hopper" with more ETH as new thresholds are crossed (https://stackoverflow.com/questions/42285806/how-to-pop-rows-from-a-dataframe)
# 2. Modify the stop loss to use a % rather than a static amount. E.g., 5% stop loss.

class StopTrail():

	def __init__(self, market, type, stopsize, interval):
		self.binance = Binance(
			api_key=config.API_DETAILS['API_KEY'],
			api_secret=config.API_DETAILS['API_SECRET']
		)
		self.market = market
		self.type = type
		self.stopsize = stopsize
		self.interval = interval
		self.running = False
		self.stoploss = self.initialize_stop()

	def initialize_stop(self):
		if self.type == "buy":
			return (self.binance.get_price(self.market) + self.stopsize)
		else:
			return (self.binance.get_price(self.market) - self.stopsize) # change to percent here; (self.binance.get_price(self.market) - (self.market * self.stopsize))

	def update_stop(self):
		price = self.binance.get_price(self.market)
		if self.type == "sell":
			if (price - self.stopsize) > self.stoploss:
				self.stoploss = price - self.stopsize
				print("New high observed: Updating stop loss to %.8f" % self.stoploss)
			elif price <= self.stoploss:
				self.running = False
				amount = self.binance.get_balance(self.market.split("/")[0]) # would need to update this to read amount from the 'holding pen/hopper' 
				price = self.binance.get_price(self.market)
				self.binance.sell(self.market, amount, price)
				print("Sell triggered | Price: %.8f | Stop loss: %.8f" % (price, self.stoploss))
		elif self.type == "buy":
			if (price + self.stopsize) < self.stoploss:
				self.stoploss = price + self.stopsize
				print("New low observed: Updating stop loss to %.8f" % self.stoploss)
			elif price >= self.stoploss:
				self.running = False
				balance = self.binance.get_balance(self.market.split("/")[1])
				price = self.binance.get_price(self.market)
				amount = (balance / price) * 0.999 # 0.10% maker/taker fee without BNB
				self.binance.buy(self.market, amount, price)
				print("Buy triggered | Price: %.8f | Stop loss: %.8f" % (price, self.stoploss))


	# def initialize_hopper(self):
		# set the base dataframe here and initialize the empty hopper

	# def update_hopper(self):
		# create a function that watches the current price and if it meets the threshold set in the dataframe, move the specified amount of ETH from the dataframe to the hopper
		# hopper should contain a running tally of the "released" ETH that can be used during the next trade

	def print_status(self):
		last = self.binance.get_price(self.market)
		print("---------------------")
		print("Trail type: %s" % self.type)
		print("Market: %s" % self.market)
		print("Stop loss: %.8f" % self.stoploss)
		print("Last price: %.8f" % last)
		print("Stop size: %.8f" % self.stopsize)
		print("---------------------")

	def run(self):
		self.running = True
		while (self.running):
			self.print_status()
			self.update_stop()
			time.sleep(self.interval)
