"""Deterministic fabric/paint patterns and validated, reusable AI references."""
import io
import re
import threading
import unicodedata
from collections import OrderedDict
from PIL import Image, ImageDraw
import requests

_CACHE = OrderedDict()
_LOCK = threading.Lock()
COLORS = {'preto': (12,12,12), 'black': (12,12,12), 'branco': (250,250,250), 'white': (250,250,250),
          'amarelo': (255,210,0), 'yellow': (255,210,0), 'vermelho': (220,20,30), 'red': (220,20,30),
          'azul': (20,80,220), 'blue': (20,80,220), 'verde': (30,160,60), 'green': (30,160,60),
          'laranja': (245,125,15), 'orange': (245,125,15), 'rosa': (235,100,155), 'pink': (235,100,155)}


def normalized(prompt):
    text = ''.join(c for c in unicodedata.normalize('NFD', prompt.lower()) if unicodedata.category(c) != 'Mn')
    return re.sub(r'\b(vermelhas?|vermelhos)\b', 'vermelho', re.sub(r'\b(amarelas?|amarelos)\b', 'amarelo', text))


def pattern_kind(prompt):
    text = normalized(prompt)
    if any(word in text for word in ('xadrez', 'xadrex', 'checker', 'quadriculad')):
        return 'checker'
    if any(word in text for word in ('bolinha', 'bolas', 'polka', 'poa', 'pontos')):
        return 'dots'
    return None


def pattern_image(prompt, resolution):
    kind = pattern_kind(prompt)
    if not kind:
        return None
    text = normalized(prompt)
    found = [(match.start(), COLORS[match.group()]) for match in re.finditer(r'\b(' + '|'.join(COLORS) + r')\b', text)]
    first, second = (found[0][1] if found else (12,12,12)), (found[1][1] if len(found) > 1 else (250,250,250))
    # "fundo branco com bolinhas vermelhas" names the background first.
    if kind == 'dots' and 'fundo' in text and found and text.index('fundo') < found[0][0]:
        first, second = second, first
    image = Image.new('RGB', (resolution * 2, resolution * 2), second)
    draw = ImageDraw.Draw(image)
    cells = 12
    size = image.width / cells
    for row in range(cells):
        for col in range(cells):
            x, y = col * size, row * size
            if kind == 'checker' and (row + col) % 2 == 0:
                draw.rectangle((round(x), round(y), round(x+size)-1, round(y+size)-1), fill=first)
            elif kind == 'dots':
                radius = size * 0.23
                cx, cy = x + size / 2, y + size / 2
                draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=first)
    return image.resize((resolution, resolution), Image.Resampling.LANCZOS)


def reference_image(prompt, resolution=1024, method='AUTO'):
    if method in {'AUTO', 'PATTERN'}:
        image = pattern_image(prompt, resolution)
        if image is not None:
            return image, 'local-pattern'
        if method == 'PATTERN':
            raise ValueError('Descreva um padrão xadrez ou de bolinhas e as cores desejadas.')
    key = prompt.strip()
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key].copy(), 'remote-cache'
    url = 'https://image.pollinations.ai/p/' + requests.utils.quote(prompt, safe='')
    response = requests.get(url, params={'width': 1024, 'height': 1024, 'seed': 42, 'nologo': 'true'}, timeout=25)
    response.raise_for_status()
    image = Image.open(io.BytesIO(response.content))
    image.load()
    image = image.convert('RGB')
    if min(image.size) < 256:
        raise ValueError('O serviço retornou uma imagem de referência pequena demais. Selecione uma imagem local.')
    with _LOCK:
        _CACHE[key] = image.copy()
        while len(_CACHE) > 8:
            _CACHE.popitem(last=False)
    return image, 'remote'
