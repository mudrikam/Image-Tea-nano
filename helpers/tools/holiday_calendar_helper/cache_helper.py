from database.db_operation import ImageTeaDB
from helpers.tools.holiday_calendar_helper.config_helper import get_expire_days, get_use_sqlite
from helpers.tools.holiday_calendar_helper.holiday_logger import logger


def _db() -> ImageTeaDB:
    return ImageTeaDB()


def _holiday_month(h: dict) -> int:
    m = h.get('date_month')
    if m:
        try:
            return int(m)
        except (ValueError, TypeError):
            pass
    try:
        return int(h.get('date', '').split('-')[1])
    except Exception:
        return 0


def get_holidays(country: str, year: int, month: int) -> list | None:
    if not get_use_sqlite():
        return None

    expire_days = get_expire_days()
    db = _db()

    result = db.holiday_cache_fetch(country, year, month, expire_days)
    if result is not None:
        logger.cache(f'Cache hit: {country} {year}/{month}')
        return result

    if month != 0:
        all_year = db.holiday_cache_fetch(country, year, 0, expire_days)
        if all_year is not None:
            filtered = [h for h in all_year if _holiday_month(h) == month]
            logger.cache(f'Derived from all-year: {country} {year}/{month} ({len(filtered)} holidays)')
            if filtered:
                db.holiday_cache_store(country, year, month, filtered)
            return filtered

    return None


def store_holidays(country: str, year: int, month: int, holidays: list):
    if not holidays:
        logger.cache(f'Skipped caching empty result: {country} {year}/{month}')
        return
    if not get_use_sqlite():
        return
    try:
        _db().holiday_cache_store(country, year, month, holidays)
        logger.cache(f'Stored: {country} {year}/{month} ({len(holidays)} holidays)')
    except Exception as e:
        logger.error(f'Cache store failed: {e}')


def clear_all():
    try:
        _db().holiday_cache_clear_all()
        logger.info('All holiday cache cleared.')
    except Exception as e:
        logger.error(f'Cache clear failed: {e}')


def clear_expired():
    try:
        _db().holiday_cache_clear_expired(get_expire_days())
        logger.info('Expired holiday cache cleared.')
    except Exception as e:
        logger.error(f'Cache clear expired failed: {e}')


def get_countries() -> list | None:
    if not get_use_sqlite():
        return None
    result = _db().holiday_cache_fetch('__COUNTRIES__', 0, 0, get_expire_days())
    if result is not None:
        logger.cache('Countries cache hit')
        return result
    return None


def store_countries(countries: list):
    if not countries:
        return
    if not get_use_sqlite():
        return
    try:
        _db().holiday_cache_store('__COUNTRIES__', 0, 0, countries)
        logger.cache(f'Stored countries list ({len(countries)} countries)')
    except Exception as e:
        logger.error(f'Countries cache store failed: {e}')
