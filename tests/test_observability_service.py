from observability_service import ReleaseRequest, decide_release


def test_release_waits_for_creator_flag_and_ships_when_enabled():
    request = ReleaseRequest("creator-18", "build-204", "release-7", "creator-publish", "creator-18")
    assert decide_release(request, False) == "review"
    assert decide_release(request, True) == "ship"


def test_release_without_build_is_blocked():
    request = ReleaseRequest("creator-18", "", "release-7", "creator-publish", "creator-18")
    assert decide_release(request, True) == "blocked"
