import concurrent.futures
from PySide6.QtCore import QRunnable, QObject, Signal, Slot
from helpers.tools.holiday_calendar_helper import api_client, cache_helper
from helpers.tools.holiday_calendar_helper.holiday_logger import logger
from helpers.tools.holiday_calendar_helper.api_client import CalendarificError, API_KEY_NOT_CONFIGURED
from helpers.tools.holiday_calendar_helper.config_helper import get_api_key


WORLD_COUNTRIES = [
    'US', 'GB', 'DE', 'FR', 'JP', 'CN', 'IN', 'BR', 'AU', 'CA',
    'MX', 'RU', 'KR', 'ID', 'TR', 'SA', 'ZA', 'NG', 'EG', 'AR',
    'IT', 'ES', 'NL', 'SE', 'NO', 'PL', 'TH', 'SG', 'MY', 'PH',
]


class WorkerSignals(QObject):
    finished = Signal(list)
    error = Signal(str)
    cached = Signal(list)
    status = Signal(str)


class HolidayWorker(QRunnable):
    def __init__(self, country: str, year: int, month: int):
        super().__init__()
        self.country = country
        self.year = year
        self.month = month
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            self.signals.status.emit(f'Checking cache for {self.country} {self.year}/{self.month}...')
            cached = cache_helper.get_holidays(self.country, self.year, self.month)
            if cached is not None:
                self.signals.status.emit(f'Loaded from cache: {self.country} {self.year}/{self.month}')
                self.signals.cached.emit(cached)
                return

            self.signals.status.emit(f'Fetching from API: {self.country} {self.year}/{self.month}...')
            holidays = api_client.fetch_holidays(self.country, self.year, self.month)
            cache_helper.store_holidays(self.country, self.year, self.month, holidays)
            self.signals.status.emit(f'Loaded {len(holidays)} holidays from API')
            self.signals.finished.emit(holidays)
        except CalendarificError as e:
            logger.error(str(e))
            self.signals.error.emit(str(e))
        except Exception as e:
            logger.error(f'Unexpected error: {e}')
            self.signals.error.emit(f'Unexpected error: {e}')


class CountriesWorker(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            cached = cache_helper.get_countries()
            if cached is not None:
                self.signals.finished.emit(cached)
                return
            countries = api_client.fetch_countries()
            cache_helper.store_countries(countries)
            self.signals.finished.emit(countries)
        except Exception as e:
            logger.error(f'Failed to fetch countries: {e}')
            self.signals.error.emit(str(e))


class WorldHolidayWorker(QRunnable):
    def __init__(self, year: int, month: int, countries: list = None):
        super().__init__()
        self.year = year
        self.month = month
        self.countries = countries or WORLD_COUNTRIES
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        all_holidays = []
        seen = set()
        self.signals.status.emit(f'Fetching world holidays ({len(self.countries)} countries)...')

        if not get_api_key():
            self.signals.error.emit(API_KEY_NOT_CONFIGURED)
            return

        def fetch_one(code):
            cached = cache_helper.get_holidays(code, self.year, self.month)
            if cached is not None:
                return cached
            try:
                result = api_client.fetch_holidays(code, self.year, self.month)
                cache_helper.store_holidays(code, self.year, self.month, result)
                return result
            except CalendarificError as e:
                logger.error(f'World fetch failed for {code}: {e}')
                return []
            except Exception as e:
                logger.error(f'World fetch unexpected error for {code}: {e}')
                return []

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                futures = {pool.submit(fetch_one, c): c for c in self.countries}
                for future in concurrent.futures.as_completed(futures):
                    for h in future.result():
                        key = (h.get('name', ''), h.get('date', ''))
                        if key not in seen:
                            seen.add(key)
                            all_holidays.append(h)
            all_holidays.sort(key=lambda h: h.get('date', ''))
            if all_holidays:
                cache_helper.store_holidays('WORLD', self.year, self.month, all_holidays)
            self.signals.status.emit(f'World: {len(all_holidays)} unique holidays')
            self.signals.finished.emit(all_holidays)
        except Exception as e:
            logger.error(f'World fetch error: {e}')
            self.signals.error.emit(str(e))
