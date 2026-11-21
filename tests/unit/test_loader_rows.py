from dataclasses import replace

from lesson_recommender.graph.loader import booking_rows, rating_rows
from tests.factories import rating, studio


def test_bookings_are_aggregated_per_student_and_lesson() -> None:
    rows = {(r["student_id"], r["lesson_id"]): r for r in booking_rows(studio())}
    ana = rows[("ana", "y1")]
    assert ana["count"] == 2
    assert ana["first_at"] < ana["last_at"]
    assert len(rows) == 5


def test_only_latest_rating_is_kept() -> None:
    dataset = studio()
    data = replace(dataset, ratings=(rating("bia", "y2", 1, day=40), *dataset.ratings))
    [row] = rating_rows(data)
    assert row["score"] == 1
