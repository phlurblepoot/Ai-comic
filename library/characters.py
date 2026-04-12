"""CRUD helpers for saved characters."""

from __future__ import annotations

from library.db import Character, session


def create(
    *,
    name: str,
    description: str = "",
    height_cm: float = 170.0,
    sheet_path: str = "",
    seed: int | None = None,
) -> Character:
    with session() as s:
        existing = s.query(Character).filter_by(name=name).one_or_none()
        if existing:
            # Overwrite on save-with-same-name so re-rolls replace the old entry.
            existing.description = description
            existing.height_cm = height_cm
            existing.sheet_path = sheet_path
            existing.seed = seed
            s.commit()
            s.refresh(existing)
            return existing
        character = Character(
            name=name,
            description=description,
            height_cm=height_cm,
            sheet_path=sheet_path,
            seed=seed,
        )
        s.add(character)
        s.commit()
        s.refresh(character)
        return character


def list_all() -> list[Character]:
    with session() as s:
        return list(s.query(Character).order_by(Character.name).all())


def get(character_id: int) -> Character | None:
    with session() as s:
        return s.get(Character, character_id)


def get_by_name(name: str) -> Character | None:
    with session() as s:
        return s.query(Character).filter_by(name=name).one_or_none()


def delete(character_id: int) -> bool:
    with session() as s:
        character = s.get(Character, character_id)
        if not character:
            return False
        s.delete(character)
        s.commit()
        return True
