"""Starter node layouts used when a board is created from a template."""
TEMPLATES = {
    "blank": [],
    "kanban": [
        {"type": "frame", "content": "Backlog, clear next", "x": 100, "y": 85, "data": {"color": "yellow", "width": 400, "height": 650}},
        {"type": "sticky", "content": "Oh sleep! it is a gentle thing, Beloved from pole to pole! To Mary Queen the praise be given! She sent the gentle sleep from Heaven, That slid into my soul.", "x": 140, "y": 203, "parent_index": 0, "data": {"color": "yellow", "reactions": {}, "rotation": -1}},
        
        {"type": "frame", "content": "In Progress, clear urgently", "x": 550, "y": 85, "data": {"color": "coral", "width": 400, "height": 650}},
        {"type": "sticky", "content": "On the fifteenth of May, in the jungle of Nool, In the heat of the day, in the cool of the pool", "x": 589, "y": 221, "parent_index": 2, "data": {"color": "coral", "reactions": {}, "rotation": 1}},
        {"type": "sticky", "content": "O happy living things! no tongue Their beauty might declare: A spring of love gushed from my heart, And I blessed them unaware", "x": 701, "y": 393, "parent_index": 2, "data": {"color": "coral", "reactions": {}, "rotation": 0}},
        
        {"type": "frame", "content": "Done, and dusted", "x": 1000, "y": 85, "data": {"color": "mint", "width": 400, "height": 650}},
        {"type": "sticky", "content": "Awesome work you've just finished", "x": 1027, "y": 199, "parent_index": 5, "data": {"color": "purple", "reactions": {}, "rotation": 1}},
    ],
    "okr": [
        {"type": "frame", "content": "Objective", "x": 100, "y": 80, "data": {"color": "coral", "width": 960, "height": 230}},
        {"type": "sticky", "content": "Make the team's work more focused", "x": 140, "y": 150, "parent_index": 0, "data": {"color": "coral", "reactions": {}}},
        {"type": "frame", "content": "Key results", "x": 100, "y": 340, "data": {"color": "blue", "width": 960, "height": 300}},
        {"type": "sticky", "content": "KR1: Ship the top 3 priorities on time", "x": 140, "y": 420, "parent_index": 2, "data": {"color": "blue", "reactions": {}}},
        {"type": "sticky", "content": "KR2: Reach 80% weekly active usage", "x": 440, "y": 420, "parent_index": 2, "data": {"color": "mint", "reactions": {}}},
        {"type": "sticky", "content": "KR3: Cut cycle time by 20%", "x": 740, "y": 420, "parent_index": 2, "data": {"color": "yellow", "reactions": {}}},
    ],
    "retrospective": [
        {"type": "frame", "content": "Start, what should we try next?", "x": 100, "y": 85, "data": {"color": "yellow", "width": 410, "height": 700}},
        {"type": "sticky", "content": "Host cross-functional listening previews early to align engineering, design, and marketing ahead of launch.", "x": 140, "y": 200, "parent_index": 0, "data": {"color": "yellow", "reactions": {}, "rotation": -1}},
        {"type": "sticky", "content": "Establish collaborative reviews of listener feature data early to prevent misaligned assumptions.", "x": 228, "y": 400, "parent_index": 0, "data": {"color": "yellow", "reactions": {}, "rotation": 0}},
        {"type": "sticky", "content": "Run targeted user sentiment surveys to validate shareable card formats before finalizing templates.", "x": 124, "y": 595, "parent_index": 0, "data": {"color": "yellow", "reactions": {}, "rotation": 1}},
        
        {"type": "frame", "content": "Stop, what's veering from our objectives", "x": 550, "y": 85, "data": {"color": "coral", "width": 410, "height": 700}},
        {"type": "sticky", "content": "Run targeted user sentiment surveys to validate shareable card formats before finalizing templates.", "x": 589, "y": 200, "parent_index": 4, "data": {"color": "coral", "reactions": {}, "rotation": 1}},
        {"type": "sticky", "content": "Avoid adding overly complex custom animations that compromise mobile performance and QA speed.", "x": 701, "y": 400, "parent_index": 4, "data": {"color": "coral", "reactions": {}, "rotation": 0}},
        {"type": "sticky", "content": "Eliminate risky localization changes during final release week to prevent truncated UI text.", "x": 566, "y": 595, "parent_index": 4, "data": {"color": "coral", "reactions": {}, "rotation": 1}},
        
        {"type": "frame", "content": "Continue, we'll keep these features", "x": 1000, "y": 85, "data": {"color": "mint", "width": 410, "height": 700}},
        {"type": "sticky", "content": "Scale core data ingestion pipelines successfully under peak traffic without service interruptions", "x": 1027, "y": 200, "parent_index": 8, "data": {"color": "mint", "reactions": {}, "rotation": 0}},
        {"type": "sticky", "content": "Maintain exceptional visual storytelling, art direction to drive organic social media traction", "x": 1134, "y": 400, "parent_index": 8, "data": {"color": "mint", "reactions": {}, "rotation": -1}},
        {"type": "sticky", "content": "Robust automated sharing tests to prevent regressions across social media platforms", "x": 1023, "y": 595, "parent_index": 8, "data": {"color": "mint", "reactions": {}, "rotation": 1}},
    ],
}



def get_template_nodes(template: str) -> list[dict]:
    """Return a fresh node list so creation cannot mutate the catalog."""
    if template not in TEMPLATES:
        raise ValueError(f"Unknown board template: {template}")
    return [node.copy() | {"data": node["data"].copy()} for node in TEMPLATES[template]]