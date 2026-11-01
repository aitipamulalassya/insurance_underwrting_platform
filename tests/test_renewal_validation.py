
import pytest

from api.services.renewal_service import (
    respond_to_renewal,
    expire_renewal_offers,
)


@pytest.mark.parametrize(
    "invalid_decision",
    ["INVALID", "APPROVE", "CANCEL", "", "PENDING"]
)
def test_invalid_renewal_decision(invalid_decision):
    """
    Invalid decisions must be rejected before database access.
    """

    with pytest.raises(ValueError):
        respond_to_renewal(
            renewal_id="REN-TEST-000001",
            decision=invalid_decision,
            decision_reason="Testing invalid decision."
        )


@pytest.mark.parametrize(
    "invalid_days",
    [0, -1, 366, 500, 1000]
)
def test_invalid_expiry_period(invalid_days):
    """
    Expiry validity must remain between 1 and 365 days.
    """

    with pytest.raises(ValueError):
        expire_renewal_offers(
            validity_days=invalid_days
        )


@pytest.mark.parametrize(
    "valid_days",
    [1, 7, 30, 90, 180, 365]
)
def test_valid_expiry_period_passes_initial_validation(valid_days):
    """
    Valid expiry periods must pass initial input validation.

    Database behavior is not tested here.
    """

    # The service validates validity_days before opening
    # the database connection. We mock that connection
    # to stop execution after validation.
    from unittest.mock import patch

    with patch(
        "api.services.renewal_service.get_connection",
        side_effect=RuntimeError("Database call reached")
    ):
        with pytest.raises(RuntimeError, match="Database call reached"):
            expire_renewal_offers(
                validity_days=valid_days
            )


@pytest.mark.parametrize(
    "valid_decision",
    ["ACCEPT", "DECLINE"]
)
def test_valid_decision_reaches_database_validation(valid_decision):
    """
    Valid decisions must pass initial input validation.

    Database behavior is not tested here.
    """

    from unittest.mock import patch

    with patch(
        "api.services.renewal_service.get_connection",
        side_effect=RuntimeError("Database call reached")
    ):
        with pytest.raises(RuntimeError, match="Database call reached"):
            respond_to_renewal(
                renewal_id="REN-TEST-000001",
                decision=valid_decision,
                decision_reason="Testing valid decision."
            )
