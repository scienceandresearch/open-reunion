"""Ground movement's single-destination wave search and first-step selection."""
from ..core import GameError


def ground_path_direction(board, start, target):
    """0xD324..0xD8C1 with both destination arguments equal, as in a frame.

    Return 0 to stand still, or 1/2/3/4 for left/up/right/down. Occupied
    destinations use the closest reachable cell. Search order and backtracking
    priorities are significant: replacing them with generic A* changes moves.
    The input board is sixteen columns of nine occupancy codes and is unchanged.
    """
    inside = lambda cell: 0 <= cell[0] < 16 and 0 <= cell[1] < 9
    if len(board) != 16 or any(len(column) != 9 for column in board):
        raise GameError("A ground battlefield must have sixteen columns and nine rows.")
    if not inside(start) or not inside(target):
        raise GameError("Ground path endpoints must be on the battlefield.")
    start, target = tuple(start), tuple(target)
    distance = lambda cell: abs(cell[0]-target[0])+abs(cell[1]-target[1])
    labels = [[255 if value else 0 for value in column] for column in board]
    labels[start[0]][start[1]] = 1
    if labels[target[0]][target[1]] == 0:labels[target[0]][target[1]] = 254
    frontier = [start];depth = 1;best = None;best_distance = 1000;found = None
    while frontier and found is None:
        depth += 1;following = []
        for cx, cy in reversed(frontier):
            if found is not None:break
            for neighbor in ((cx-1, cy), (cx+1, cy), (cx, cy-1), (cx, cy+1)):
                if not inside(neighbor):continue
                nx, ny = neighbor;label = labels[nx][ny]
                if label == 254:found = neighbor;best_distance = 0
                elif label == 0:
                    following.append(neighbor);labels[nx][ny] = depth
                    if distance(neighbor) < best_distance:
                        best, best_distance = neighbor, distance(neighbor)
        frontier = following
    endpoint = found if found is not None else best
    if endpoint is None or distance(start) <= best_distance:return 0
    cx, cy = endpoint
    if abs(start[0]-cx) >= abs(start[1]-cy):steps = ((0, 1), (0, -1), (1, 0), (-1, 0))
    else:steps = ((1, 0), (-1, 0), (0, 1), (0, -1))
    while depth > 2:
        for dx, dy in steps:
            neighbor = (cx+dx, cy+dy)
            if inside(neighbor) and 0 < labels[neighbor[0]][neighbor[1]] < depth:
                cx, cy = neighbor;depth = labels[cx][cy];break
        else:raise GameError("Ground path has no decreasing route to its origin.")
    direction = 0
    if cx == start[0]+1:direction = 3
    if cy == start[1]+1:direction = 4
    if cx == start[0]-1:direction = 1
    if cy == start[1]-1:direction = 2
    return direction
