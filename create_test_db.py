import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    user="postgres",
    password="postgres123",
    database="postgres"
)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname = 'accounting_test'")
if not cur.fetchone():
    cur.execute("CREATE DATABASE accounting_test")
    print("Created accounting_test database")
else:
    print("accounting_test already exists")
cur.close()
conn.close()
