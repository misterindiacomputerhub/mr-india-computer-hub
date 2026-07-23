import os
import database as db
from main import run_one_topic, OUTPUT_DIR

os.makedirs(OUTPUT_DIR, exist_ok=True)
db.init_db()
topics = db.next_topics(1)
if not topics:
    print("Content queue is empty")
else:
    result = run_one_topic(topics[0])
    print("RESULT:", result)
