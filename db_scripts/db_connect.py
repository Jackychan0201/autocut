import os
import logging
from dotenv import load_dotenv
import psycopg2

load_dotenv()

DB_USER = os.getenv('POSTGRES_USER')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD')
DB_NAME = os.getenv('POSTGRES_DB')
DB_HOST = os.getenv('POSTGRES_HOST')
DB_PORT = os.getenv('POSTGRES_PORT')

def db_conn():
    # If we are running locally (outside Docker), 'db' won't resolve.
    # We try the configured host first, then fallback to localhost.
    hosts_to_try = [DB_HOST]
    if DB_HOST != 'localhost' and DB_HOST != '127.0.0.1':
        hosts_to_try.append('localhost')

    for host in hosts_to_try:
        try:
            conn = psycopg2.connect(dbname=DB_NAME,
                                    user=DB_USER,
                                    password=DB_PASSWORD,
                                    host=host,
                                    port=DB_PORT,
                                    connect_timeout=3
                                    )
            return conn
        except Exception:
            continue
    
    print(f"Unable to connect to PostgreSQL on any of {hosts_to_try}")
    return None