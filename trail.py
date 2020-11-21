import ccxt
from coinbasepro import CoinbasePro
import config
import time
import datetime
import pandas as pd
import sqlite3 as sl

# PLEASE CONFIGURE API DETAILS IN config.py

# To Do:
# 1. DONE? - Instead of usin a static amount of funds, create a function to read from a dataframe, check against current price, and update a "holding pen/hopper" with more ETH as new thresholds are crossed (https://stackoverflow.com/questions/42285806/how-to-pop-rows-from-a-dataframe)
# 2. DONE - Modify the stop loss to use a % rather than a static amount. E.g., 5% stop loss.
# 3. DONE? - Modify the logging output to specify how much is currently in the hopper (e.g., ETH to trade: 0.5, 0.75, etc.)
# 4. DONE - Adjust script so it only initializes the stop loss once a threshold is first hit
# 5. Need to allow script to continue running after a sell, right now it simply exits
# 6. DONE - Persist the exit strategy table and make adjustments based on what thresholsd have been hit.
# 6b. 	Should persist a Hit Threshold Y/N for each line/row - then look for the first threshold that hasn't been hit
# 7. DONE - Persist the hopper data in another table in the sqlite db. initialize_hopper() and update_hopper() should read from this table.
# 7a. 	When hopper changes, insert the new value into the database.
# 7. Set up actual logging output to a logfile. Print timestamps for each message. Hopper updates, stop loss updates, etc should all be logged to the system for tracking purposes.
# 8. Error handling? e.g., ccxt.base.errors.InsufficientFunds: coinbasepro Insufficient funds
# 9. Prepare to dockerize the script
# 10. Improve testability - comment out the check_price call and have script ask for a manual price entry to test against?


