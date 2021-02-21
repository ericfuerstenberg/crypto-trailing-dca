import sqlite3

class Database(object):
    """sqlite3 database class that holds testers jobs"""
    DB_LOCATION = "exit_strategy.db"

    def __init__(self):
        """Initialize db class variables"""
        self.connection = sqlite3.connect(Database.DB_LOCATION)
        self.cur = self.connection.cursor()

    def commit(self):
        """commit changes to database"""
        self.connection.commit()

    def close(self):
        """close sqlite3 connection"""
        self.connection.close()

	def terminate(self):
        self.commit()
        self.close()
        logger.info('Database closed')


    def execute(self, query):
        """execute a row of data to current cursor"""
        self.cur.execute(query)

    def execute_many(self, many_query):
        """add many new data to database in one go"""
        #self.create_table()
        self.cur.executemany('REPLACE INTO jobs VALUES(?, ?, ?, ?)', many_query)

    def get_stoploss(self):
        self.cur.execute("SELECT * FROM stoploss;")
        first_row = self.cur.fetchone()
        stop_value = first_row[1]
        return stop_value

    def get_hopper_amount(self):
        self.cur.execute("SELECT * FROM hopper;")
        first_row = self.cur.fetchone()
        hopper_amount = first_row[1]
        return hopper_amount