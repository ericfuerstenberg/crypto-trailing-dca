#! /bin/bash

## ETH
rsync -av /home/efuerstenberg/crypto-bot/src/ /home/efuerstenberg/eric-eth-buy/src/ --exclude=exit_strategy.db

## BTC
rsync -av /home/efuerstenberg/crypto-bot/src/ /home/efuerstenberg/eric-btc-buy/src/ --exclude=exit_strategy.db