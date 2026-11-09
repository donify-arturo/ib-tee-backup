"""The locked screen on the hosted app names what is wrong with the Streamlit Secrets, and never shows a value."""
import copy

from ibtee import login

GOOD = {
    "auth": {"redirect_uri": "https://x.test/oauth2callback", "cookie_secret": "s3cret-cookie",
             "google": {"client_id": "abc.apps.googleusercontent.com", "client_secret": "s3cret-client",
                        "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration"}},
    "access": {"owner_email": "me@example.test"},
    "firestore": {"type": "service_account", "project_id": "ib-tee", "private_key_id": "k1",
                  "private_key": "-----BEGIN PRIVATE KEY-----\ns3cret-key\n-----END PRIVATE KEY-----\n",
                  "client_email": "a@ib-tee.iam.gserviceaccount.com", "client_id": "123", "token_uri": "https://oauth2.googleapis.com/token"},
}


def test_complete_secrets_have_no_problems():
    assert login.setup_problems(GOOD) == []


def test_a_missing_firestore_section_is_named():
    s = {k: v for k, v in GOOD.items() if k != "firestore"}
    assert login.setup_problems(s) == ["[firestore] section is missing"]


def test_a_key_without_its_begin_line_is_named():
    s = copy.deepcopy(GOOD)
    s["firestore"]["private_key"] = "s3cret-key-only"
    assert ["private_key" in p for p in login.setup_problems(s)] == [True]


def test_placeholders_count_as_empty():
    s = copy.deepcopy(GOOD)
    s["firestore"]["project_id"] = "CHANGE_ME"
    s["auth"]["google"]["client_id"] = "CHANGE_ME.apps.googleusercontent.com"
    problems = login.setup_problems(s)
    assert "[firestore] project_id is empty" in problems and any("client_id" in p and "auth.google" in p for p in problems)


def test_no_value_is_ever_reported():
    s = copy.deepcopy(GOOD)
    s["firestore"]["private_key"] = "s3cret-key-only"
    s["auth"]["google"]["client_id"] = "s3cret-wrong-id"
    s["auth"]["google"]["client_secret"] = ""
    assert "s3cret" not in " ".join(login.setup_problems(s))
