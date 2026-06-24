from labeling.schemas import ClusterInsightLLM, ClusterLabelLLM


def test_cluster_insight_parses_full_payload() -> None:
    m = ClusterInsightLLM.model_validate(
        {
            "label": "Kenaikan harga beras premium",
            "what_happened": "Harga beras melonjak di sejumlah daerah.",
            "parties_involved": ["Bulog", "Kemendag"],
            "editorial_angle": "Telusuri rantai distribusi.",
            "summary": ["Harga naik 10 persen", "Stok menipis"],
        }
    )
    d = m.model_dump()
    assert d["label"] == "Kenaikan harga beras premium"
    assert d["parties_involved"] == ["Bulog", "Kemendag"]
    assert set(d) == {"label", "what_happened", "parties_involved", "editorial_angle", "summary"}


def test_cluster_insight_minimal() -> None:
    m = ClusterInsightLLM.model_validate({"label": "X"})
    assert m.model_dump() == {
        "label": "X",
        "what_happened": None,
        "parties_involved": None,
        "editorial_angle": None,
        "summary": None,
    }


def test_cluster_label() -> None:
    assert ClusterLabelLLM.model_validate({"label": "Topik singkat"}).label == "Topik singkat"
