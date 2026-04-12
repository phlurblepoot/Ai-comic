"""CRUD helpers for saved scenes."""

from __future__ import annotations

from library.db import Scene, session


def create(
    *,
    name: str,
    description: str = "",
    image_path: str = "",
    depth_map_path: str = "",
) -> Scene:
    with session() as s:
        existing = s.query(Scene).filter_by(name=name).one_or_none()
        if existing:
            existing.description = description
            existing.image_path = image_path
            existing.depth_map_path = depth_map_path
            s.commit()
            s.refresh(existing)
            return existing
        scene = Scene(
            name=name,
            description=description,
            image_path=image_path,
            depth_map_path=depth_map_path,
        )
        s.add(scene)
        s.commit()
        s.refresh(scene)
        return scene


def list_all() -> list[Scene]:
    with session() as s:
        return list(s.query(Scene).order_by(Scene.name).all())


def get(scene_id: int) -> Scene | None:
    with session() as s:
        return s.get(Scene, scene_id)


def delete(scene_id: int) -> bool:
    with session() as s:
        scene = s.get(Scene, scene_id)
        if not scene:
            return False
        s.delete(scene)
        s.commit()
        return True
