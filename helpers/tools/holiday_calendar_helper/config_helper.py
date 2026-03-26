import json
import os
from pathlib import Path
from config import BASE_PATH


_CONFIG_PATH = Path(BASE_PATH) / 'configs' / 'calendarific_config.json'

_config: dict = {}


def _load():
    global _config
    with open(str(_CONFIG_PATH), 'r', encoding='utf-8') as f:
        _config = json.load(f)


def _save():
    with open(str(_CONFIG_PATH), 'w', encoding='utf-8') as f:
        json.dump(_config, f, indent=4)


_load()


def get_api_key() -> str:
    from helpers.members_helper.members_helper import is_logged_in, get_calendarific_api_key
    if is_logged_in():
        member_key = get_calendarific_api_key()
        if member_key:
            return member_key
    from database.db_operation import ImageTeaDB
    return ImageTeaDB().calendarific_get_api_key()


def get_base_url() -> str:
    return _config['api']['base_url']


def get_default_country() -> str:
    return _config['api']['default_country']


def get_expire_days() -> int:
    return _config['cache']['expire_days']


def get_use_sqlite() -> bool:
    return _config['cache']['use_sqlite']


def get_ui(key: str):
    return _config['ui'][key]


def set_api_key(value: str):
    from database.db_operation import ImageTeaDB
    ImageTeaDB().calendarific_set_api_key(value.strip())


def set_base_url(value: str):
    _config['api']['base_url'] = value
    _save()


def set_default_country(value: str):
    _config['api']['default_country'] = value.upper()
    _save()


def set_expire_days(value: int):
    _config['cache']['expire_days'] = value
    _save()


def set_use_sqlite(value: bool):
    _config['cache']['use_sqlite'] = value
    _save()


def set_ui(key: str, value):
    _config['ui'][key] = value
    _save()
