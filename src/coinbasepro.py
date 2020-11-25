import ccxt

class CoinbasePro():

    def __init__(self, api_key, api_secret, password):
        self.ccxtClient = ccxt.coinbasepro({
            'apiKey': api_key,
            'secret': api_secret,
            'password': password
        })

        # set sandbox mode
        self.ccxtClient.set_sandbox_mode(True)

    def buy(self, market, amount, price):
        return (self.ccxtClient.create_order(
            symbol=market,
            type="market", #maybe I can use 'funds' here to pass the total balance? how does this work on ccxt's end
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
