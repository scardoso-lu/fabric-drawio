"""Tests for agent/main.py — _summarise and _load_skills helpers."""

from pathlib import Path

import pytest

from agent.main import _summarise, _load_skills


class TestSummarise:
    def test_simple_string(self):
        result = _summarise({"key": "value"})
        assert result == "key='value'"

    def test_long_string_truncated(self):
        result = _summarise({"key": "a" * 50})
        assert len(result) < 60
        assert result.endswith("...")

    def test_long_string_boundary(self):
        # 40 chars should NOT be truncated, 41 should
        assert "..." not in _summarise({"k": "a" * 40})
        assert "..." in _summarise({"k": "a" * 41})

    def test_list_shows_count(self):
        result = _summarise({"items": [1, 2, 3]})
        assert "items=[3 items]" in result

    def test_integer_value(self):
        result = _summarise({"id": 42})
        assert "id=42" in result

    def test_multiple_keys(self):
        result = _summarise({"a": "x", "b": "y"})
        assert "a='x'" in result
        assert "b='y'" in result

    def test_empty_dict(self):
        assert _summarise({}) == ""


class TestLoadSkills:
    def test_no_skills_returns_empty_string(self, tmp_path):
        result = _load_skills(tmp_path)
        assert result == ""

    def test_single_skill_loaded(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---\nDo this thing.", encoding="utf-8")

        result = _load_skills(tmp_path)

        assert "my-skill" in result
        assert "Do this thing." in result

    def test_multiple_skills_loaded(self, tmp_path):
        for name in ["skill-a", "skill-b"]:
            d = tmp_path / name
            d.mkdir()
            (d / "SKILL.md").write_text(f"Content of {name}", encoding="utf-8")

        result = _load_skills(tmp_path)

        assert "skill-a" in result
        assert "skill-b" in result

    def test_skills_wrapped_in_section_header(self, tmp_path):
        skill_dir = tmp_path / "s"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("skill content", encoding="utf-8")

        result = _load_skills(tmp_path)

        assert "Active Skills" in result

    def test_skills_sorted_alphabetically(self, tmp_path):
        for name in ["z-skill", "a-skill", "m-skill"]:
            d = tmp_path / name
            d.mkdir()
            (d / "SKILL.md").write_text(f"Content {name}", encoding="utf-8")

        result = _load_skills(tmp_path)

        pos_a = result.index("a-skill")
        pos_m = result.index("m-skill")
        pos_z = result.index("z-skill")
        assert pos_a < pos_m < pos_z

    def test_non_skill_files_ignored(self, tmp_path):
        (tmp_path / "README.md").write_text("not a skill", encoding="utf-8")
        skill_dir = tmp_path / "real-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("real content", encoding="utf-8")

        result = _load_skills(tmp_path)

        assert "not a skill" not in result
        assert "real content" in result
