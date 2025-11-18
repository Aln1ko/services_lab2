from fastapi import APIRouter, HTTPException
from datetime import datetime
import requests
from typing import List
from shared.rabbitmq import publish_notification_async

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
    try:
        await publish_notification_async(
            user_id=board_data.admin_user_id,
            notification_type="board_created",
            subject="board_created",
            message=f"User {board_data.admin_user_id}, created board with id {new_board.id}"
        )
    except Exception as e:
        print(f"Failed to publish create board notification: {e}")

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

    try:
        await publish_notification_async(
            user_id=board.admin_user_id,
            notification_type="board_updated",
            subject="board_updated",
            message=f"Board {board.id}, updated"
        )
    except Exception as e:
        print(f"Failed to publish update board notification: {e}")
    
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

    try:
        await publish_notification_async(
            user_id=board.admin_user_id,
            notification_type="board_archived",
            subject = "board_archived",
            message = f"Board {board.id} archived"
        )
    except Exception as e:
        print(f"Failed to publish archive board notification: {e}")
    
    
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

    try:
        await publish_notification_async(
            user_id=board.admin_user_id,
            notification_type="board_restored",
            subject = "board_restored",
            message = f"Board {board.id} restored"
        )
    except Exception as e:
        print(f"Failed to publish restore board notification: {e}")
    
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
    
    try:
        await publish_notification_async(
            user_id=board.admin_user_id,
            notification_type="board_deleted",
            subject = "board_deleted",
            message = f"Board {board.id} deleted"
        )
    except Exception as e:
        print(f"Failed to publish delete board notification: {e}")
    
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
    
    try:
        await publish_notification_async(
            user_id=invite_data.invited_user_id,
            notification_type="invitation_sent",
            subject = "invitation_sent",
            message = f"Invitation to board {invite_data.board_id} send to {invite_data.invited_user_id}"
        )
    except Exception as e:
        print(f"Failed to publish invite user to board notification: {e}")

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
    
    try:
        await publish_notification_async(
            user_id=join_data.user_id,
            notification_type="user_joined",
            subject = "user_joined",
            message = f"user {join_data.user_id} joined to board{join_data.board_id}"
        )
    except Exception as e:
        print(f"Failed to publish join user to board notification: {e}")

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
    
    try:
        await publish_notification_async(
            user_id = role_data.target_user_id,
            notification_type="user_role_changed",
            subject = "user_role_changed",
            message = f"user  {role_data.target_user_id} changed role to {role_data.new_role}"
        )
    except Exception as e:
        print(f"Failed to publish change role to board notification: {e}")

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
    
    try:
        await publish_notification_async(
            user_id = remove_data.target_user_id,
            notification_type="user_removed",
            subject = "user_removed",
            message = f"user  {remove_data.target_user_id} deleted from board {remove_data.board_id}"
        )
    except Exception as e:
        print(f"Failed to publish user remove notification: {e}")
    
    return {"message": "User removed from board successfully"}

@router.get("/boards/{board_id}/users", response_model=List[BoardUserResponse])
async def get_board_users_endpoint(board_id: str):
    board = find_board_by_id(board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    users_data = get_board_users(board_id)
    return [BoardUserResponse(**user) for user in users_data]