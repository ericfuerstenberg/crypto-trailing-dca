import sqlite3 as sl


#set up the sqlite database here? use it instead of the pandas dataframe
con = sl.connect('exit_strategy.db')
with con:
    con.execute("""
        CREATE TABLE thresholds (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            price INTEGER,
            amount INTEGER
        );
    """)

    con.execute("""
        CREATE TABLE hopper (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            amount INTEGER
        );
    """)

prices = 'INSERT INTO thresholds (id, price, amount) values(?, ?, ?)'
data1 = [
    (1, 17949, 0.05),
    (2, 17990, 0.09),
    (3, 18079, 0.1)
]

hopper = 'INSERT INTO hopper (id, amount) values (?, ?)'
data2 = [
    (1, 0)
]

with con:
    con.executemany(prices, data1) 
    con.executemany(hopper, data2)