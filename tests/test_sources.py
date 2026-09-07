from osservatorio_seo.sources import is_event_item, is_google_source, override_importance


def test_is_google_source_true_for_known_ids() -> None:
    assert is_google_source("google_search_central_blog") is True
    assert is_google_source("web_dev") is True


def test_is_google_source_false_for_unknown_id() -> None:
    assert is_google_source("ahrefs_blog") is False


def test_is_event_item_true_for_event_tags() -> None:
    assert is_event_item(["search_central_live"]) is True
    assert is_event_item(["conference", "other_tag"]) is True


def test_is_event_item_false_without_tags() -> None:
    assert is_event_item([]) is False
    assert is_event_item(None) is False
    assert is_event_item(["core_update"]) is False


def test_override_importance_google_source_always_five() -> None:
    assert override_importance("google_search_central_blog", 2, [], authority=10) == 5


def test_override_importance_google_event_respects_ai_judgment() -> None:
    assert override_importance("google_search_central_blog", 2, ["event"], authority=10) == 2


def test_override_importance_non_google_respects_ai_judgment_when_authority_high() -> None:
    assert override_importance("ahrefs_blog", 5, [], authority=8) == 5
    assert override_importance("ahrefs_blog", 3, [], authority=8) == 3


def test_override_importance_caps_at_4_for_low_authority_source() -> None:
    """D8: una fonte con autorevolezza <= 7 non puo' ricevere importance 5,
    anche se il summarizer AI l'ha giudicata cosi'."""
    assert override_importance("semrush_blog", 5, [], authority=7) == 4


def test_override_importance_low_authority_below_cap_unaffected() -> None:
    """Il tetto D8 abbassa solo il 5: un 3 o 4 da una fonte poco autorevole
    restano quello che erano, non c'e' ragione di alzarli o abbassarli."""
    assert override_importance("semrush_blog", 3, [], authority=5) == 3
    assert override_importance("semrush_blog", 4, [], authority=5) == 4


def test_override_importance_without_authority_is_unaffected() -> None:
    """authority=None (non passato) non deve mai far scattare il tetto D8."""
    assert override_importance("semrush_blog", 5, []) == 5
