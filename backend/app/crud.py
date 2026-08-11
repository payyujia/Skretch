from sqlalchemy.orm import Session

from . import models

BOARD_ID = "default"  # single-board MVP; swap for a real id once multi-board lands


def get_board(db: Session, board_id: str = BOARD_ID):
    return db.query(models.Node).filter_by(board_id=board_id).all()


def get_node(db: Session, node_id: str):
    return db.get(models.Node, node_id)


def create_node(db: Session, content: str = "", x: float = 0, y: float = 0,
                 created_by: str = "user", type: str = "sticky", data: dict | None = None,
                 parent_id: str | None = None, board_id: str = BOARD_ID):
    node = models.Node(
        content=content, x=x, y=y, created_by=created_by,
        type=type, data=data or {}, parent_id=parent_id, board_id=board_id,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def update_node(db: Session, node_id: str, set_parent_id: bool = False, **fields):
    """`set_parent_id=True` is required to touch parent_id — that's the only
    field where "not provided" and "explicitly set to null" mean different
    things (leave the frame membership alone vs. pop the node out of its
    frame), so it can't use the same "skip if None" rule as every other field.
    """
    node = get_node(db, node_id)
    if not node:
        return None
    parent_id = fields.pop("parent_id", None)
    for key, value in fields.items():
        if value is not None:
            setattr(node, key, value)
    if set_parent_id:
        node.parent_id = parent_id
    db.commit()
    db.refresh(node)
    return node


def delete_node(db: Session, node_id: str) -> bool:
    node = get_node(db, node_id)
    if not node:
        return False
    # Deleting a frame shouldn't take its contents down with it — orphan any
    # children back to the top level instead of cascading the delete.
    db.query(models.Node).filter(models.Node.parent_id == node_id).update(
        {"parent_id": None}, synchronize_session=False
    )
    db.delete(node)
    db.commit()
    return True