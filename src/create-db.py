import sqlite3 as sl

con = sl.connect('exit_strategy.db')
with con:
    con.execute("""
        CREATE TABLE thresholds (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            price INTEGER,
            amount INTEGER,
            threshold_hit STRING,
            sold_at REAL
        );
    """)

    con.execute("""
        CREATE TABLE hopper (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            amount INTEGER
        );
    """)

    con.execute("""
        CREATE TABLE available_funds (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            account_balance INTEGER,
            coin_hopper INTEGER
        );
    """)   

    con.execute("""
        CREATE TABLE stoploss (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            stop_value REAL
        );
    """)

    con.execute("""
        CREATE TABLE win_tracker (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            price_at_deposit REAL,
            price_at_buy INTEGER,
            buy_count INTEGER,
            win_count INTEGER
        );
    """)  

thresholds = 'INSERT INTO thresholds (id, price, amount, threshold_hit, sold_at) values (?, ?, ?, ?, ?)'
data1 = [
    (1, 14200, 0.05, 'N', None),
    (2, 14900, 0.05, 'N', None),
    (3, 15500, 0.05, 'N', None),
    (4, 16500, 0.05, 'N', None)
]

hopper = 'INSERT INTO hopper (id, amount) values (?, ?)'
data2 = [
    (1, 0)
]

available_funds = 'INSERT INTO available_funds (id, account_balance, coin_hopper) values (?, ?, ?)'
data3= [
    (1, 0, 0)
]

stoploss = 'INSERT INTO stoploss (id, stop_value) values (?, ?)'
data4 = [
    (1, None)
]

win_tracker = 'INSERT INTO win_tracker (id, price_at_deposit, price_at_buy, buy_count, win_count) values (?, ?, ?, ?, ?)'
data5= [
    (1, None, None, 0, 0)
]

with con:
    con.executemany(thresholds, data1) 
    con.executemany(hopper, data2)
    con.executemany(available_funds, data3)
    con.executemany(stoploss, data4)
    con.executemany(win_tracker, data5)