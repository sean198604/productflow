from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.customers import router as customers_router
from app.api.v1.field_definitions import router as field_definitions_router
from app.api.v1.generation import router as generation_router
from app.api.v1.health import router as health_router
from app.api.v1.imports import router as imports_router
from app.api.v1.output_templates import router as output_templates_router
from app.api.v1.product_sets import router as product_sets_router
from app.api.v1.products import router as products_router
from app.api.v1.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(health_router, prefix="/api/v1", include_in_schema=False)
api_router.include_router(auth_router, prefix="/api/v1")
api_router.include_router(customers_router, prefix="/api/v1")
api_router.include_router(admin_router, prefix="/api/v1")
api_router.include_router(users_router, prefix="/api/v1")
api_router.include_router(field_definitions_router, prefix="/api/v1")
api_router.include_router(generation_router, prefix="/api/v1")
api_router.include_router(products_router, prefix="/api/v1")
api_router.include_router(product_sets_router, prefix="/api/v1")
api_router.include_router(imports_router, prefix="/api/v1")
api_router.include_router(output_templates_router, prefix="/api/v1")
