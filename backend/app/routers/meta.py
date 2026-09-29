from fastapi import APIRouter

from app.models import CategoryInfo

router = APIRouter(prefix="/api", tags=["meta"])

CATEGORIES: list[CategoryInfo] = [
    CategoryInfo(id="admissions", label_en="Admissions", label_hi="प्रवेश", label_mr="प्रवेश"),
    CategoryInfo(id="fees", label_en="Fees & Accounts", label_hi="शुल्क एवं लेखा", label_mr="शुल्क आणि लेखा"),
    CategoryInfo(id="examinations", label_en="Examinations", label_hi="परीक्षा", label_mr="परीक्षा"),
    CategoryInfo(id="placements", label_en="Placements", label_hi="प्लेसमेंट", label_mr="नोकरी नियुक्ती"),
    CategoryInfo(id="hostel", label_en="Hostel & Campus", label_hi="छात्रावास एवं परिसर", label_mr="वसतिगृह आणि आवार"),
    CategoryInfo(id="notices", label_en="Notices & Announcements", label_hi="सूचनाएं", label_mr="सूचना"),
]


@router.get("/categories", response_model=list[CategoryInfo])
def get_categories() -> list[CategoryInfo]:
    return CATEGORIES


@router.get("/health")
def health_check() -> dict:
    return {"status": "ok", "rag_pipeline": "stub", "note": "Retrieval is running on a demo document set, not a live document repository."}
