"""CRUD helpers for saved comic panels."""

from __future__ import annotations

import json

from library.db import Panel, session


def create(*, title: str, image_path: str, compose: dict | None = None) -> Panel:
    with session() as s:
        panel = Panel(
            title=title,
            image_path=image_path,
            compose_json=json.dumps(compose or {}),
        )
        s.add(panel)
        s.commit()
        s.refresh(panel)
        return panel


def list_all() -> list[Panel]:
    with session() as s:
        return list(s.query(Panel).order_by(Panel.created_at.desc()).all())


def delete(panel_id: int) -> bool:
    with session() as s:
        panel = s.get(Panel, panel_id)
        if not panel:
            return False
        s.delete(panel)
        s.commit()
        return True
