"""
Generates two raw CSVs with deliberately seeded data quality problems:
customers_raw.csv, orders_raw.csv

Problems injected:
- missing values
- duplicate records
- invalid dates
- incorrect data types
- incomplete records (missing columns / ragged rows)
"""
import csv
import random
from datetime import datetime, timedelta
from faker import Faker

random.seed(42)
fake = Faker()
Faker.seed(42)

N_CUSTOMERS = 200
N_ORDERS = 800

# ---------------- customers ----------------
customers = []
for i in range(1, N_CUSTOMERS + 1):
    customers.append({
        "customer_id": i,
        "name": fake.name(),
        "email": fake.email(),
        "signup_date": fake.date_between(start_date="-3y", end_date="today").isoformat(),
        "country": fake.country(),
    })

# inject missing values (email/name blanks)
for row in random.sample(customers, 15):
    row["email"] = ""
for row in random.sample(customers, 8):
    row["name"] = ""

# inject invalid dates
for row in random.sample(customers, 6):
    row["signup_date"] = random.choice(["2025-13-40", "not_a_date", "31/02/2024", ""])

# inject duplicate records (exact dupes of existing rows)
dupes = random.sample(customers, 10)
customers.extend(dupes)

# incorrect data types (customer_id as text / float where int expected)
for row in random.sample(customers, 5):
    row["customer_id"] = f"CUST_{row['customer_id']}"

random.shuffle(customers)

with open("/home/claude/dq-platform/data/raw/customers_raw.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["customer_id", "name", "email", "signup_date", "country"])
    w.writeheader()
    w.writerows(customers)

# ---------------- orders ----------------
valid_customer_ids = list(range(1, N_CUSTOMERS + 1))
statuses = ["completed", "pending", "cancelled", "refunded"]

orders = []
for i in range(1, N_ORDERS + 1):
    order_date = fake.date_between(start_date="-1y", end_date="today")
    orders.append({
        "order_id": i,
        "customer_id": random.choice(valid_customer_ids),
        "order_date": order_date.isoformat(),
        "amount": round(random.uniform(5, 500), 2),
        "status": random.choice(statuses),
    })

# missing values (amount / status blanks)
for row in random.sample(orders, 40):
    row["amount"] = ""
for row in random.sample(orders, 25):
    row["status"] = ""

# invalid dates
for row in random.sample(orders, 20):
    row["order_date"] = random.choice(["2024-02-30", "0000-00-00", "13/45/2023", "N/A"])

# incorrect data types (amount as text, negative amounts)
for row in random.sample(orders, 15):
    row["amount"] = random.choice(["free", "N/A", "$45.00"])
for row in random.sample(orders, 10):
    row["amount"] = -abs(round(random.uniform(5, 100), 2))

# orphan records - customer_id that doesn't exist in customers table
for row in random.sample(orders, 12):
    row["customer_id"] = random.randint(9000, 9999)

# duplicate records
dupes = random.sample(orders, 30)
orders.extend(dupes)

random.shuffle(orders)

with open("/home/claude/dq-platform/data/raw/orders_raw.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["order_id", "customer_id", "order_date", "amount", "status"])
    w.writeheader()
    w.writerows(orders)

# incomplete records - append a few ragged rows directly (missing trailing columns)
with open("/home/claude/dq-platform/data/raw/orders_raw.csv", "a", newline="") as f:
    f.write("9001,15,2024-05-01\n")          # missing amount, status
    f.write("9002,,,\n")                     # missing customer_id, date, amount
    f.write("9003,22,2024-06-10,150.00\n")   # missing status

print(f"Generated {len(customers)} customer rows, {len(orders)+3} order rows")
