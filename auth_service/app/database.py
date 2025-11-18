import uuid
from datetime import datetime

test_id = str(uuid.uuid4())

users_db = [
    {
        'id':test_id,
        'email':'something@gmail.com',
        'password':'a123bk',
        'full_name':'Oleksandr',
        'created_at':datetime.now()
    }
]

outbox_db = []

sessions_db = {}