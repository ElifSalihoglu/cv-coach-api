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


# ---- regressions: what counts as a change ----

from app.models.cv_document import TailoredBullet, TailoredContent, TailoredExperience  # noqa: E402
from app.services.cv_changes import normalize_text  # noqa: E402
from app.services.cv_tailoring import build_tailored_cv  # noqa: E402

NBSP = chr(0xA0)  # non-breaking space, as PDF text extraction produces it
PDF_TEXT = f"Built a billing API for{NBSP}200 merchants\nusing Python  and FastAPI. "


def _with_bullets(texts: list[str], exp_id="exp1", employer="Acme", title="Engineer") -> StructuredCV:
    return StructuredCV(
        name="T", summary="S.",
        experiences=[CVExperience(
            id=exp_id, employer=employer, title=title,
            bullets=[CVBullet(id=f"{exp_id}.b{i}", text=t) for i, t in enumerate(texts, start=1)],
        )],
    )


def _tailored(original: StructuredCV, order: list[str], texts: dict[str, str] | None = None) -> StructuredCV:
    texts = texts or {}
    exp = original.experiences[0]
    by_id = {b.id: b for b in exp.bullets}
    bullets = [CVBullet(id=i, text=texts.get(i, by_id[i].text)) for i in order]
    return original.model_copy(update={"experiences": [exp.model_copy(update={"bullets": bullets})]})


def test_only_line_breaks_spaces_and_non_breaking_spaces_differ_is_not_a_change():
    original = _with_bullets([PDF_TEXT, "Mentored four engineers."])
    tailored = _tailored(original, ["exp1.b1", "exp1.b2"], {
        "exp1.b1": "Built a billing API for 200 merchants using Python and FastAPI.",
    })
    assert describe_changes(original, tailored) == []


def test_only_the_order_differs_gives_one_moved_record_with_the_original_text():
    original = _with_bullets([PDF_TEXT, "Mentored four engineers.", "Led the review."])
    tailored = _tailored(original, ["exp1.b3", "exp1.b1", "exp1.b2"])

    (change,) = describe_changes(original, tailored)

    assert (change.kind, change.id, change.detail) == ("moved", "exp1.b3", "Moved from 3rd to 1st")
    assert change.after == "Led the review."


def test_one_changed_number_is_kept_despite_whitespace_noise():
    original = _with_bullets([f"Reduced backlog by 3{NBSP}years\nof data."])
    tailored = _tailored(original, ["exp1.b1"], {"exp1.b1": "Reduced backlog by 5 years of data."})

    (change,) = describe_changes(original, tailored)

    assert change.kind == "rewritten"
    assert change.before == f"Reduced backlog by 3{NBSP}years\nof data."  # original text kept as is
    assert change.after == "Reduced backlog by 5 years of data."
    assert normalize_text("3 years") != normalize_text("5 years")


def test_a_bullet_moved_and_reworded_is_one_record():
    original = _with_bullets(["First.", "Second.", PDF_TEXT])
    tailored = _tailored(original, ["exp1.b3", "exp1.b1", "exp1.b2"], {
        "exp1.b3": "Built a billing API for 200 merchants with Python and FastAPI.",
    })

    changes = describe_changes(original, tailored)

    assert [(c.kind, c.id) for c in changes] == [("moved_rewritten", "exp1.b3")]
    assert changes[0].detail == "Moved from 3rd to 1st"
    assert changes[0].before == PDF_TEXT


def test_reworded_bullet_that_stays_in_place_is_plain_rewritten():
    original = _with_bullets(["Alpha beta.", "Gamma."])
    tailored = _tailored(original, ["exp1.b1", "exp1.b2"], {"exp1.b2": "Gamma delta."})
    assert [(c.kind, c.detail) for c in describe_changes(original, tailored)] == [("rewritten", "")]


def test_text_reverted_by_the_faithfulness_check_is_not_reworded():
    original = _with_bullets([PDF_TEXT, "Mentored four engineers."])
    content = TailoredContent(summary="S.", experiences=[TailoredExperience(id="exp1", bullets=[
        # the model invents "40%": the check puts the source text back
        TailoredBullet(source_id="exp1.b1", text="Built a billing API for 200 merchants, cutting costs by 40%."),
        TailoredBullet(source_id="exp1.b2", text="Mentored four engineers."),
    ])])

    result = build_tailored_cv(original, content, "Job needing Python")

    assert any("original wording kept" in w for w in result.warnings)
    assert describe_changes(original, result.cv) == []


def test_whitespace_trimmed_by_the_model_schema_is_not_a_change():
    original = _with_bullets([PDF_TEXT])  # ends with a space; TailoredBullet strips it
    content = TailoredContent(summary="S.", experiences=[TailoredExperience(
        id="exp1", bullets=[TailoredBullet(source_id="exp1.b1", text=PDF_TEXT)])])
    result = build_tailored_cv(original, content, "Job")
    assert describe_changes(original, result.cv) == []


def test_summary_with_only_whitespace_differences_is_not_a_change():
    original = _with_bullets(["A."]).model_copy(update={"summary": f"Backend{NBSP}engineer\nwith  Python."})
    tailored = original.model_copy(update={"summary": "Backend engineer with Python."})
    assert describe_changes(original, tailored) == []


def test_role_labels_tell_apart_same_title_same_employer_and_same_employer_other_role():
    def exp(i, employer, title, start, end):
        return CVExperience(id=f"exp{i}", employer=employer, title=title, start=start, end=end,
                            bullets=[CVBullet(id=f"exp{i}.b1", text="x"), CVBullet(id=f"exp{i}.b2", text="y")])

    original = StructuredCV(name="T", summary="S.", experiences=[
        exp(1, "Acme", "Engineer", "2018", "2020"),
        exp(2, "Acme", "Engineer", "2020", "2022"),   # same title, same employer
        exp(3, "Beta", "Engineer", "2022", "2024"),   # same title, other employer
        exp(4, "Beta", "Lead", "2024", ""),           # same employer, other role
    ])
    swapped = [e.model_copy(update={"bullets": list(reversed(e.bullets))}) for e in original.experiences]
    tailored = original.model_copy(update={"experiences": swapped})

    where = [c.where for c in describe_changes(original, tailored)]

    assert where == [
        "Engineer — Acme (2018 – 2020)", "Engineer — Acme (2020 – 2022)",
        "Engineer — Beta", "Lead — Beta",
    ]
