from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.user import User
from app.models.category import Category
from app.schemas.category import CategoryResponse, CategoryCreate, CategoryUpdate, CategoryListResponse
from app.api.dependencies import get_current_user_dep

router = APIRouter()

DEFAULT_CATEGORIES = [
    {"name": "Primary", "description": "Primary inbox", "color": "#6366F1", "is_system": True},
    {"name": "Social", "description": "Social media notifications", "color": "#10B981", "is_system": True},
    {"name": "Promotions", "description": "Marketing and promotional emails", "color": "#F59E0B", "is_system": True},
    {"name": "Updates", "description": "News and updates", "color": "#8B5CF6", "is_system": True},
    {"name": "Personal", "description": "Personal emails", "color": "#EC4899", "is_system": True},
]


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Category).where(Category.user_id == current_user.id, Category.is_active == True)
    )
    categories = result.scalars().all()
    
    if not categories:
        for cat_data in DEFAULT_CATEGORIES:
            category = Category(user_id=current_user.id, **cat_data)
            db.add(category)
        await db.commit()
        
        result = await db.execute(
            select(Category).where(Category.user_id == current_user.id)
        )
        categories = result.scalars().all()
    
    return [CategoryResponse.model_validate(c) for c in categories]


@router.post("", response_model=CategoryResponse)
async def create_category(
    category_data: CategoryCreate,
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    category = Category(user_id=current_user.id, **category_data.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    
    return CategoryResponse.model_validate(category)


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: int,
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Category).where(
            Category.id == category_id,
            Category.user_id == current_user.id
        )
    )
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    return CategoryResponse.model_validate(category)


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category_update: CategoryUpdate,
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Category).where(
            Category.id == category_id,
            Category.user_id == current_user.id
        )
    )
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    if category.is_system:
        raise HTTPException(status_code=400, detail="Cannot modify system category")
    
    update_data = category_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)
    
    await db.commit()
    await db.refresh(category)
    
    return CategoryResponse.model_validate(category)


@router.delete("/{category_id}")
async def delete_category(
    category_id: int,
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Category).where(
            Category.id == category_id,
            Category.user_id == current_user.id
        )
    )
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    if category.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system category")
    
    category.is_active = False
    await db.commit()
    
    return {"message": "Category deleted"}
