from studio.titles import display_chat_title, generation_title, prompt_title, sketch_title


def test_image_titles_use_subject_anatomy_or_a_short_prompt_without_model_calls():
    assert generation_title({"mode":"general","prompt":"Please generate an image of a red fox in a forest"}) == "A red fox in a forest"
    assert generation_title({"mode":"general","generationMetadata":{"subject":"DNA molecule"}}) == "DNA molecule"
    assert generation_title({"mode":"anatomy","prompt":"Create a detailed diagram","anatomy":{"organ":"human_heart"}}) == "Human heart"
    assert len(prompt_title("Generate a detailed image of " + "a beautiful forest " * 20)) <= 64


def test_existing_image_defaults_get_titles_and_custom_names_are_preserved():
    metadata = {"prompt":"Please generate an image of a red fox in a forest"}
    for title in ["New conversation", metadata["prompt"]]:
        assert display_chat_title({"mode":"general","title":title,"generation_metadata":metadata})["title"] == "A red fox in a forest"
    assert display_chat_title({"mode":"general","title":"My forest demo","generation_metadata":metadata})["title"] == "My forest demo"


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
