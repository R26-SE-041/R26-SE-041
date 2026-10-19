from studio.titles import display_chat_title, sketch_title


def test_subject_title_uses_existing_recognition_and_preserves_acronyms():
    assert sketch_title({"subject": "  human   eye "}) == "Human eye"
    assert sketch_title({"recognition": {"subject": "DNA molecule"}}) == "DNA molecule"
    assert sketch_title({"subject": []}) is None


def test_legacy_sketch_placeholder_gets_a_subject_without_rewriting_history():
    source = {"mode": "sketch", "title": "New conversation", "generation_metadata": {"sketchMetadata": {"subject": "human heart"}}}
    assert display_chat_title(dict(source))["title"] == "Human heart"
    assert source["title"] == "New conversation"
    assert "generation_metadata" not in display_chat_title(dict(source))


def test_custom_names_and_other_workspaces_stay_unchanged():
    for mode, title in [("sketch", "My viva drawing"), ("general", "New conversation")]:
        assert display_chat_title({"mode": mode, "title": title, "generation_metadata": {"sketchMetadata": {"subject": "eye"}}})["title"] == title
