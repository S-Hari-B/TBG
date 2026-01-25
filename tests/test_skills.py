from tbg.data.repositories import SkillsRepository


def test_skills_repo_loads_entries() -> None:
    repo = SkillsRepository()
    skills = repo.all()
    skill_ids = {skill.id for skill in skills}
    assert "skill_power_slash" in skill_ids
    assert "skill_firebolt" in skill_ids


def test_skill_schema_loaded_correctly() -> None:
    repo = SkillsRepository()
    firebolt = repo.get("skill_firebolt")
    assert firebolt.target_mode == "single_enemy"
    assert firebolt.effect_type == "damage"
    assert firebolt.mp_cost >= 0


