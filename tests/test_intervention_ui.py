from pathlib import Path


def test_intervention_rollback_is_rendered() -> None:
    app_js = Path("src/fieldtech/api/static/app.js").read_text(encoding="utf-8")

    assert "escapeHtml(action.rollback)" in app_js
    assert "<strong>Rollback</strong>" in app_js
