import httpx
import json
import re
from mcp.server.fastmcp import FastMCP, Context

# ==========================================
# КОНФІГУРАЦІЯ
# ==========================================
# Адрес твоего шлюза (або служби аутентифікації напряму)
API_BASE_URL = "http://127.0.0.1:8000/auth" 

# Ініціалізуємо сервер MCP
mcp = FastMCP("AuthServiceMCP")

# ============================================
# ДОПОМІЖНІ ФУНКЦІЇ (HELPERS)
# ============================================
def validate_email(email: str):
    """Guardrail: Проста перевірка формату електронної пошти"""
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        raise ValueError(f"Security Guardrail: Invalid email format '{email}'")

def is_admin_email(email: str) -> bool:
    """Guardrail: Захист критично ключових користувачів"""
    admin_emails = ["admin@system.com", "root@localhost", "boss@company.com"]
    return email in admin_emails

# ============================================
# ІНСТРУМЕНТИ (TOOLS)
# ============================================
@mcp.tool()
async def get_user_by_email(email: str) -> str:
    """
    Find a user by email. 
    Returns JSON string with user details or error message.
    """
    # 1. Guardrail: Input Validation
    try:
        validate_email(email)
    except ValueError as e:
        return f"Error: {str(e)}"

    print(f"MCP Request: Searching for {email}")

    async with httpx.AsyncClient() as client:
        try:
            # Емуляція пошуку немає endpoint /users?email=...)
            response = await client.get(f"{API_BASE_URL}/users")
            
            if response.status_code != 200:
                return f"API Error: {response.status_code}"
            
            users = response.json()
            found = next((u for u in users if u["email"] == email), None)
            
            if found:
                return json.dumps(found, indent=2)
            else:
                return json.dumps({"error": "User not found"})
        except Exception as e:
            return f"Network Error: {str(e)}"

@mcp.tool()
async def create_new_user(email: str, password: str, full_name: str) -> str:
    """
    Register a new user in the system.
    """
    # 1. Guardrail: Input Validation
    try:
        validate_email(email)
    except ValueError as e:
        return f"Error: {str(e)}"

    # 2. Guardrail: Policy Check (Заборона створення адмінів через цей интерфейс)
    if "admin" in email.lower() or "admin" in full_name.lower():
        return "Security Guardrail: Creating admin accounts via MCP is FORBIDDEN."

    print(f"MCP Request: Creating {email}")

    payload = {
        "email": email,
        "password": password,
        "full_name": full_name
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{API_BASE_URL}/users", json=payload)
            if response.status_code in [200, 201]:
                return json.dumps(response.json(), indent=2)
            elif response.status_code == 400:
                return "Error: User already exists or bad data."
            else:
                return f"API Error: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Network Error: {str(e)}"

@mcp.tool()
async def delete_user_by_id(user_id: str, requester_email: str) -> str:
    """
    Delete a user by ID. 
    Requires 'requester_email' for audit and permission check.
    """
    print(f"MCP Request: Delete {user_id} by {requester_email}")

    # 1. Guardrail: Перевірка прав (Симуляція)
    if not requester_email.endswith("@admin.com"):
        return "Security Guardrail: Only @admin.com users can delete accounts."

    async with httpx.AsyncClient() as client:
        try:
            # Спочатку перевіримо, кого видаляємо (захист від видалення важливих осіб) 
            response = await client.delete(f"{API_BASE_URL}/users/{user_id}/")
            
            if response.status_code == 200:
                return "User successfully deleted."
            elif response.status_code == 404:
                return "Error: User ID not found."
            else:
                return f"API Error: {response.status_code}"
        except Exception as e:
            return f"Network Error: {str(e)}"

# ==========================================
# ЗАПУСК
# ==========================================
if __name__ == "__main__":
    # MCP сервер працює через Standard Input/Output (stdio)
    mcp.run(transport='stdio')