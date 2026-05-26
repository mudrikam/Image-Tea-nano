import os
from urllib.parse import quote_plus
from config import BASE_PATH


PLATFORMS = [
    {
        'id': 'adobe_stock',
        'name': 'Adobe Stock',
        'ico': 'adobe_stock.ico',
        'url': 'https://stock.adobe.com/search?k={kw}&search_type=usertyped',
    },
    {
        'id': 'shutterstock',
        'name': 'Shutterstock',
        'ico': 'shutterstock.ico',
        'url': 'https://www.shutterstock.com/search/{kw}',
    },
    {
        'id': 'magnific',
        'name': 'Magnific',
        'ico': 'magnific.ico',
        'url': 'https://www.magnific.com/search?format=search&term={kw}',
    },
    {
        'id': 'vecteezy',
        'name': 'Vecteezy',
        'ico': 'vecteezy.ico',
        'url': 'https://www.vecteezy.com/search?qterm={kw}&content_type=image',
    },
    {
        'id': 'envato_elements',
        'name': 'Envato Elements',
        'ico': 'envato_elements.ico',
        'url': 'https://elements.envato.com/all-items/{kw}',
    },
    {
        'id': 'miricanvas',
        'name': 'MiriCanvas',
        'ico': 'miricanvas.ico',
        'url': 'https://www.miricanvas.com/en/template/all-types?keyword={kw}',
    },
    {
        'id': 'istock',
        'name': 'iStock',
        'ico': 'istock.ico',
        'url': 'https://www.istockphoto.com/search/2/image?phrase={kw}',
    },
    {
        'id': 'depositphotos',
        'name': 'DepositPhotos',
        'ico': 'depositphotos.ico',
        'url': 'https://depositphotos.com/stock-photos/{kw}.html',
    },
    {
        'id': 'dreamstime',
        'name': 'Dreamstime',
        'ico': 'dreamstime.ico',
        'url': 'https://www.dreamstime.com/search.php?srh_field={kw}',
    },
    {
        'id': 'pngtree',
        'name': 'Pngtree',
        'ico': 'pngtree.ico',
        'url': 'https://pngtree.com/so/{kw}',
    },
    {
        'id': 'pikbest',
        'name': 'Pikbest',
        'ico': 'pikbest.ico',
        'url': 'https://pikbest.com/search.php?m=tags&a=index&class=0-0-0-0-0-c0_0&key={kw}&group_c1=image',
    },
    {
        'id': 'alamy',
        'name': 'Alamy',
        'ico': 'alamy.ico',
        'url': 'https://www.alamy.com/stock-photo/{kw}.html?sortBy=relevant',
    },
    {
        'id': '123rf',
        'name': '123RF',
        'ico': '123rf.ico',
        'url': 'https://www.123rf.com/stock-photo/{kw}.html',
    },
]

_PLATFORMS_DIR = os.path.join(BASE_PATH, 'res', 'platforms')


def ico_path(platform_id: str) -> str:
    for p in PLATFORMS:
        if p['id'] == platform_id:
            return os.path.join(_PLATFORMS_DIR, p['ico'])
    return ''


def build_url(platform_id: str, keyword: str) -> str:
    kw_encoded = quote_plus(keyword.strip())
    for p in PLATFORMS:
        if p['id'] == platform_id:
            return p['url'].format(kw=kw_encoded)
    raise KeyError(f'Unknown platform id: {platform_id!r}')
