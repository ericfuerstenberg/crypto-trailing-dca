import ccxt
import time
from datetime import datetime, timedelta
from coinbasepro import CoinbasePro
from helper import get_logger, send_sns, Config

logger = get_logger('deposit')

coinbasepro = CoinbasePro(
    api_key = Config.get_value('deposit', 'deposit_api_key'),
    api_secret = Config.get_value('deposit', 'deposit_api_secret'),
    password = Config.get_value('deposit', 'deposit_password')
)

payment_method_id = Config.get_value('deposit', 'payment_method_id')
deposit_amount = Config.get_value('deposit', 'deposit_amount')
currency = Config.get_value('deposit', 'currency')

try:
    deposit = coinbasepro.deposit_funds(payment_method_id, deposit_amount, currency)
    message = 'Deposit successful: $%s' % deposit_amount
    logger.warning(message)
    send_sns(message)

except ccxt.NetworkError as e:
    time.sleep(5)
    deposit_lookup = coinbasepro.fetch_deposits()
    timestamp = deposit_lookup[-1]['info']['created_at'][:-3]
    timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
    difference = datetime.now() - timestamp
    if difference < timedelta(minutes=5):
        message = 'Deposit successful: $%s' % deposit_lookup['info']['amount']
        logger.warning(message)
        send_sns(message)
    else:
        message = 'Deposit failed: %s' % e
        logger.exception(message)
        send_sns(message)

except Exception as e:
    message = 'Deposit failed: %s' % e
    logger.exception(message)
    send_sns(message)