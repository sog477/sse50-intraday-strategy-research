"""Portable Chinese font selection for existing research plots."""
from pathlib import Path
from matplotlib.font_manager import FontProperties, fontManager

def research_font():
    windows = Path('C:/Windows/Fonts/msyh.ttc')
    if windows.exists():
        return FontProperties(fname=str(windows))
    for name in ('Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'SimHei', 'Arial Unicode MS'):
        if any(item.name == name for item in fontManager.ttflist):
            return FontProperties(family=name)
    return FontProperties(family='DejaVu Sans')
