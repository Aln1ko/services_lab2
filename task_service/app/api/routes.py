from fastapi import APIRouter, HTTPException
from datetime import datetime
import requests
from typing import List

from app.api.models import (
    TaskCreate, TaskResponse, TaskUpdate, TaskStatus, TaskPriority,
    CommentCreate, CommentResponse, AssignRequest
)
from app.database import (
    tasks_db, comments_db, create_task, find_task_by_id, 
    find_tasks_by_board, update_task, add_comment, get_task_comments
)

router = APIRouter()

def verify_user_exists(user_id: str) -> bool:
    """Перевіряє чи існує користувач в auth-service"""
    try:
        response = requests.get(f"http://auth-service:8000/users/{user_id}")
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def verify_board_exists(board_id: str) -> bool:
    """Перевіряє чи існує дошка в board-service"""
    try:
        response = requests.get(f"http://board-service:8000/boards/{board_id}")
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

@router.post("/tasks", response_model=TaskResponse)
async def create_task_endpoint(task_data: TaskCreate):
    # Перевірка чи існує користувач
    if not verify_user_exists(task_data.created_by):
        raise HTTPException(status_code=404, detail="User not found")
    
    # Перевірка чи існує дошка
    if not verify_board_exists(task_data.board_id):
        raise HTTPException(status_code=404, detail="Board not found")
    
    # Створення завдання
    try:
        new_task = create_task(
            title=task_data.title,
            description=task_data.description,
            board_id=task_data.board_id,
            created_by=task_data.created_by
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    print(f"Task '{new_task['title']}' created by user: {task_data.created_by}")
    
    return TaskResponse(**new_task)

@router.get("/tasks/board/{board_id}", response_model=List[TaskResponse])
async def get_board_tasks(board_id: str):
    if not verify_board_exists(board_id):
        raise HTTPException(status_code=404, detail="Board not found")
    
    tasks = find_tasks_by_board(board_id)
    return [TaskResponse(**task) for task in tasks]

@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    task = find_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskResponse(**task)

@router.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task_endpoint(task_id: str, task_data: TaskUpdate):
    task = find_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Оновлюємо завдання
    updates = {}
    if task_data.title is not None:
        updates["title"] = task_data.title
    if task_data.description is not None:
        updates["description"] = task_data.description
    if task_data.status is not None:
        updates["status"] = task_data.status
    if task_data.priority is not None:
        updates["priority"] = task_data.priority
    if task_data.assignee_id is not None:
        updates["assignee_id"] = task_data.assignee_id
    if task_data.due_date is not None:
        updates["due_date"] = task_data.due_date
    
    updated_task = update_task(task_id, updates)
    
    print(f"Task '{task_id}' updated")
    
    # Якщо статус "done" - можна архівувати (асинхронно)
    if task_data.status == TaskStatus.DONE:
        print(f"Task '{task_id}' completed - ready for archiving")
    
    return TaskResponse(**updated_task)

@router.post("/tasks/{task_id}/assign")
async def assign_task(assign_data: AssignRequest):
    task = find_task_by_id(assign_data.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Перевірка чи призначаючий користувач існує
    if not verify_user_exists(assign_data.admin_user_id):
        raise HTTPException(status_code=404, detail="Admin user not found")
    
    # Перевірка чи призначений користувач існує
    if not verify_user_exists(assign_data.assignee_id):
        raise HTTPException(status_code=404, detail="Assignee user not found")
    
    # Оновлюємо призначення
    update_task(assign_data.task_id, {"assignee_id": assign_data.assignee_id})
    
    print(f"Task '{assign_data.task_id}' assigned to user: {assign_data.assignee_id}")
    
    # Тут буде асинхронний виклик до notification-service
    # await send_assignment_notification(assign_data.assignee_id, assign_data.task_id)
    
    return {"message": "Task assigned successfully"}

@router.post("/tasks/comments", response_model=CommentResponse)
async def add_comment_endpoint(comment_data: CommentCreate):
    # Перевірка чи завдання існує
    task = find_task_by_id(comment_data.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Перевірка чи користувач існує
    if not verify_user_exists(comment_data.user_id):
        raise HTTPException(status_code=404, detail="User not found")
    
    # Додаємо коментар
    new_comment = add_comment(
        task_id=comment_data.task_id,
        user_id=comment_data.user_id,
        text=comment_data.text
    )
    
    print(f"Comment added to task '{comment_data.task_id}' by user: {comment_data.user_id}")
    
    return CommentResponse(**new_comment)

@router.get("/tasks/{task_id}/comments", response_model=List[CommentResponse])
async def get_task_comments_endpoint(task_id: str):
    task = find_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    comments = get_task_comments(task_id)
    return [CommentResponse(**comment) for comment in comments]

@router.post("/tasks/{task_id}/archive")
async def archive_task(task_id: str):
    task = find_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
     # Перевірка чи завдання вже архівоване
    if task["status"] == "archived":
        raise HTTPException(status_code=400, detail="Task already archived")
    
    # Перевірка чи завдання завершене (тільки завершені можна архівувати)
    if task["status"] != TaskStatus.DONE:
        raise HTTPException(status_code=400, detail="Only completed tasks can be archived")
    
    # Архівуємо завдання
    update_task(task_id, {"status": "archived"})
    
    print(f"Task '{task_id}' archived")
    
    return {"message": "Task archived successfully"}

@router.post("/tasks/{task_id}/restore")
async def restore_task(task_id: str):
    task = find_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
   
    # Перевірка чи завдання архівоване
    if task["status"] != "archived":
        raise HTTPException(status_code=400, detail="Only archived tasks can be restored")
    
    # Відновлюємо завдання (статус TODO)
    update_task(task_id, {"status": "todo"})
    
    print(f"Task '{task_id}' restored")
    
    return {"message": "Task restored successfully"}

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    task = find_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Видаляємо завдання (в реальному додатку - м'яке видалення)
    global tasks_db
    tasks_db = [t for t in tasks_db if t["id"] != task_id]
    
    # Видаляємо коментарі до завдання
    global comments_db
    comments_db = [c for c in comments_db if c["task_id"] != task_id]
    
    print(f"Task '{task_id}' deleted")
    
    return {"message": "Task deleted successfully"}