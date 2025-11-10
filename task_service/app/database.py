from datetime import datetime, timedelta
import uuid
from shared.unique_id import generate_unique_id

# Тимчасова база даних в пам'яті
tasks_db = []
comments_db = []
TASK_LIMIT_PER_BOARD = 100

def create_task(title: str, description: str, board_id: str, created_by: str):
    # Перевірка ліміту завдань на дошці
    board_tasks = [t for t in tasks_db if t["board_id"] == board_id and t["status"] != "archived"]
    if len(board_tasks) >= TASK_LIMIT_PER_BOARD:
        raise Exception("Task limit reached for this board")
    
    task_id = generate_unique_id(tasks_db)
    
    task = {
        "id": task_id,
        "title": title,
        "description": description,
        "board_id": board_id,
        "status": "todo",
        "priority": "medium",
        "assignee_id": None,
        "created_by": created_by,
        "due_date": None,
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    
    tasks_db.append(task)
    return task

def find_task_by_id(task_id: str):
    for task in tasks_db:
        if task["id"] == task_id:
            return task
    return None

def find_tasks_by_board(board_id: str):
    return [t for t in tasks_db if t["board_id"] == board_id and t["status"] != "archived"]

def update_task(task_id: str, updates: dict):
    task = find_task_by_id(task_id)
    if task:
        for key, value in updates.items():
            if value is not None:
                task[key] = value
        task["updated_at"] = datetime.now()
    return task

def add_comment(task_id: str, user_id: str, text: str):
    comment_id = generate_unique_id(comments_db)
    
    comment = {
        "id": comment_id,
        "task_id": task_id,
        "user_id": user_id,
        "text": text,
        "created_at": datetime.now()
    }
    
    comments_db.append(comment)
    return comment

def get_task_comments(task_id: str):
    return [c for c in comments_db if c["task_id"] == task_id]