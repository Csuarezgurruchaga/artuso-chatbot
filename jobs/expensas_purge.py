import logging
import sys

from services.expensas_purge_service import ExpensasPurgeService


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    service = ExpensasPurgeService()
    summary = service.rotate_monthly()
    logging.info("Expensas rotation completed: %s", summary)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        logging.exception("Expensas rotation failed: %s", exc)
        sys.exit(1)
