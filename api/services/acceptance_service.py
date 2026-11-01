from psycopg.types.json import Jsonb

from api.database import get_connection


def accept_quote(quote_id: str, customer_reference: str | None = None):

    with get_connection() as conn:
        with conn.cursor() as cur:

            # Lock the quote to prevent simultaneous acceptance requests.
            cur.execute(
                """
                SELECT
                    quote_id,
                    quote_status,
                    quote_valid_until,
                    applicant_accepted_at
                FROM quotes
                WHERE quote_id = %s
                FOR UPDATE
                """,
                (quote_id,)
            )

            quote = cur.fetchone()

            if not quote:
                raise ValueError("Quote not found.")

            if quote["quote_status"] != "APPROVED":
                raise ValueError(
                    f"Only APPROVED quotes can be accepted. "
                    f"Current status: {quote['quote_status']}"
                )

            if quote["applicant_accepted_at"] is not None:
                raise ValueError("Quote has already been accepted.")

            # Check quote validity using the database clock.
            cur.execute(
                """
                SELECT quote_valid_until >= CURRENT_TIMESTAMP AS is_valid
                FROM quotes
                WHERE quote_id = %s
                """,
                (quote_id,)
            )

            validity = cur.fetchone()

            if not validity["is_valid"]:
                raise ValueError("Quote has expired and cannot be accepted.")

            previous_status = quote["quote_status"]

            # Update quote acceptance.
            cur.execute(
                """
                UPDATE quotes
                SET
                    quote_status = 'ACCEPTED',
                    applicant_accepted_at = CURRENT_TIMESTAMP
                WHERE quote_id = %s
                RETURNING applicant_accepted_at
                """,
                (quote_id,)
            )

            accepted_at = cur.fetchone()["applicant_accepted_at"]

            event_details = {
                "customer_reference": customer_reference,
                "acceptance_timestamp": accepted_at.isoformat(),
                "acceptance_source": "API"
            }

            # Record the acceptance in the audit history.
            cur.execute(
                """
                INSERT INTO quote_events (
                    quote_id,
                    event_type,
                    previous_status,
                    new_status,
                    actor_reference,
                    event_reason,
                    event_details
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING quote_event_id
                """,
                (
                    quote_id,
                    "CUSTOMER_ACCEPTED",
                    previous_status,
                    "ACCEPTED",
                    customer_reference or "CUSTOMER",
                    "Customer accepted the approved insurance quote.",
                    Jsonb(event_details)
                )
            )

            event = cur.fetchone()

            return {
                "message": "Quote accepted successfully",
                "quote_id": quote_id,
                "quote_status": "ACCEPTED",
                "accepted_at": accepted_at,
                "quote_event_id": event["quote_event_id"]
            }