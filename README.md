# crypto-trailing-dca
Implements dynamic, trailing stop loss functionality for Coinbase Pro. Designed to be utilized in either 1) “buy-mode” to create a dollar cost average (DCA) strategy that capitalizes on short-term down swings or 2) “sell-mode” to maximize profits by executing a hybrid-DCA exit strategy based on predefined take-profit thresholds and trailing stop losses.


## Installation

**Clone the repository**
```
git clone https://github.com/efuerstenberg/crypto-trailing-stoploss
```

**Install required libraries**
```
apt-get install python-pip -y
pip install ccxt
```


## Configure API keys

Obtain an API key from Coinbase Pro with 'view' and 'trade' permissions enabled. 

Then modify `/conf/settings.ini` and insert your API key, secret, and passcode.



## Running

**Usage**

```
$ python main.py --help
usage: main.py [-h] --symbol SYMBOL --size SIZE --type TYPE [--interval INTERVAL] [--split SPLIT]

optional arguments:
  -h, --help           show this help message and exit
  --symbol SYMBOL      Market Symbol (e.g., BTC/USD, ETH/USD)
  --size SIZE          The decimal value of the percentage that the stop loss should be placed above or below current price (e.g., 0.05, 0.10)
  --type TYPE          Specify whether the trailing stop loss should be in buying or selling mode. (e.g., 'buy' or 'sell')
  --interval INTERVAL  How often the bot should check for price changes
  --split SPLIT        How many trading pairs should we allocate our funds between? (e.g., if ETH/USD and BTC/USD simultaneously: 2, if ETH/USD only: 1
```
```
$ python3 main.py --symbol BTC/USD --size 0.05 --type sell
```


**Important note**

If you are running in sell mode, it is assumed that you have already purchased the coins. If you are running in buy mode, it will use the total available balance in the base (USDT, BTC, etc).


## Parameters

**--type buy**

If the **buy** option is set, the bot will initially place a stop-loss (100 * `size`)% **above** the current market price (e.g., (100 * 0.05 = 5%)). As the price goes lower, the stop-loss will get dragged with it, staying no higher than the size specified. Once the price crosses the stop-loss price, a buy order is executed.

**--type sell**

If the **sell** option is set, the bot will initially place a stop-loss (100 * `size`)% **below** the current market price (e.g., (100 * 0.05 = 5%)). As the price goes higher, the stop-loss will get dragged with it, staying no lower than the size specified. Once the price crosses the stop-loss price, a sell order is executed.

**--size**

This is the percentage difference you would like the stop-loss to be retained at. The difference between the current price and stop-loss will never be larger than this amount.

## Overview

### Sell Mode
Allows user to create an exit strategy including:
1. Exit price (e.g., $600)
2. Amount of coins to release at exit price (e.g., 0.5 ETH)

| Exit Price | Amount (ETH) |
|-----|------|
| 600 | 0.25 |
| 775 | 0.25 |
| 925 | 0.50 |
| 1080 | 1.0 |
| 1250 | 1.5 |

The bot will track the current price against the defined thresholds and release coins to be sold as thresholds are met. As new thresholds are hit, the bot will automatically increment a "hopper" to track the appropriate amount of coins to sell based on the defined exit strategy. When the market price drops below an established stop loss value, the bot will sell only the amount of coins that have been released into the hopper (i.e., those marked "available to sell"). 

![image](https://user-images.githubusercontent.com/13890717/113211258-1c89b280-922a-11eb-866d-2a9d3c10a292.png)


### Buy Mode

In 'buy-mode', the bot will actively monitor the market price around a defined range that is initialized upon the deposit of USD funds to the account. The bot will execute a strategy around this "range" that consists of three modes: 

1. If the market price rises X% above the deposit price it will execute a market buy order. 
2. If the market price ranges between the higher and lower bound (X% above and X% below deposit price), no action is taken.
3. If the market price drops X% below the deposit price, it will initialize a stoploss at the deposit price and continue to lower the stoploss upon each new price low observed. Once a stoploss has been initialized the bot will execute a market buy order if the current market price exceeds the stoploss. 

![image](https://user-images.githubusercontent.com/13890717/113211108-e1877f00-9229-11eb-971b-35af02e8d68f.png)


## License
Released under GPLv3.
