import bcrypt

from app.main import safe_csv_cell
from app.security import decode_access_token, hash_pin, hash_token, issue_access_token, verify_pin


def test_pin_hash_verifies_only_the_original_pin() -> None:
    encoded = hash_pin("2468")

    assert verify_pin("2468", encoded)
    assert not verify_pin("0000", encoded)


def test_access_token_contains_user_subject_and_role() -> None:
    claims = decode_access_token(issue_access_token(42, "STUDENT"))

    assert claims["sub"] == "42"
    assert claims["roles"] == ["STUDENT"]


def test_refresh_token_hash_is_one_way_and_stable() -> None:
    token = "random-refresh-token"

    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token


def test_existing_spring_bcrypt_pin_can_be_verified() -> None:
    legacy_hash = bcrypt.hashpw(b"2468", bcrypt.gensalt()).decode()

    assert verify_pin("2468", legacy_hash)
    assert not verify_pin("0000", legacy_hash)


def test_csv_cells_that_start_with_formulas_are_escaped() -> None:
    assert safe_csv_cell("=1+1") == "'=1+1"
    assert safe_csv_cell("Student") == "Student"