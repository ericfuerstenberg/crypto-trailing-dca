import ccxt

# To Do:
# 1. Modify to use ccxt to connect to CoinbasePro (https://github.com/ccxt/ccxt/blob/master/python/ccxt/coinbasepro.py)

class CoinbasePro(): # CoinbasePro

    def __init__(self, api_key, api_secret, password):
        self.ccxtClient = ccxt.coinbasepro({ # ccxt.coinbasepro()
            'apiKey': api_key,
            'secret': api_secret, # verify that you only need these two credentials - maybe need password too?
            'password': password
        })

        # set sandbox mode
        self.ccxtClient.set_sandbox_mode(True)

    def buy(self, market, amount, price):
        return (self.ccxtClient.create_order(
            symbol=market,
            type="limit",
            side="buy",
            amount=amount,
            price=price,
        ))

    def sell(self, market, amount):
        return (self.ccxtClient.create_order(
            symbol=market,
            type="market",
            side="sell",
            amount=amount
        ))

    def get_price(self, market):
        return float(self.ccxtClient.fetch_ticker(market)['info']['price'])

    def get_balance(self, coin):
        return float(self.ccxtClient.fetch_balance()[coin]['free'])
