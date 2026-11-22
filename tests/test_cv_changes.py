from app.models.cv_document import CVBullet, CVExperience, StructuredCV
from app.services.cv_changes import describe_changes, readable_tailoring_warning


def _cv(summary="Original summary.", bullets=("a", "b", "c", "d")) -> StructuredCV:
    return StructuredCV(
        name="Elçin Yıldız",
        summary=summary,
        experiences=[
            CVExperience(
                id="exp1", employer="Acme", title="Engineer",
                bullets=[CVBullet(id=f"exp1.b{i}", text=t) for i, t in enumerate(bullets, start=1)],
            ),
            CVExperience(
                id="exp2", employer="Beta", title="Analyst",
                bullets=[CVBullet(id="exp2.b1", text="x"), CVBullet(id="exp2.b2", text="y")],
            ),
        ],
    )


def _reordered(cv: StructuredCV, exp_id: str, order: list[str]) -> StructuredCV:
    exps = []
    for exp in cv.experiences:
        if exp.id == exp_id:
            by_id = {b.id: b for b in exp.bullets}
            exp = exp.model_copy(update={"bullets": [by_id[i] for i in order]})
        exps.append(exp)
    return cv.model_copy(update={"experiences": exps})


def test_identical_cvs_have_no_changes():
    cv = _cv()
    assert describe_changes(cv, cv.model_copy(deep=True)) == []


def test_moved_bullet_names_the_old_and_new_position():
    original = _cv()
    tailored = _reordered(original, "exp1", ["exp1.b3", "exp1.b1", "exp1.b2", "exp1.b4"])

    (change,) = describe_changes(original, tailored)

    assert change.kind == "moved"
    assert change.id == "exp1.b3"
    assert change.where == "Engineer — Acme"
    assert change.after == "c"
    assert change.detail == "Moved from 3rd to 1st"


def test_only_the_furthest_move_per_role_is_reported():
    original = _cv()
    tailored = _reordered(original, "exp1", ["exp1.b4", "exp1.b3", "exp1.b1", "exp1.b2"])
    moves = [c for c in describe_changes(original, tailored) if c.kind == "moved"]
    assert [m.id for m in moves] == ["exp1.b4"]
    assert moves[0].detail == "Moved from 4th to 1st"


def test_summary_and_rewritten_bullets_carry_before_and_after():
    original = _cv()
    tailored = original.model_copy(update={
        "summary": "Tailored summary.",
        "experiences": [
            original.experiences[0].model_copy(update={"bullets": [
                CVBullet(id="exp1.b1", text="a, reworded"),
                *original.experiences[0].bullets[1:],
            ]}),
            original.experiences[1],
        ],
    })

    changes = describe_changes(original, tailored)

    assert [c.kind for c in changes] == ["summary", "rewritten"]
    summary, rewritten = changes
    assert (summary.id, summary.before, summary.after) == (
        "summary", "Original summary.", "Tailored summary.")
    assert (rewritten.id, rewritten.before, rewritten.after) == ("exp1.b1", "a", "a, reworded")


def test_moves_come_first_biggest_first_then_summary_then_rewrites():
    original = _cv()
    tailored = _reordered(original, "exp1", ["exp1.b4", "exp1.b1", "exp1.b2", "exp1.b3"])
    tailored = _reordered(tailored, "exp2", ["exp2.b2", "exp2.b1"])
    tailored = tailored.model_copy(update={"summary": "New."})

    kinds_ids = [(c.kind, c.id) for c in describe_changes(original, tailored)]

    assert kinds_ids == [("moved", "exp1.b4"), ("moved", "exp2.b2"), ("summary", "summary")]


def test_an_empty_tailored_summary_is_not_reported_as_a_change():
    original = _cv()
    assert describe_changes(original, original.model_copy(update={"summary": ""})) == []


def test_warning_ids_become_employer_names():
    cv = _cv()
    assert readable_tailoring_warning("exp1.b2: rewrite reverted (new numbers 40)", cv) == (
        "Bullet 2 at Acme: rewrite reverted (new numbers 40)")
    assert readable_tailoring_warning("exp2: missing in the model answer", cv) == (
        "Beta: missing in the model answer")
    assert readable_tailoring_warning("exp9: odd", cv) == "This role: odd"
