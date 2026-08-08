from sqlalchemy.orm import Session

from . import models

BOARD_ID = "default"  # single-board MVP; swap for a real id once multi-board lands


def get_board(db: Session, board_id: str = BOARD_ID):
    nodes = db.query(models.Node).filter_by(board_id=board_id).all()
    edges = db.query(models.Edge).filter_by(board_id=board_id).all()
    return nodes, edges


def get_node(db: Session, node_id: str):
    return db.get(models.Node, node_id)


def create_node(db: Session, content: str, x: float, y: float,
                 created_by: str = "user", board_id: str = BOARD_ID):
    node = models.Node(content=content, x=x, y=y, created_by=created_by, board_id=board_id)
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def update_node(db: Session, node_id: str, **fields):
    node = get_node(db, node_id)
    if not node:
        return None
    for key, value in fields.items():
        if value is not None:
            setattr(node, key, value)
    db.commit()
    db.refresh(node)
    return node


def delete_node(db: Session, node_id: str) -> bool:
    node = get_node(db, node_id)
    if not node:
        return False
    db.query(models.Edge).filter(
        (models.Edge.source_id == node_id) | (models.Edge.target_id == node_id)
    ).delete(synchronize_session=False)
    db.delete(node)
    db.commit()
    return True


def create_edge(db: Session, source_id: str, target_id: str, board_id: str = BOARD_ID):
    edge = models.Edge(source_id=source_id, target_id=target_id, board_id=board_id)
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return edge


def delete_edge(db: Session, edge_id: str) -> bool:
    edge = db.get(models.Edge, edge_id)
    if not edge:
        return False
    db.delete(edge)
    db.commit()
    return True
