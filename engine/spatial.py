"""Floor adjacency, fragmentation scoring, and spatial seat assignment."""

from typing import Dict, List, Tuple
from models.building import Floor
from models.allocation import AllocationRecommendation, FloorAssignment
from config.defaults import (
    ADJACENCY_BONUS_SAME_FLOOR, ADJACENCY_BONUS_ADJACENT_FLOOR,
    ADJACENCY_BONUS_SAME_TOWER, ADJACENCY_BONUS_CROSS_TOWER,
    FRAGMENTATION_PENALTY_PER_FLOOR,
)


def compute_adjacency_tier(
    floor: Floor,
    existing_assignments: List[FloorAssignment],
    unit_name: str,
) -> Tuple[str, int]:
    """Determine adjacency tier and bonus for placing a unit on a floor."""
    unit_floors = [a for a in existing_assignments if a.unit_name == unit_name]

    if not unit_floors:
        return "new_placement", 0

    for a in unit_floors:
        if a.tower_id == floor.tower_id and a.floor_number == floor.floor_number:
            return "same_floor", ADJACENCY_BONUS_SAME_FLOOR

    for a in unit_floors:
        if a.tower_id == floor.tower_id and abs(a.floor_number - floor.floor_number) == 1:
            return "adjacent", ADJACENCY_BONUS_ADJACENT_FLOOR

    for a in unit_floors:
        if a.tower_id == floor.tower_id:
            return "same_tower", ADJACENCY_BONUS_SAME_TOWER

    return "cross_tower", ADJACENCY_BONUS_CROSS_TOWER


def score_floor_for_unit(
    floor: Floor,
    available_seats: int,
    existing_assignments: List[FloorAssignment],
    unit_name: str,
    floors_used_by_unit: int,
) -> float:
    """Score a candidate floor for placing a unit's seats."""
    if available_seats <= 0:
        return -999999

    _, adjacency_bonus = compute_adjacency_tier(floor, existing_assignments, unit_name)
    fragmentation_penalty = floors_used_by_unit * FRAGMENTATION_PENALTY_PER_FLOOR

    score = available_seats * 10 + adjacency_bonus - fragmentation_penalty
    return score


def assign_units_to_floors(
    allocations: List[AllocationRecommendation],
    floors: List[Floor],
    excluded_floor_ids: List[str] = None,
) -> Tuple[List[FloorAssignment], Dict[str, float]]:
    """Assign allocated seats to physical floors. Returns assignments and fragmentation scores."""
    excluded = set(excluded_floor_ids or [])
    assignments: List[FloorAssignment] = []
    floor_remaining: Dict[str, int] = {}

    for f in floors:
        if f.floor_id not in excluded:
            floor_remaining[f.floor_id] = f.total_seats

    floor_map = {f.floor_id: f for f in floors}

    # Sort units by allocated seats descending (place large units first)
    sorted_allocs = sorted(allocations, key=lambda a: a.allocated_seats, reverse=True)

    for alloc in sorted_allocs:
        seats_to_place = alloc.allocated_seats
        unit_name = alloc.unit_name

        while seats_to_place > 0:
            # Find best floor
            best_floor_id = None
            best_score = -999999

            unit_floor_ids = {a.tower_id + "-F" + str(a.floor_number)
                              for a in assignments if a.unit_name == unit_name}
            floors_used = len(unit_floor_ids)

            for fid, remaining in floor_remaining.items():
                if remaining <= 0:
                    continue
                f = floor_map[fid]
                s = score_floor_for_unit(f, remaining, assignments, unit_name, floors_used)
                if s > best_score:
                    best_score = s
                    best_floor_id = fid

            if best_floor_id is None:
                break  # No capacity left anywhere

            f = floor_map[best_floor_id]
            seats_on_floor = min(seats_to_place, floor_remaining[best_floor_id])

            tier, _ = compute_adjacency_tier(f, assignments, unit_name)

            assignments.append(FloorAssignment(
                unit_name=unit_name,
                building_id=f.building_id,
                tower_id=f.tower_id,
                floor_number=f.floor_number,
                seats_assigned=seats_on_floor,
                adjacency_tier=tier,
            ))

            floor_remaining[best_floor_id] -= seats_on_floor
            seats_to_place -= seats_on_floor

    # Compute fragmentation scores
    fragmentation_scores: Dict[str, float] = {}
    for alloc in allocations:
        unit_assignments = [a for a in assignments if a.unit_name == alloc.unit_name]
        floors_used = len(set((a.tower_id, a.floor_number) for a in unit_assignments))
        if alloc.allocated_seats == 0:
            fragmentation_scores[alloc.unit_name] = 0.0
        else:
            # Ideal: all seats on one floor. Max typical floor ~150 seats.
            ideal_floors = max(1, alloc.allocated_seats / 120)
            fragmentation_scores[alloc.unit_name] = min(1.0, (floors_used / ideal_floors - 1) / 3)

    # Update fragmentation scores on allocations
    for alloc in allocations:
        alloc.fragmentation_score = fragmentation_scores.get(alloc.unit_name, 0.0)

    return assignments, fragmentation_scores


def get_floor_utilization(
    floors: List[Floor],
    assignments: List[FloorAssignment],
) -> List[dict]:
    """Compute utilization stats per floor."""
    usage = {}
    for a in assignments:
        fid = f"{a.tower_id}-F{a.floor_number}"
        if fid not in usage:
            usage[fid] = {"units": {}, "total_used": 0}
        usage[fid]["units"][a.unit_name] = usage[fid]["units"].get(a.unit_name, 0) + a.seats_assigned
        usage[fid]["total_used"] += a.seats_assigned

    results = []
    for f in floors:
        fid = f.floor_id
        used = usage.get(fid, {}).get("total_used", 0)
        units = usage.get(fid, {}).get("units", {})
        results.append({
            "floor_id": fid,
            "building_id": f.building_id,
            "building_name": f.building_name,
            "tower_id": f.tower_id,
            "floor_number": f.floor_number,
            "total_seats": f.total_seats,
            "used_seats": used,
            "available_seats": f.total_seats - used,
            "utilization_pct": used / f.total_seats if f.total_seats > 0 else 0,
            "unit_count": len(units),
            "units": units,
        })
    return results


def get_consolidation_suggestions(
    allocations: List[AllocationRecommendation],
    assignments: List[FloorAssignment],
    fragmentation_scores: Dict[str, float],
) -> List[str]:
    """Generate consolidation suggestions for fragmented units."""
    suggestions = []
    for alloc in allocations:
        if fragmentation_scores.get(alloc.unit_name, 0) > 0.5:
            unit_floors = [(a.tower_id, a.floor_number, a.seats_assigned)
                           for a in assignments if a.unit_name == alloc.unit_name]
            unit_floors.sort(key=lambda x: x[2])  # Sort by seats ascending
            if len(unit_floors) >= 2:
                smallest = unit_floors[0]
                largest = unit_floors[-1]
                suggestions.append(
                    f"{alloc.unit_name}: Consider moving {smallest[2]} seats from "
                    f"{smallest[0]}-F{smallest[1]} to {largest[0]}-F{largest[1]} "
                    f"to reduce fragmentation (score: {fragmentation_scores[alloc.unit_name]:.2f})"
                )
    return suggestions
