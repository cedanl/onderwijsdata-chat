"""Een rij in `answer_feedback` zoals de duimpjes hem schreven (#248), voor de tests van export, verwijderen en opschonen.

De app schrijft zulke rijen sinds #983 niet meer; die van vóór 09-11 blijven tot de opschoning, en zolang ze er zijn
moeten export en verwijderen ze meenemen.
"""

import json
from datetime import UTC, datetime

from persistence import db


def voeg_toe(username: str, conv_id: str, message_index: int, oordeel: str, toelichting: str, trace: dict) -> None:
    with db._connection() as conn:
        db._execute(
            conn,
            "INSERT INTO answer_feedback "
            "(username, conversation_id, message_index, oordeel, toelichting, trace, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                username,
                conv_id,
                message_index,
                oordeel,
                toelichting,
                json.dumps(trace, ensure_ascii=False),
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
