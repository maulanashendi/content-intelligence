from labeling.schemas import ClusterInsightLLM, ClusterLabelLLM


def test_cluster_insight_parses_full_payload() -> None:
    m = ClusterInsightLLM.model_validate(
        {
            "label": "Kenaikan harga beras premium",
            "what_happened": "Harga beras melonjak di sejumlah daerah.",
            "parties_involved": ["Bulog", "Kemendag"],
            "editorial_angle": "Telusuri rantai distribusi.",
            "summary": ["Harga naik 10 persen", "Stok menipis"],
            "desk_category": "Ekonomi & Bisnis",
            "user_need_category": "Update me",
        }
    )
    d = m.model_dump()
    assert d["label"] == "Kenaikan harga beras premium"
    assert d["parties_involved"] == ["Bulog", "Kemendag"]
    assert d["desk_category"] == "Ekonomi & Bisnis"
    assert d["user_need_category"] == "Update me"
    assert set(d) == {
        "label", "what_happened", "parties_involved", "editorial_angle",
        "summary", "desk_category", "user_need_category",
    }


def test_cluster_insight_minimal() -> None:
    m = ClusterInsightLLM.model_validate({"label": "X"})
    assert m.model_dump() == {
        "label": "X",
        "what_happened": None,
        "parties_involved": None,
        "editorial_angle": None,
        "summary": None,
        "desk_category": None,
        "user_need_category": None,
    }


def test_cluster_label() -> None:
    assert ClusterLabelLLM.model_validate({"label": "Topik singkat"}).label == "Topik singkat"
