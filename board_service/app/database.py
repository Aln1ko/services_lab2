from datetime import datetime
import uuid
from shared.unique_id import generate_unique_id
from app.api.models import UserRole

# Тимчасова база даних в пам'яті
boards_db = []
BOARD_LIMIT_PER_USER = 10  # Ліміт дошок на користувача

def create_board(name:str, admin_id:str):
    user_boards = [ b for b in boards_db if b["admin_user_id"] == admin_id]
    if len(user_boards) >= BOARD_LIMIT_PER_USER:
        raise Exception("Board limit reached")
    
    board_id = generate_unique_id(boards_db)

    board = {
        "id":board_id,
        "name": name,
        "admin_user_id": admin_id,
        "users": [admin_id],  
        "status": "active",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }

    boards_db.append(board)
    return board

def find_board_by_id(board_id: str):
    for index, board in enumerate(boards_db):
        if board["id"] == board_id:
            return board,index
    return None,-1

def find_boards_by_user(user_id: str):
    return [b for b in boards_db if user_id in b["users"]]

def update_board(board_id:str,updates:dict):
    board = find_board_by_id(board_id)
    if board:
        for key,value in updates.items():
            if value is not None:
                board[key] = value
            board["updated_at"] = datetime.now()
    return board



USER_LIMIT_PER_BOARD = 20  # Ліміт користувачів на дошці

def is_user_admin(board_id: str, user_id: str) -> bool:
    """Перевіряє чи є користувач адміністратором дошки"""
    board = find_board_by_id(board_id)
    if not board:
        return False
    return board["admin_user_id"] == user_id

def add_user_to_board(board_id: str, user_id: str, role: UserRole = UserRole.MEMBER):
    """Додає користувача до дошки"""
    board = find_board_by_id(board_id)
    if not board:
        raise Exception("Board not found")
    
    # Перевірка ліміту користувачів
    if len(board["users"]) >= USER_LIMIT_PER_BOARD:
        raise Exception("User limit reached for this board")
    
    # Перевірка чи вже є користувач на дошці
    if user_id in board["users"]:
        raise Exception("User already on board")
    
    # Додаємо користувача
    board["users"].append(user_id)
    
    # Зберігаємо роль (в реальному додатку - окрема таблиця)
    if "user_roles" not in board:
        board["user_roles"] = {}
    board["user_roles"][user_id] = role
    
    # Додаємо час приєднання
    if "joined_at" not in board:
        board["joined_at"] = {}
    board["joined_at"][user_id] = datetime.now()
    
    board["updated_at"] = datetime.now()
    return board

def remove_user_from_board(board_id: str, user_id: str):
    """Видаляє користувача з дошки"""
    board = find_board_by_id(board_id)
    if not board:
        raise Exception("Board not found")
    
    if user_id not in board["users"]:
        raise Exception("User not on board")
    
    # Не можна видалити адміністратора
    if board["admin_user_id"] == user_id:
        raise Exception("Cannot remove board admin")
    
    # Видаляємо користувача
    board["users"].remove(user_id)
    
    # Видаляємо додаткові дані
    if "user_roles" in board and user_id in board["user_roles"]:
        del board["user_roles"][user_id]
    if "joined_at" in board and user_id in board["joined_at"]:
        del board["joined_at"][user_id]
    
    board["updated_at"] = datetime.now()
    return board

def update_user_role(board_id: str, user_id: str, new_role: UserRole):
    """Оновлює роль користувача на дошці"""
    board = find_board_by_id(board_id)
    if not board:
        raise Exception("Board not found")
    
    if user_id not in board["users"]:
        raise Exception("User not on board")
    
    if "user_roles" not in board:
        board["user_roles"] = {}
    
    board["user_roles"][user_id] = new_role
    board["updated_at"] = datetime.now()
    return board

def get_board_users(board_id: str):
    """Повертає список користувачів дошки з ролями"""
    board = find_board_by_id(board_id)
    if not board:
        return []
    
    users = []
    for user_id in board["users"]:
        role = board.get("user_roles", {}).get(user_id, UserRole.MEMBER)
        joined_at = board.get("joined_at", {}).get(user_id, board["created_at"])
        
        users.append({
            "user_id": user_id,
            "role": role,
            "joined_at": joined_at
        })
    
    return users