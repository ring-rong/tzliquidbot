from aiogram import Router

from app.handlers.confirm import router as confirm_router
from app.handlers.fallback import router as fallback_router
from app.handlers.start import router as start_router
from app.handlers.survey import router as survey_router

router = Router(name="root")
router.include_router(start_router)
router.include_router(survey_router)
router.include_router(confirm_router)
# Ловит всё, что не подошло выше — обязательно последним, иначе перехватит
# сообщения/колбэки, для которых есть более специфичный хендлер.
router.include_router(fallback_router)
