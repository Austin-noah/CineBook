"""
Intelligent adjacent seat selection logic for cinema booking.
Supports both standard 5x8 grid (A1-E8) and multi-section cinema rows.
"""

# Standard 5-row x 8-column layout (40 seats)
STANDARD_ROWS = {
    "A": [f"A{c}" for c in range(1, 9)],
    "B": [f"B{c}" for c in range(1, 9)],
    "C": [f"C{c}" for c in range(1, 9)],
    "D": [f"D{c}" for c in range(1, 9)],
    "E": [f"E{c}" for c in range(1, 9)],
}

STANDARD_SEATS = [seat for row in STANDARD_ROWS.values() for seat in row]


def find_row_for_seat(seat, custom_rows=None):
    """
    Identifies the ordered row sequence containing the specified seat.
    """
    if custom_rows:
        for row in custom_rows:
            if seat in row:
                return list(row)
    # Check standard 5x8 grid
    row_letter = seat[:1].upper()
    if row_letter in STANDARD_ROWS and seat in STANDARD_ROWS[row_letter]:
        return list(STANDARD_ROWS[row_letter])
    return None


def select_adjacent_seats(row_seats, selected_seat, requested_count, booked_seats=None):
    """
    Selects adjacent contiguous seats in the given row.

    Rules:
    1. Primary preference: select `selected_seat` and up to `requested_count - 1`
       seats immediately to its right in the same row.
    2. Never select a booked seat.
    3. Never exceed the grid / row boundary.
    4. Never skip over an occupied seat to select one beyond it.
    5. Fallback: if the right block is unavailable, search for another valid contiguous
       block of `requested_count` seats in the same row, prioritizing blocks that
       include the selected seat (shifted left) or contiguous blocks closest to it.
    6. If no contiguous block exists in this row, returns None to allow manual selection.
    """
    if requested_count <= 0 or not row_seats or selected_seat not in row_seats:
        return []

    booked = set(booked_seats or ())
    if selected_seat in booked:
        return []

    row = list(row_seats)
    total_in_row = len(row)
    idx = row.index(selected_seat)

    if requested_count > total_in_row:
        return None

    # Step 1: Preferred block: [idx ... idx + requested_count - 1] to the right
    if idx + requested_count <= total_in_row:
        candidate = row[idx : idx + requested_count]
        if not any(s in booked for s in candidate):
            return candidate

    # Step 2: Search for another contiguous block in the same row.
    # Prioritize blocks that still include the selected seat (shifting start index leftwards)
    # e.g., if user picked B3 and requested 3 tickets, but B5 is booked or boundary hit:
    # try start=idx-1 [B2, B3, B4], then start=idx-2 [B1, B2, B3].
    possible_starts = []

    # Shifts including selected_seat:
    for shift in range(1, requested_count):
        start = idx - shift
        if start >= 0 and start + requested_count <= total_in_row:
            possible_starts.append(start)

    # Other starts in the row, ordered by proximity to idx
    other_starts = [
        s for s in range(total_in_row - requested_count + 1)
        if s not in possible_starts and s != idx
    ]
    other_starts.sort(key=lambda s: abs(s - idx))
    all_candidate_starts = possible_starts + other_starts

    for start in all_candidate_starts:
        block = row[start : start + requested_count]
        if not any(s in booked for s in block):
            return block

    # No contiguous block of requested_count available in this row
    return None
