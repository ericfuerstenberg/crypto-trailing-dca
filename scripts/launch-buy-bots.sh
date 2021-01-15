#! /bin/bash

## ETH
cd /home/efuerstenberg/eric-eth-buy/src
rm exit_strategy.db && python3 create-db.py
nohup python3 main.py --symbol ETH/USD --size .03 --type buy --split 2 &


## BTC
cd /home/efuerstenberg/eric-btc-buy/src
rm exit_strategy.db && python3 create-db.py
nohup python3 main.py --symbol BTC/USD --size .02 --type buy --split 2 &