
# Для бекенду (обмін токена)
KEYCLOAK_INTERNAL_URL = "http://keycloak:8080/realms/KpiRealm/protocol/openid-connect" 

# Для браузера (редирект на логін)
KEYCLOAK_EXTERNAL_URL = "http://localhost:8080/realms/KpiRealm/protocol/openid-connect"

# ID  клієнта (створений у Keycloak)
CLIENT_ID = "web-client"

# Секрет, отриманий із вкладки Credentials клієнта 'web-client' у Keycloak
CLIENT_SECRET = "nt4vbW89ek0UYBj79LCwC429BH6QQDqg"

# Адреса, на яку Keycloak поверне код.
# Він повинен збігатися з "Valid redirect URIs" у налаштуваннях клієнта Keycloak
REDIRECT_URI = "http://localhost:8000/auth/callback"