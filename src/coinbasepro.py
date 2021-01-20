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

    # def buy(self, market, amount, price):
    #     return (self.ccxtClient.create_order(
    #         symbol=market,
    #         type="market", 
    #         side="buy",
    #         amount=amount,
    #         price=price,
    #     ))

    def buy(self, market, funds):
        return (self.ccxtClient.create_order(
            symbol=market,
            type="market", 
            side="buy",
            amount=0,
            params = {
                "funds": funds
            }
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

    def get_order(self, id):
        return (self.ccxtClient.fetch_order(
            id=id
        ))

    def get_payment_methods(self):
        return (self.ccxtClient.fetch_payment_methods())

    def deposit_funds(self, payment_method_id, deposit_amount, currency):
        return (self.ccxtClient.deposit(
            amount = deposit_amount,
            code = currency,
            address = 'None',
            params = {
                'payment_method_id': payment_method_id
            }
        ))

    def fetch_deposits(self):
        return (self.ccxtClient.fetch_deposits())
