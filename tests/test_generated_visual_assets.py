"""Generated artwork must ship as credited, decodable originals."""
from pathlib import Path
import hashlib
import json
from PIL import Image
from src.core.runtime_assets import runtime_data_files
from src.story.script import CREDITS

ROOT = Path(__file__).resolve().parents[1]


def test_generated_visual_assets_are_usable_and_packaged():
    manifest = json.loads((ROOT / 'data/visual_asset_sources.json').read_text(encoding='utf-8'))
    packaged = set(runtime_data_files())
    for entry in manifest['files']:
        path = ROOT / entry['path']
        assert path in packaged
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
        assert entry['prompt'] and entry['usage']
        with Image.open(path) as image:
            image.load()
            assert image.width >= 800 and image.height >= 800
            if '/characters/' in entry['path']:
                assert image.mode == 'RGBA'
                lo, hi = image.getchannel('A').getextrema()
                assert lo == 0 and hi >= 250
                # Both empty space and a substantial visible body must exist.
                histogram = image.getchannel('A').histogram()
                assert histogram[0] > image.width * image.height * .03
                assert sum(histogram[220:]) > image.width * image.height * .10
    words = ' '.join(line for page in CREDITS for line in page.lines)
    assert 'OpenAI 画像生成' in words
    assert 'ブラックホール / 澤口 / カロナール先輩' in words
