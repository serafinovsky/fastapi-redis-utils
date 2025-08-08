# Usage Guide

## BaseRepository with Triple Schema Support

The `BaseRepository` now supports separate schemas for create, update, and result operations, providing better type safety and more flexible data handling.

### Basic Concept

Instead of using a single model for all operations, you can define:

1. **CreateSchemaType** - Model for creating new records (all required fields)
2. **UpdateSchemaType** - Model for updating existing records (all fields optional)
3. **ResultSchemaType** - Model for result operations (must inherit from BaseResultModel)

This approach provides:

- Better type safety
- Clear separation of concerns
- Partial update support
- More intuitive API design
- Flexible result model handling

### Example: User Management

```python
from typing import Optional
from pydantic import BaseModel
from fastapi_redis_utils import BaseRepository, RedisManager, BaseResultModel

# Schema for creating users
class UserCreate(BaseModel):
    username: str
    email: str
    full_name: str
    age: int
    is_active: bool = True

# Schema for updating users (all fields optional)
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    age: Optional[int] = None
    is_active: Optional[bool] = None

# Schema for result operations (inherits from BaseResultModel)
class UserResult(UserCreate, BaseResultModel):
    key: str | None = None

    def set_key(self, key: str) -> None:
        self.key = key


class UserRepository(BaseRepository[UserCreate, UserUpdate, UserResult]):
    def __init__(self, redis_manager: RedisManager):
        super().__init__(
            redis_manager=redis_manager,
            create_model=UserCreate,
            update_model=UserUpdate,
            result_model=UserResult,
            key_prefix="user:",
            default_ttl=3600
        )

# Usage
redis_manager = RedisManager(dsn="redis://localhost:6379")
user_repo = UserRepository(redis_manager)

# Create a new user
new_user = UserCreate(
    username="john_doe",
    email="john@example.com",
    full_name="John Doe",
    age=30
)
created_user = await user_repo.create("john_doe", new_user)

# Update user - only email and age
update_data = UserUpdate(
    email="john.updated@example.com",
    age=31
)
updated_user = await user_repo.update("john_doe", update_data)
# Result: only email and age are updated, other fields remain unchanged
```

### Partial Update Behavior

The `update` method performs partial updates:

```python
# Original user data
# username: "john_doe"
# email: "john@example.com"
# full_name: "John Doe"
# age: 30
# is_active: True

# Update with only some fields
update_data = UserUpdate(
    email="new@example.com",
    is_active=False
)

updated_user = await user_repo.update("john_doe", update_data)

# Result:
# username: "john_doe" (unchanged)
# email: "new@example.com" (updated)
# full_name: "John Doe" (unchanged)
# age: 30 (unchanged)
# is_active: False (updated)
```

### FastAPI Integration

```python
from fastapi import FastAPI, Depends
from typing import Optional

app = FastAPI()

# Repository setup
redis_manager = RedisManager(dsn="redis://localhost:6379")
user_repo = UserRepository(redis_manager)

@app.post("/users")
async def create_user(user: UserCreate):
    """Create a new user"""
    return await user_repo.create(user.username, user)

@app.get("/users/{username}")
async def get_user(username: str):
    """Get user by username"""
    return await user_repo.get(username)

@app.patch("/users/{username}")
async def update_user(username: str, user_update: UserUpdate):
    """Update user with partial update"""
    return await user_repo.update(username, user_update)

@app.delete("/users/{username}")
async def delete_user(username: str):
    """Delete user"""
    return await user_repo.delete(username)
```

### Benefits of Triple Schema Approach

1. **Type Safety**: Clear distinction between create, update, and result operations
2. **Partial Updates**: Only specified fields are updated
3. **API Clarity**: Different schemas for different operations
4. **Validation**: Separate validation rules for each schema
5. **Flexibility**: Update schema can have different field requirements
6. **Result Control**: Custom result models with additional fields or methods

### Best Practices

1. **Naming Convention**: Use `Create` and `Update` suffixes for clarity
2. **Optional Fields**: Make all fields in update schema optional
3. **Validation**: Add appropriate validation rules for each schema
4. **Documentation**: Document the purpose of each schema
5. **Testing**: Test both create and update operations separately

### Error Handling

The repository handles various error scenarios:

```python
# Non-existent key update
result = await user_repo.update("nonexistent", UserUpdate(email="test@example.com"))
assert result is None

# Invalid data serialization
try:
    await user_repo.create("test", invalid_data)
except ValueError as e:
    print(f"Serialization error: {e}")

# Invalid data deserialization
user = await user_repo.get("invalid_key")
assert user is None  # Returns None for deserialization errors
```
