from app.auth import create_access_token, create_refresh_token, decode_token


def test_access_token_has_expected_subject_and_type():
    token = create_access_token(42)
    user_id, claims = decode_token(token, "access")

    assert user_id == 42
    assert claims["type"] == "access"


def test_refresh_token_includes_unique_identifier():
    token, token_id, _ = create_refresh_token(7)
    user_id, claims = decode_token(token, "refresh")

    assert user_id == 7
    assert claims["jti"] == token_id
