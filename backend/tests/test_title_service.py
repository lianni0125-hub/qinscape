from types import SimpleNamespace

from backend.app.services.title_service import compose_title


def card(mode="xieyi", prompt="月下松风穿过远山", target="让景物形成可听见的流动"):
    return SimpleNamespace(
        mode=mode,
        prompt=prompt,
        current="一幅正在展开的景" if mode == "xieyi" else "悲伤",
        target=target,
        imagery=["松风", "远山"],
        sound=["疏缓", "清润"],
        five_tone_path=["shang", "gong"],
    )


def test_title_is_stable_for_the_same_seed():
    item = card()
    assert compose_title(item, seed="same-work") == compose_title(item, seed="same-work")


def test_all_supported_lengths_can_appear():
    lengths = {len(compose_title(card(), seed=f"work-{index}")) for index in range(200)}
    assert lengths == {2, 3, 4, 5}


def test_generated_titles_stay_inside_two_to_five_characters():
    for index in range(200):
        title = compose_title(card(), seed=index, lyrics=index % 2 == 0, lyric_lines=8)
        assert 2 <= len(title) <= 5


def test_tiaoxin_does_not_name_present_sadness_as_yuan():
    item = card(mode="tiaoxin", prompt="我很悲伤，希望慢慢安定", target="被容纳 · 慢慢稳定")
    assert all(not compose_title(item, seed=index).endswith("怨") for index in range(200))


def test_song_and_pai_are_not_used_without_lyrics():
    item = card()
    titles = [compose_title(item, seed=index, lyrics=False) for index in range(200)]
    assert all(not title.endswith(("歌", "拍")) for title in titles)
