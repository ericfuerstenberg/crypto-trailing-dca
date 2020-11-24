import sqlite3 as sl


#set up the sqlite database here? use it instead of the pandas dataframe
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
        CREATE TABLE stoploss (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            stop_value REAL
        );
    """)

thresholds = 'INSERT INTO thresholds (id, price, amount, threshold_hit, sold_at) values (?, ?, ?, ?, ?)'
data1 = [
    (1, 19200, 0.05, 'N', None),
    (2, 19210, 0.05, 'N', None),
    (3, 19900, 0.05, 'N', None),
    (4, 21000, 0.05, 'N', None)
]

hopper = 'INSERT INTO hopper (id, amount) values (?, ?)'
data2 = [
    (1, 0)
]

stoploss = 'INSERT INTO stoploss (id, stop_value) values (?, ?)'
data3 = [
    (1, None)
]

with con:
    con.executemany(thresholds, data1) 
    con.executemany(hopper, data2)
    con.executemany(stoploss, data3)