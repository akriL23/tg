from aiogram import Router
from .user import router as user_router
from .registration import router as registration_router
from .group import router as group_router
from .assignment import router as assignment_router

router = Router()
router.include_router(user_router)
router.include_router(registration_router)
router.include_router(group_router)
router.include_router(assignment_router)

def setup_handlers(dp):
    dp.include_router(router)