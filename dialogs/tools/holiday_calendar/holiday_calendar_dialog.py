import os
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QStackedWidget, QLabel, QStatusBar,
    QPushButton, QFrame
)
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QFont, QIcon
import qtawesome as qta
from config import BASE_PATH

from ui.theme_system import theme
from helpers.tools.holiday_calendar_helper.config_helper import (
    get_default_country, get_ui, set_ui
)
from helpers.tools.holiday_calendar_helper import cache_helper
from helpers.tools.holiday_calendar_helper.api_client import API_KEY_NOT_CONFIGURED
from helpers.tools.holiday_calendar_helper.api_worker import (
    HolidayWorker, CountriesWorker, WorldHolidayWorker
)
from helpers.tools.holiday_calendar_helper.holiday_logger import logger

from dialogs.tools.holiday_calendar.sidebar_widget import SidebarWidget
from dialogs.tools.holiday_calendar.filter_bar_widget import FilterBarWidget
from dialogs.tools.holiday_calendar.holiday_list_widget import HolidayListWidget
from dialogs.tools.holiday_calendar.calendar_view_widget import CalendarViewWidget
from dialogs.tools.holiday_calendar.detail_panel_widget import DetailPanelWidget
from dialogs.tools.holiday_calendar.logs_panel_widget import LogsPanelWidget
from dialogs.tools.holiday_calendar.config_tab_widget import ConfigTabWidget
from dialogs.tools.holiday_calendar.search_tab_widget import SearchTabWidget


class HolidayCalendarDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Microstock Holiday Calendar')
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint
        )
        self.resize(920, 640)
        self.setMinimumSize(780, 500)

        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._thread_pool = QThreadPool.globalInstance()
        self._holidays: list = []
        self._memory_cache: dict = {}
        self._month_counts: dict = {}
        self._pending_holiday: dict = {}

        self._current_year = get_ui('last_year')
        self._current_month = get_ui('last_month')
        self._current_country = get_ui('last_country') or get_default_country()

        self._setup_ui()
        self._connect_signals()
        self._post_init()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setHandleWidth(1)

        self._sidebar = SidebarWidget()
        main_splitter.addWidget(self._sidebar)

        self._center = self._build_center()
        main_splitter.addWidget(self._center)

        main_splitter.setCollapsible(0, True)
        main_splitter.setCollapsible(1, False)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([190, 1000])
        self._main_splitter = main_splitter

        self._logs_panel = LogsPanelWidget()
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.setHandleWidth(1)
        v_splitter.addWidget(main_splitter)
        v_splitter.addWidget(self._logs_panel)
        v_splitter.setCollapsible(0, False)
        v_splitter.setCollapsible(1, True)
        v_splitter.setStretchFactor(0, 1)
        v_splitter.setStretchFactor(1, 0)
        v_splitter.setSizes([640, 28])
        self._v_splitter = v_splitter

        self._logs_panel.toggled.connect(self._on_logs_toggled)

        root_layout.addWidget(v_splitter, 1)

        self._status_bar = QStatusBar()
        self._status_text = QLabel('Ready')
        self._status_bar.addWidget(self._status_text)
        root_layout.addWidget(self._status_bar)

    def _on_logs_toggled(self, collapsed: bool):
        if collapsed:
            self._v_splitter.setSizes([self._v_splitter.height() - 28, 28])
        else:
            self._v_splitter.setSizes([self._v_splitter.height() - 120, 120])

    def _build_center(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tab_widget = QTabWidget()

        self._holidays_tab = self._build_holidays_tab()
        self._search_tab = SearchTabWidget()
        self._config_tab = ConfigTabWidget()

        self._tab_widget.addTab(self._holidays_tab, qta.icon('fa6s.calendar-days'), 'Holidays')
        self._tab_widget.addTab(self._search_tab, qta.icon('fa6s.magnifying-glass'), 'Search')
        self._tab_widget.addTab(self._config_tab, qta.icon('fa6s.gear'), 'Configuration')

        layout.addWidget(self._tab_widget)
        return container

    def _build_holidays_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._filter_bar = FilterBarWidget()
        layout.addWidget(self._filter_bar)

        self._view_stack = QStackedWidget()
        self._holiday_list = HolidayListWidget()
        self._calendar_view = CalendarViewWidget()
        self._view_stack.addWidget(self._holiday_list)
        self._view_stack.addWidget(self._calendar_view)

        self._detail_panel = DetailPanelWidget()

        center_splitter = QSplitter(Qt.Orientation.Horizontal)
        center_splitter.setHandleWidth(1)
        center_splitter.addWidget(self._view_stack)
        center_splitter.addWidget(self._detail_panel)
        center_splitter.setCollapsible(0, False)
        center_splitter.setCollapsible(1, True)
        center_splitter.setStretchFactor(0, 1)
        center_splitter.setStretchFactor(1, 0)
        center_splitter.setSizes([760, 280])
        self._center_splitter = center_splitter

        layout.addWidget(center_splitter, 1)
        return tab

    def _connect_signals(self):
        self._sidebar.month_selected.connect(self._on_month_selected)
        self._sidebar.year_changed.connect(self._on_year_changed)
        self._filter_bar.country_changed.connect(self._on_country_changed)
        self._filter_bar.search_changed.connect(self._holiday_list.set_search)
        self._filter_bar.view_mode_changed.connect(self._on_view_mode_changed)
        self._filter_bar.refresh_requested.connect(self._on_refresh)
        self._holiday_list.holiday_selected.connect(self._on_holiday_selected)
        self._calendar_view.date_clicked.connect(self._on_date_clicked)
        self._detail_panel.close_requested.connect(lambda: None)
        self._detail_panel.search_platform_requested.connect(self._on_search_platform)
        self._config_tab.config_saved.connect(self._on_config_saved)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)

    def _post_init(self):
        self._sidebar.set_year(self._current_year)
        self._sidebar.set_selected_month(self._current_month - 1 if self._current_month > 0 else -1)

        worker = CountriesWorker()
        worker.signals.finished.connect(self._on_countries_loaded)
        self._thread_pool.start(worker)

        if self._current_month > 0:
            self._load_holidays(self._current_country, self._current_year, self._current_month, show_dialog=False)
        else:
            self._load_holidays(self._current_country, self._current_year, 0, show_dialog=False)

    def _on_countries_loaded(self, countries: list):
        self._filter_bar.populate_countries(countries)
        self._filter_bar.set_country(self._current_country)

    def _on_month_selected(self, month: int):
        self._current_month = month
        set_ui('last_month', month)
        self._load_holidays(self._current_country, self._current_year, month, show_dialog=True)

    def _on_year_changed(self, year: int):
        self._current_year = year
        set_ui('last_year', year)
        self._memory_cache.clear()
        self._month_counts.clear()
        if self._current_month > 0:
            self._load_holidays(self._current_country, year, self._current_month, show_dialog=True)
        else:
            self._load_holidays(self._current_country, year, 0, show_dialog=True)

    def _on_country_changed(self, code: str):
        self._current_country = code
        set_ui('last_country', code)
        self._memory_cache.clear()
        self._month_counts.clear()
        if self._current_month > 0:
            self._load_holidays(code, self._current_year, self._current_month, show_dialog=True)
        else:
            self._load_holidays(code, self._current_year, 0, show_dialog=True)

    def _on_view_mode_changed(self, mode: str):
        if mode == 'list':
            self._view_stack.setCurrentWidget(self._holiday_list)
        else:
            self._view_stack.setCurrentWidget(self._calendar_view)
            self._calendar_view.set_month(self._current_year, self._current_month if self._current_month > 0 else 1)
            self._calendar_view.set_holidays(self._holidays)

    def _on_refresh(self):
        cache_helper.clear_all()
        self._memory_cache.clear()
        self._month_counts.clear()
        self._load_holidays(self._current_country, self._current_year, self._current_month, force=True, show_dialog=True)

    def _on_holiday_selected(self, holiday: dict):
        self._detail_panel.show_holiday(holiday)
        self._pending_holiday = holiday

    def _on_date_clicked(self, date_str: str, holidays: list):
        self._detail_panel.show_date_holidays(date_str, holidays)

    def _on_tab_changed(self, index: int):
        if index == 1 and self._pending_holiday:
            self._search_tab.set_holiday(self._pending_holiday)

    def _on_search_platform(self, platform_id: str, keyword: str):
        if hasattr(self, '_pending_holiday') and self._pending_holiday:
            self._search_tab.set_holiday(self._pending_holiday)
        self._tab_widget.setCurrentIndex(1)
        self._search_tab.switch_to_platform(platform_id)

    def _on_config_saved(self):
        worker = CountriesWorker()
        worker.signals.finished.connect(self._on_countries_loaded)
        self._thread_pool.start(worker)

    def _set_status(self, msg: str):
        self._status_text.setText(msg)

    def _load_holidays(self, country: str, year: int, month: int, force: bool = False, show_dialog: bool = True):
        cache_key = (country, year, month)

        # 1. Memory cache (synchronous)
        self._current_country = country
        self._current_year = year
        self._current_month = month

        if not force and cache_key in self._memory_cache:
            self._on_holidays_loaded(self._memory_cache[cache_key])
            return

        # 2. SQLite cache (synchronous, no worker needed)
        if not force:
            cached = cache_helper.get_holidays(country, year, month)
            if cached is not None:
                self._on_holidays_loaded(cached)
                return

        # 3. Need API fetch - check key first from main thread before spawning worker
        from helpers.tools.holiday_calendar_helper.config_helper import get_api_key
        from helpers.tools.holiday_calendar_helper.api_client import API_KEY_NOT_CONFIGURED
        if not get_api_key():
            self._holiday_list.show_error(
                'No API key configured. Become a member or add your own Calendarific API key.'
            )
            self._set_status('No API key — open Configuration tab to set your key')
            if show_dialog:
                self._show_api_key_missing_dialog()
            return

        self._holiday_list.show_loading()

        if country == 'WORLD':
            worker = WorldHolidayWorker(year, month)
        else:
            worker = HolidayWorker(country, year, month)

        worker.signals.status.connect(self._set_status)
        worker.signals.finished.connect(self._on_holidays_loaded)
        worker.signals.cached.connect(self._on_holidays_loaded)
        worker.signals.error.connect(self._on_fetch_error)
        self._thread_pool.start(worker)

    def _on_holidays_loaded(self, holidays: list):
        from collections import Counter
        self._holidays = holidays
        self._holiday_list.set_holidays(holidays)
        self._calendar_view.set_holidays(holidays)
        if self._filter_bar.get_view_mode() == 'calendar':
            m = self._current_month if self._current_month > 0 else 1
            self._calendar_view.set_month(self._current_year, m)
        key = (self._current_country, self._current_year, self._current_month)
        self._memory_cache[key] = holidays
        count = len(holidays)
        ck = (self._current_country, self._current_year)
        if ck not in self._month_counts:
            self._month_counts[ck] = {}
        if self._current_month == 0:
            counts = Counter()
            for h in holidays:
                try:
                    m = int(h.get('date_month') or h.get('date', '').split('-')[1])
                    counts[m] += 1
                except Exception:
                    pass
            self._month_counts[ck].update(dict(counts))
        else:
            self._month_counts[ck][self._current_month] = count
        self._sidebar.set_month_counts(self._month_counts[ck])
        self._set_status(f'Loaded: {count} holidays')

    def _on_fetch_error(self, error: str):
        if error == API_KEY_NOT_CONFIGURED:
            self._holiday_list.show_error(
                'No API key configured. Become a member or add your own Calendarific API key.'
            )
            self._set_status('No API key — open Configuration tab to set your key')
        else:
            self._holiday_list.show_error(error)
            self._set_status(f'Error: {error}')

    def _show_api_key_missing_dialog(self):
        import webbrowser
        dlg = QDialog(self)
        dlg.setWindowTitle('Calendarific API Key Required')
        dlg.setFixedWidth(420)
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 14, 16, 12)

        icon_row = QHBoxLayout()
        icon_row.setSpacing(10)
        icon_lbl = QLabel()
        try:
            icon_lbl.setPixmap(qta.icon('fa6s.calendar-xmark', color=theme.get_color('error')).pixmap(28, 28))
        except Exception:
            pass
        title_lbl = QLabel('No API Key Configured')
        title_lbl.setStyleSheet('font-size: 16px; font-weight: bold;')
        icon_row.addWidget(icon_lbl)
        icon_row.addWidget(title_lbl)
        icon_row.addStretch()
        layout.addLayout(icon_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        member_box = QFrame()
        member_box.setFrameShape(QFrame.Shape.StyledPanel)
        member_box.setFrameShadow(QFrame.Shadow.Sunken)
        member_lyt = QVBoxLayout(member_box)
        member_lyt.setContentsMargins(10, 8, 10, 10)
        member_lyt.setSpacing(6)

        opt1_title = QLabel('Option 1 - Become a Member (Recommended)')
        opt1_title.setStyleSheet('font-size: 11px; font-weight: bold;')
        member_lyt.addWidget(opt1_title)

        opt1_desc = QLabel(
            'As a member, you get automatic access to the Holiday Calendar '
            'with no API key needed. The key is provided by Desainia Studio on your behalf.'
        )
        opt1_desc.setWordWrap(True)
        opt1_desc.setStyleSheet('font-size: 11px;')
        member_lyt.addWidget(opt1_desc)

        member_btn = QPushButton(qta.icon('fa6s.star', color=theme.get_color('white')), ' Become a Member')
        member_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        member_btn.setStyleSheet(
            f'background-color: {theme.get_color("primary")}; color: {theme.get_color("white")};'
            f'font-weight: bold; border-radius: 5px; padding: 5px 14px;'
        )
        member_btn.clicked.connect(lambda: (
            webbrowser.open('https://lynk.id/desainiajob/rrwn88qj8jjl'),
            dlg.accept()
        ))
        member_lyt.addWidget(member_btn)
        layout.addWidget(member_box)

        own_box = QFrame()
        own_box.setFrameShape(QFrame.Shape.StyledPanel)
        own_box.setFrameShadow(QFrame.Shadow.Sunken)
        own_lyt = QVBoxLayout(own_box)
        own_lyt.setContentsMargins(10, 8, 10, 10)
        own_lyt.setSpacing(6)

        opt2_title = QLabel('Option 2 - Use Your Own API Key')
        opt2_title.setStyleSheet('font-size: 11px; font-weight: bold;')
        own_lyt.addWidget(opt2_title)

        opt2_desc = QLabel(
            'Get a free API key at calendarific.com, then paste it in the '
            'Configuration tab of this tool.'
        )
        opt2_desc.setWordWrap(True)
        opt2_desc.setStyleSheet('font-size: 11px;')
        own_lyt.addWidget(opt2_desc)

        own_btn_row = QHBoxLayout()
        get_key_btn = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), ' Get Free API Key')
        get_key_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        get_key_btn.clicked.connect(lambda: webbrowser.open('https://calendarific.com/account/dashboard'))
        config_btn = QPushButton(qta.icon('fa6s.gear'), ' Open Configuration')
        config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        config_btn.clicked.connect(lambda: (
            self._tab_widget.setCurrentIndex(2),
            dlg.accept()
        ))
        own_btn_row.addWidget(get_key_btn)
        own_btn_row.addWidget(config_btn)
        own_btn_row.addStretch()
        own_lyt.addLayout(own_btn_row)
        layout.addWidget(own_box)

        close_btn = QPushButton(qta.icon('fa6s.xmark'), ' Close')
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

        dlg.exec()

    def closeEvent(self, event):
        event.accept()
