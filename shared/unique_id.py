import uuid

def generate_unique_id(data):
    """Генерує ID і перевіряє унікальність в пам'яті"""
    max_attempts = 10
    for _ in range(max_attempts):
        user_id = str(uuid.uuid4())

        # Перевіряємо чи немає користувача з таким ID
        user_exists = any(example['id'] == user_id for example in data)
        if not user_exists:
            return user_id
            
    raise Exception("Cannot generate unique ID")