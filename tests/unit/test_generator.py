from collections import Counter

import pytest

from lesson_recommender.dataset.generator import GeneratorConfig, generate
from lesson_recommender.dataset.io import dataset_from_dict, dataset_to_dict
from lesson_recommender.domain.models import Dataset
from lesson_recommender.domain.rules import level_fits

SMALL = GeneratorConfig(seed=7, lessons=30, students=60, weeks=12)


@pytest.fixture(scope="module")
def small() -> Dataset:
    return generate(SMALL)


def test_same_seed_same_dataset(small: Dataset) -> None:
    assert generate(SMALL) == small


def test_different_seed_changes_dataset(small: Dataset) -> None:
    other = generate(GeneratorConfig(seed=8, lessons=30, students=60, weeks=12))
    assert other.bookings != small.bookings


def test_sizes_follow_config(small: Dataset) -> None:
    assert len(small.lessons) == 30
    assert len(small.students) == 60
    assert len(small.bookings) > len(small.students)


def test_students_only_book_lessons_allowed_by_rules(small: Dataset) -> None:
    lessons = {lesson.id: lesson for lesson in small.lessons}
    students = {student.id: student for student in small.students}
    for booking in small.bookings:
        student, lesson = students[booking.student_id], lessons[booking.lesson_id]
        assert level_fits(student.level, lesson.level)
        assert not student.restrictions & lesson.contraindications


def test_every_lesson_references_existing_entities(small: Dataset) -> None:
    modalities = {m.id for m in small.modalities}
    instructors = {i.id for i in small.instructors}
    for lesson in small.lessons:
        assert lesson.modality_id in modalities
        assert lesson.instructor_id in instructors


def test_ratings_exist_only_for_booked_pairs(small: Dataset) -> None:
    booked = {(b.student_id, b.lesson_id) for b in small.bookings}
    assert small.ratings
    assert all((r.student_id, r.lesson_id) in booked for r in small.ratings)
    assert Counter((r.student_id, r.lesson_id) for r in small.ratings).most_common(1)[0][1] == 1


def test_students_discover_lessons_over_time(small: Dataset) -> None:
    # Padrão plantado: o conjunto de aulas conhecidas cresce, então há descobertas tardias.
    first_seen: dict[tuple[str, str], int] = {}
    for index, booking in enumerate(small.bookings):
        first_seen.setdefault((booking.student_id, booking.lesson_id), index)
    late = [i for i in first_seen.values() if i > len(small.bookings) * 0.8]
    assert late


def test_json_roundtrip_is_lossless(small: Dataset) -> None:
    assert dataset_from_dict(dataset_to_dict(small)) == small


def test_unknown_schema_version_is_rejected(small: Dataset) -> None:
    data = dataset_to_dict(small)
    data["schema_version"] = 99
    with pytest.raises(ValueError, match="schema"):
        dataset_from_dict(data)
