from fastapi import APIRouter, HTTPException
from datetime import datetime
import requests
from typing import List

from app.api.models import (BoardCreate, Board, BoardUpdate, BoardStatus,
    UserInviteRequest, UserJoinRequest, UserRoleUpdate, 
    UserRemoveRequest, BoardUserResponse, UserRole
)
from app.database import (boards_db, create_board, find_board_by_id, find_boards_by_user, update_board,
                          is_user_admin,add_user_to_board,update_user_role,remove_user_from_board,get_board_users)

router = APIRouter()

# Синхронний виклик до auth-service для перевірки користувача
def verify_user_exists(user_id: str) -> bool:
    try:
        # Виклик до auth-service (синхронна комунікація)
        response = requests.get(f"http://auth-service:8000/users/{user_id}")
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False
    
@router.post("/boards", response_model=Board)
async def create_board_endpoint(board_data: BoardCreate):
    # Перевірка чи існує адміністратор
    if not verify_user_exists(board_data.admin_user_id):
        raise HTTPException(status_code=404, detail="Admin user not found")
    
    # Створення дошки
    try:
        new_board = create_board(
            name=board_data.name,
            admin_user_id=board_data.admin_user_id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    print(f"Board '{new_board['name']}' created by user: {board_data.admin_user_id}")
    
    return Board(**new_board)

@router.get("/boards/users/{user_id}", response_model=List[Board])
async def get_user_boards(user_id: str):
    if not verify_user_exists(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    
    boards = find_boards_by_user(user_id)
    return [Board(**board) for board in boards]

@router.get("/boards/{board_id}", response_model=Board)
async def get_board(board_id: str):
    board,index = find_board_by_id(board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    return Board(**board)

@router.put("/boards/{board_id}", response_model=Board)
async def update_board_endpoint(board_id: str, board_data: BoardUpdate):
    board,index = find_board_by_id(board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    # Оновлюємо дошку
    updates = {}
    if board_data.name is not None:
        updates["name"] = board_data.name
    if board_data.status is not None:
        updates["status"] = board_data.status
    
    updated_board = update_board(board_id, updates)
    
    print(f"Board '{board_id}' updated")
    
    return Board(**updated_board)

@router.post("/boards/{board_id}/archive")
async def archive_board(board_id: str):
    board,index = find_board_by_id(board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    if board["status"] == BoardStatus.ARCHIVED:
        raise HTTPException(status_code=400, detail="Board already archived")
    
    # Архівуємо дошку
    update_board(board_id, {"status": BoardStatus.ARCHIVED})
    
    print(f"Board '{board_id}' archived")
    
    # Тут буде асинхронний виклик до notification-service
    # await notify_users(board["users"], "board_archived", board_id)
    
    return {"message": "Board archived successfully"}

@router.post("/boards/{board_id}/restore")
async def restore_board(board_id: str):
    board,index = find_board_by_id(board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    if board["status"] != BoardStatus.ARCHIVED:
        raise HTTPException(status_code=400, detail="Board is not archived")
    
    # Відновлюємо дошку
    update_board(board_id, {"status": BoardStatus.ACTIVE})
    
    print(f"Board '{board_id}' restored from archive")
    
    return {"message": "Board restored successfully"}

@router.delete("/boards/{board_id}")
async def delete_board(board_id: str):
    board,index = find_board_by_id(board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    # "М'яке" видалення - міняємо статус
    # update_board(board_id, {"status": BoardStatus.DELETED})
    del boards_db[index]
    print(f"Board '{board_id}' deleted (soft delete)")
    
    # Тут буде асинхронний виклик до notification-service
    # await notify_users(board["users"], "board_deleted", board_id)
    
    return {"message": "Board deleted successfully"}



@router.post("/boards/invite")
async def invite_user_to_board(invite_data: UserInviteRequest):
    # Перевірка чи адміністратор існує
    if not verify_user_exists(invite_data.admin_user_id):
        raise HTTPException(status_code=404, detail="Admin user not found")
    
    # Перевірка чи запрошений користувач існує
    if not verify_user_exists(invite_data.invited_user_id):
        raise HTTPException(status_code=404, detail="Invited user not found")
    
    # Перевірка прав адміністратора
    if not is_user_admin(invite_data.board_id, invite_data.admin_user_id):
        raise HTTPException(status_code=403, detail="Only board admin can invite users")
    
    # Додаємо користувача до дошки
    try:
        updated_board = add_user_to_board(
            board_id=invite_data.board_id,
            user_id=invite_data.invited_user_id,
            role=UserRole.MEMBER
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    print(f"User {invite_data.invited_user_id} invited to board {invite_data.board_id}")
    
    # Тут буде асинхронний виклик до notification-service
    # await send_invitation_notification(invite_data.invited_user_id, invite_data.board_id)
    
    return {"message": "User invited successfully"}

@router.post("/boards/join")
async def join_board(join_data: UserJoinRequest):
    # Перевірка чи користувач існує
    if not verify_user_exists(join_data.user_id):
        raise HTTPException(status_code=404, detail="User not found")
    
    # Додаємо користувача до дошки
    try:
        updated_board = add_user_to_board(
            board_id=join_data.board_id,
            user_id=join_data.user_id,
            role=UserRole.MEMBER
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    print(f"User {join_data.user_id} joined board {join_data.board_id}")
    
    # Тут буде асинхронний виклик до notification-service
    # await notify_board_users(join_data.board_id, "user_joined", join_data.user_id)
    
    return {"message": "Joined board successfully"}

@router.put("/boards/users/role")
async def update_user_role_endpoint(role_data: UserRoleUpdate):
    # Перевірка прав адміністратора
    if not is_user_admin(role_data.board_id, role_data.admin_user_id):
        raise HTTPException(status_code=403, detail="Only board admin can change roles")
    
    # Оновлюємо роль
    try:
        updated_board = update_user_role(
            board_id=role_data.board_id,
            user_id=role_data.target_user_id,
            new_role=role_data.new_role
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    print(f"User {role_data.target_user_id} role changed to {role_data.new_role} on board {role_data.board_id}")
    
    return {"message": "User role updated successfully"}

@router.delete("/boards/users/remove")
async def remove_user_from_board_endpoint(remove_data: UserRemoveRequest):
    # Перевірка прав адміністратора
    if not is_user_admin(remove_data.board_id, remove_data.admin_user_id):
        raise HTTPException(status_code=403, detail="Only board admin can remove users")
    
    # Видаляємо користувача
    try:
        updated_board = remove_user_from_board(
            board_id=remove_data.board_id,
            user_id=remove_data.target_user_id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    print(f"User {remove_data.target_user_id} removed from board {remove_data.board_id}")
    
    # Тут буде асинхронний виклик до notification-service
    # await send_removal_notification(remove_data.target_user_id, remove_data.board_id)
    
    return {"message": "User removed from board successfully"}

@router.get("/boards/{board_id}/users", response_model=List[BoardUserResponse])
async def get_board_users_endpoint(board_id: str):
    board = find_board_by_id(board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    users_data = get_board_users(board_id)
    return [BoardUserResponse(**user) for user in users_data]