# Other Notes:
# 1. The script can only add one chunk of coins per interval when the price exceeds a threshold (or multiple). Debate whether we want it to add all of the available funds up to a specific price when multiple thresholds are crossed at once?
# 2. It seems prone to effects of short-term spikes. E.g., price spikes up 200-300 USD and then it drops back down immediately, but our stoploss is pulled up higher than we'd want. Could take like an average of the price over the last 3 seconds? Dunno. It doesn't need to be perfect though.

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
		
		#self.stoploss_initialized = False
		
		#Open db connection and check for a persisted stoploss value
		self.con = sl.connect("exit_strategy.db")
		self.cursor = self.con.cursor()
		self.cursor.execute("SELECT * FROM stoploss;")
		first_row = self.cursor.fetchone()
		self.cursor.close()
				
		stop_value = first_row[1]
		print('Stoploss already set at: ' + str(stop_value))
		
		if stop_value != None:
			self.stoploss = first_row[1]
			self.stoploss_initialized = True
		else:
			print('else')
			self.stoploss_initialized = False
			
			
		self.hopper = self.initialize_hopper()
			
	def __del__(self):
		print('\nInside __del__') 
		print('Deconstructing StopTrail() safely')
		self.close_db()
			

	def __exit__(self, exc_type, exc_value, traceback): 
		print('\nInside __exit__') 
		print('\nExecution type:', exc_type) 
		print('\nExecution value:', exc_value) 
		print('\nTraceback:', traceback) 
		self.close_db()
		
	def close_db(self):
		if self.con:
			 self.con.commit()
			 self.con.close()
			 print('Database closed')
			
	def initialize_stop(self):
		self.stoploss_initialized = True
		price = self.coinbasepro.get_price(self.market)
		
		#if the stoploss is set in the table, grab that value, if not, set the stoploss from the market price
		if self.type == "buy":
			self.stoploss = (price + (price * self.stopsize))
			self.cursor = self.con.cursor()
			self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
			print('Stop loss initialized at: ' + str(self.stoploss))
			self.cursor.close()
			self.con.commit()
			
			return self.stoploss, self.stoploss_initialized
		else: 
			self.stoploss = (price - (price * self.stopsize))
			self.cursor = self.con.cursor()
			self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
			print('Stop loss initialized at: ' + str(self.stoploss))
			self.cursor.close()
			self.con.commit()
		
			return self.stoploss, self.stoploss_initialized

	def update_stop(self):
		if self.stoploss_initialized is True:
			price = self.coinbasepro.get_price(self.market)
			if self.type == "sell":
				if (price - (price * self.stopsize)) > self.stoploss:
					self.stoploss = (price - (price * self.stopsize))
					
					self.cursor = self.con.cursor()
					self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
					self.cursor.close()
					self.con.commit()
					
					print("New high observed: Updated stop loss to %.8f" % self.stoploss)
				elif price <= self.stoploss:
					self.running = False #this is the line that "breaks" the script and stops everything, just remove this to keep it running after a sell?
					amount = self.hopper 
					# when we sell here we need to reset the hopper value in the hopper table, else when the script restarts it will keep the old hopper value
					self.coinbasepro.sell(self.market, amount)
				
					self.cursor = self.con.cursor()
					self.cursor.execute("REPLACE INTO hopper (id, amount) VALUES (1, 0)")
					self.hopper = 0
					self.cursor.close()
					self.con.commit()
					
					print("Sell triggered | Price: %.8f | Stop loss: %.8f" % (price, self.stoploss))
					print("Sold %.8f %s at %.8f for %.8f %s" % (amount, self.market.split("/")[0], price, (price*amount), self.market.split("/")[1]))
					print("Reset Hopper: " + str(self.hopper))
			elif self.type == "buy":
				if (price + self.stopsize) < self.stoploss:
					self.stoploss = price + self.stopsize
				
					self.cursor = self.con.cursor()
					self.cursor.execute("REPLACE INTO stoploss (id, stop_value) VALUES (?, ?)", (1, self.stoploss))
					self.cursor.close()
					self.con.commit()
				
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
		#df = pd.DataFrame(data=config.EXIT_STRATEGY['DATA'])
		#self.hopper = 0
		#return df, self.hopper

		# DATABASE REFACTOR: read hopper value from the HOPPER table of the db
		self.cursor = self.con.cursor()
		self.cursor.execute("SELECT * FROM HOPPER;")
		first_row = self.cursor.fetchone()
		self.cursor.close()

		hopper_amount = first_row[1]
		print('Hopper: ' + str(hopper_amount))
		self.hopper = hopper_amount
		return self.hopper


	def update_hopper(self):

		price = self.coinbasepro.get_price(self.market)

		self.cursor = self.con.cursor()
		self.cursor.execute("SELECT Count(*) from thresholds WHERE threshold_hit = 'N';")
		result = self.cursor.fetchone()
		self.cursor.close()
		remaining_rows = result[0]
		print('remaining rows: ' + str(remaining_rows))

		if remaining_rows > 0:
			self.cursor = self.con.cursor()
			self.cursor.execute("SELECT * FROM thresholds WHERE threshold_hit = 'N';")
			
			first_row = self.cursor.fetchone()
			self.cursor.close()
			exit_price = first_row[1]
			exit_amount = first_row[2]
			
			if price >= exit_price:
				row_id = str(first_row[0])
				self.cursor = self.con.cursor()
				self.cursor.execute("UPDATE thresholds SET threshold_hit = 'Y' WHERE id = ?", (row_id))
				self.cursor.close()
				self.con.commit()
				
				print('Hit our threshold at ' + str(exit_price) + '. Adding ' + str(exit_amount) + ' to hopper.')
				if self.stoploss_initialized == False:
					self.initialize_stop()
				# write the new hopper value to the hopper table
				
				self.hopper += exit_amount
				self.cursor = self.con.cursor()
				self.cursor.execute("REPLACE INTO hopper (id, amount) VALUES (?, ?)", (1, self.hopper)) # this should prob be UPDATE
				self.cursor.close()
				self.con.commit()
				print('Hopper: ' + str(self.hopper))
				
			else:
				threshold = exit_price
				print('Price has not yet met the next threshold of ' + str(threshold))
				

		else:
			print('No more values to add to hopper.')
			

		# OLD STRATEGY, DATAFRAME
		# if total_rows > 0:
		# 	if price >= self.df.iloc[0]['price']:
		# 		self.df,first_row = self.df.drop(self.df.head(1).index),self.df.head(1)
		# 		amount = first_row.iloc[0]['amount']
		# 		threshold = first_row.iloc[0]['price']
		# 		print('Hit our threshold at ' + str(threshold) + '. Adding ' + str(amount) + ' to hopper.')
		# 		#print('Update Hopper stoploss status: ' + str(self.stoploss_initialized) )
		# 		if self.stoploss_initialized == False:
		# 			 self.initialize_stop()
		# 		self.hopper += amount
		# 		print('Hopper: ' + str(self.hopper))
		# 	else:
		# 		threshold = self.df.iloc[0]['price']
		# 		print('Price has not yet met the next threshold of ' + str(threshold))

		# else:
		# 	print('No more values to add to hopper.')

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
