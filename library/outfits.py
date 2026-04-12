"""CRUD helpers for saved outfits."""

from __future__ import annotations

from library.db import Outfit, session


def create(*, name: str, description: str = "", ref_image_path: str = "", tags: str = "") -> Outfit:
    with session() as s:
        existing = s.query(Outfit).filter_by(name=name).one_or_none()
        if existing:
            existing.description = description
            existing.ref_image_path = ref_image_path
            existing.tags = tags
            s.commit()
            s.refresh(existing)
            return existing
        outfit = Outfit(name=name, description=description, ref_image_path=ref_image_path, tags=tags)
        s.add(outfit)
        s.commit()
        s.refresh(outfit)
        return outfit


def list_all() -> list[Outfit]:
    with session() as s:
        return list(s.query(Outfit).order_by(Outfit.name).all())


def get(outfit_id: int) -> Outfit | None:
    with session() as s:
        return s.get(Outfit, outfit_id)


def delete(outfit_id: int) -> bool:
    with session() as s:
        outfit = s.get(Outfit, outfit_id)
        if not outfit:
            return False
        s.delete(outfit)
        s.commit()
        return True
