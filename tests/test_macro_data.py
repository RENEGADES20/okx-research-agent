from epi_agent.macro_data import macro_release_from_payload


def test_macro_release_from_payload_computes_surprise_z():
    release = macro_release_from_payload(
        {
            "event_name": "US Core PCE MoM",
            "actual": "0.4%",
            "forecast": "0.2%",
            "previous": "0.1%",
            "surprise_std": "0.2",
            "importance": 3,
        }
    )

    assert release.event_name == "US Core PCE MoM"
    assert release.actual == 0.4
    assert release.forecast == 0.2
    assert release.surprise == 0.2
    assert release.surprise_z == 1.0
    assert release.importance == 3


def test_macro_release_clamps_large_surprise_z():
    release = macro_release_from_payload(
        {
            "event_name": "NFP",
            "actual": 500,
            "forecast": 100,
            "surprise_std": 10,
        }
    )

    assert release.surprise_z == 5.0
