# app/api/router.py
from fastapi import APIRouter
from .v1 import router as router_v1
from .v2 import router as router_v2

router = APIRouter()

router.include_router(router_v1, prefix="/v1")
router.include_router(router_v2, prefix="/v2")

router.include_router(router_v1)