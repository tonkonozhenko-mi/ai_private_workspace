from app.core.domain.structured_output import (
    json_object_response_format,
    json_schema_response_format,
)


def test_json_schema_shape():
    rf = json_schema_response_format({"type": "object"}, name="tool_call")
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["name"] == "tool_call"
    assert rf["json_schema"]["strict"] is True
    assert rf["json_schema"]["schema"] == {"type": "object"}


def test_json_schema_strict_false():
    rf = json_schema_response_format({"a": 1}, strict=False)
    assert rf["json_schema"]["strict"] is False


def test_json_object_shape():
    assert json_object_response_format() == {"type": "json_object"}
