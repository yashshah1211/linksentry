from linksentry.classifier import classify
from linksentry.models import HealthLabel


def test_200_is_healthy():
    assert classify(200) == HealthLabel.HEALTHY


def test_301_is_redirect():
    assert classify(301) == HealthLabel.REDIRECT


def test_404_is_broken():
    assert classify(404) == HealthLabel.BROKEN


from hypothesis import given, settings
from hypothesis import strategies as st


# Feature: link-sentry, Property 5: Deterministic Health Classification
# Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5
@given(st.one_of(st.integers(), st.none(), st.text(), st.floats()))
@settings(max_examples=200)
def test_deterministic_classification(s):
    """Calling classify twice with the same input always returns the same result."""
    assert classify(s) == classify(s)
