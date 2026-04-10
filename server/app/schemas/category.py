from pydantic import BaseModel
from typing import List


class CategoryBase(BaseModel):
    name: str
    description: str | None = None
    color: str = "#6366F1"


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    is_active: bool | None = None


class CategoryResponse(CategoryBase):
    id: int
    user_id: int
    is_system: bool
    is_active: bool

    class Config:
        from_attributes = True


class CategoryListResponse(List[CategoryResponse]):
    pass
