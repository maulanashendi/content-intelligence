"""Canonical editorial taxonomy shared by `labeling` (writes) and `api` (reads).

Lives in `core` because batch modules never import each other; both the
labeling pipeline and the API need the same value sets.
"""

DESK_CATEGORIES: tuple[str, ...] = (
    "Politik",
    "Hukum",
    "Nasional",
    "Ekonomi & Bisnis",
    "Internasional",
    "Investigasi",
    "Sains & Teknologi",
    "Lingkungan",
    "Hiburan",
    "Olahraga",
    "Lifestyle",
    "Selebriti",
    "Otomotif",
    "Lainnya",
)

USER_NEED_CATEGORIES: tuple[str, ...] = (
    "Update me",
    "Keep me engaged",
    "Educate me",
    "Give me perspective",
    "Inspire me",
    "Divert me",
    "Help me",
    "Connect me",
)

_DESK_BY_FOLD = {d.casefold(): d for d in DESK_CATEGORIES}
_NEED_BY_FOLD = {n.casefold(): n for n in USER_NEED_CATEGORIES}


def normalize_desk(value: str | None) -> str | None:
    if not value:
        return None
    return _DESK_BY_FOLD.get(value.strip().casefold())


def normalize_user_need(value: str | None) -> str | None:
    if not value:
        return None
    return _NEED_BY_FOLD.get(value.strip().casefold())
