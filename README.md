# CoinbasePro Trailing Stop-Loss
Provides a dynamic stop-loss that automatically adjusts as the price increases or decreases (depending on mode specified).


## Sell Mode
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

## Buy Mode

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

Obtain an API key from CoinbasePro with 'view' and 'trade' permissions enabled. 

Then modify `/conf/settings.ini` and insert your API key, secret, and passcode.



## Running

**Usage**

```
$ python main.py --help
usage: main.py [-h] --symbol SYMBOL --size SIZE --type TYPE
               [--interval INTERVAL]

optional arguments:
  -h, --help           show this help message and exit
  --symbol SYMBOL      Market Symbol (Ex: NEO/BTC - NEO/USDT)
  --size SIZE          What percentage the stop loss should be
                       placed above or below current price (e.g., 0.05 for 5%, 0.10 for 10%)
  --type TYPE          Specify whether the trailing stop loss should be in
                       buying or selling mode. (Ex: 'buy' or 'sell')
  --interval INTERVAL  How often the bot should check for price changes (default 5 seconds)
```
```
$ python3 main.py --symbol BTC/USD --size 0.05 --type sell
```


**Important note**

If you are running in sell mode, it is assumed that you have already purchased the coins. If you are running in buy mode, it will use the total available balance in the base (USDT, BTC, etc).



## About the bot

**Buy mode**

If the **buy** option is set, the bot will initially place a stop-loss (100 * `size`) % **above** the current market price (e.g., (100 * 0.05 = 5%)). As the price goes lower, the stop-loss will get dragged with it, staying no higher than the size specified. Once the price crosses the stop-loss price, a buy order is executed.

**Sell mode**

If the **sell** option is set, the bot will initially place a stop-loss (100 * `size`) % **below** the current market price (e.g., (100 * 0.05 = 5%)). As the price goes higher, the stop-loss will get dragged with it, staying no lower than the size specified. Once the price crosses the stop-loss price, a sell order is executed.

**Size**

This is the percentage difference you would like the stop-loss to be retained at. The difference between the current price and stop-loss will never be larger than this amount.



## License
Released under GPLv3.
