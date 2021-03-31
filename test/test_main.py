from test_trail import StopTrail
import argparse

def main(options):

    if options.type not in ['buy', 'sell']:
        print("Error: Please use valid trail type (Ex: 'buy' or 'sell')")
        return

    task = StopTrail(options.symbol, options.type, options.size, options.interval, options.split)
    task.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', type=str, help='Market Symbol (Ex: NEO/BTC - NEO/USDT)', required=True)
    parser.add_argument('--size', type=float, help='How many satoshis (or USD) the stop loss should be placed above or below current price', required=True)
    parser.add_argument('--type', type=str, help="Specify whether the trailing stop loss should be in buying or selling mode. (Ex: 'buy' or 'sell')", required=True)
    parser.add_argument('--interval', type=float, help="How often the bot should check for price changes", default=5)
    parser.add_argument('--split', type=int, help="How many trading pairs should we allocate our funds between? (e.g., if ETH/USD and BTC/USD simultaneously: 2, if ETH/USD only: 1", default=1)

    options = parser.parse_args()
    main(options)

