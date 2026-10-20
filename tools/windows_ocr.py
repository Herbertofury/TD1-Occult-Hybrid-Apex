"""Bounded local Windows OCR for captured native game/EA windows."""
import json
import hashlib
import io
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time
from test_profile import unlinked


def original_viewport(observation, requested_scale):
    """Map WinRT's scaled, deskewed word boxes back to captured pixels.

    WinRT BoundingRect is measured on the counter-clockwise rotated image
    when TextAngle is nonzero. Microsoft's OCR sample rotates the overlay
    clockwise around the image centre; apply that same mapping to all corners.
    https://learn.microsoft.com/uwp/api/windows.media.ocr.ocrresult.textangle
    """
    if (not isinstance(observation, dict) or observation.get('ok') is not True or
            type(requested_scale) is not int or requested_scale not in (1, 2)):
        raise ValueError('OCR requires a typed successful bitmap observation.')
    width, height, preprocessing = observation.get('width'), observation.get('height'), observation.get('preprocessing')
    if (type(width) is not int or type(height) is not int or not 0 < width <= 8192 or not 0 < height <= 8192 or
            not isinstance(preprocessing, dict) or preprocessing.get('coordinates') != 'scaled-bitmap' or
            type(preprocessing.get('requested_scale')) is not int or preprocessing['requested_scale'] != requested_scale or
            type(preprocessing.get('scale')) is not int or preprocessing['scale'] not in (1, requested_scale)):
        raise ValueError('OCR scaling/viewport identity is unknown.')
    scale, scaled_width, scaled_height = preprocessing['scale'], preprocessing.get('ocr_width'), preprocessing.get('ocr_height')
    if (type(scaled_width) is not int or type(scaled_height) is not int or
            (scaled_width, scaled_height) != (width * scale, height * scale) or
            scaled_width * scaled_height > 16 * 1024 * 1024):
        raise ValueError('OCR transform dimensions differ from the original viewport.')
    angle = observation.get('text_angle')
    if angle is None:
        angle = 0
    if type(angle) not in (int, float) or not math.isfinite(angle) or not -180 <= angle <= 180:
        raise ValueError('OCR text angle is not a bounded rotation.')
    radians = math.radians(angle)
    cosine, sine = math.cos(radians), math.sin(radians)
    centre_x, centre_y = scaled_width / 2, scaled_height / 2
    lines = observation.get('lines')
    if not isinstance(lines, list) or len(lines) > 8192:
        raise ValueError('OCR line inventory is not bounded.')
    mapped = []
    word_count = 0
    for line in lines:
        if not isinstance(line, dict) or not isinstance(line.get('text'), str) or not isinstance(line.get('words'), list):
            raise ValueError('OCR lines require typed text and word rectangles.')
        words = []
        for word in line['words']:
            word_count += 1
            if word_count > 32768 or not isinstance(word, dict) or not isinstance(word.get('text'), str):
                raise ValueError('OCR word inventory is untyped or oversized.')
            values = [word.get(name) for name in ('x', 'y', 'width', 'height')]
            if any(type(value) not in (int, float) or not -1e6 <= value <= 1e6 or not math.isfinite(value) for value in values):
                raise ValueError('OCR word rectangle requires finite numeric coordinates.')
            x, y, word_width, word_height = values
            if not (0 <= x < x + word_width <= scaled_width and 0 <= y < y + word_height <= scaled_height):
                raise ValueError('OCR word rectangle is outside the scaled bitmap.')
            if angle:
                corners = [(centre_x + cosine * (px-centre_x) - sine * (py-centre_y),
                            centre_y + sine * (px-centre_x) + cosine * (py-centre_y))
                           for px, py in ((x,y),(x+word_width,y),(x,y+word_height),(x+word_width,y+word_height))]
                left, top = max(0,min(p[0] for p in corners)), max(0,min(p[1] for p in corners))
                right, bottom = min(scaled_width,max(p[0] for p in corners)), min(scaled_height,max(p[1] for p in corners))
                if left >= right or top >= bottom:
                    raise ValueError('Rotated OCR word lies outside the captured image.')
                values = (left, top, right-left, bottom-top)
            words.append(dict(word, **{name: value / scale for name, value in zip(('x', 'y', 'width', 'height'), values)}))
        mapped.append(dict(line, words=words))
    return dict(observation, lines=mapped, preprocessing=dict(preprocessing, coordinates='original-viewport'))


def _native_observation(path, scale, timeout=35):
    script = Path(__file__).with_suffix('.ps1')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File', str(script)],
        input=json.dumps({'path': str(path), 'scale': scale}), capture_output=True, text=True,
        encoding='utf-8', timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise ValueError('Windows OCR failed: ' + result.stderr[-1500:])
    return original_viewport(json.loads(result.stdout), scale)


def _home_labels(observation):
    return [' '.join(line['text'].split()).casefold() for line in observation['lines']]


def _home_scale_candidate(observation, require_load=False):
    """Recognize a complete Home context; never infer its missing Load label."""
    labels = _home_labels(observation)
    load_count, new_count = labels.count('load game'), labels.count('new game')
    controls = (load_count == new_count == 1 if require_load else
                load_count <= 1 and new_count <= 1 and load_count + new_count < 2)
    return (labels.count('home') <= 1 and
            controls and all(labels.count(item) == 1 for item in ('marketplace', 'gallery')) and
            sum(labels.count(item) for item in ('resume game', 'iresume game')) == 1 and
            not any(item in labels for item in ('save game?', 'buy now', 'play', 'autosave',
                'this game requires permissions', "you don't have access", 'you don’t have access',
                'get missing packs?', 'get missing packs', 'cancel', 'reset current household')))


def _contrast_candidate(observation):
    labels = _home_labels(observation)
    # A full native Home observation missing only its selected colored label
    # can benefit from one color-only transform. Other surfaces stay untouched.
    anchors = ('marketplace', 'load game', 'new game', 'gallery')
    forbidden = ('save game?', 'buy now', 'expansion pack', 'game pack', 'stuff pack',
                 'this game requires permissions', 'you don’t have access',
                 "you don't have access", 'cancel')
    return ('home' not in labels and all(labels.count(item) == 1 for item in anchors) and
            sum(labels.count(item) for item in ('resume game', 'resume')) == 1 and
            not any(item in labels for item in forbidden))


def _partial_home_candidate(observation, preprocessing_only=False):
    """Permit another pixel observation, never permission to click a control."""
    labels = _home_labels(observation)
    forbidden = ('save game?', 'cannot save', 'buy now', 'expansion pack', 'game pack', 'stuff pack',
                 'get missing packs?', 'get missing packs', 'play save with missing content',
                 'this game requires permissions', 'you don’t have access', "you don't have access", 'cancel')
    # These observed glyph errors permit only a second read of actual pixels.
    # The transformed result and lifecycle button still require exact labels.
    resumes = ('resume game', 'iresume game', 'resume came') if preprocessing_only else ('resume game',)
    return (labels.count('marketplace') == 1 and sum(labels.count(item) for item in resumes) == 1 and
            all(labels.count(item) <= 1 for item in ('home', 'load game', 'new game', 'gallery')) and
            not any(item in labels for item in forbidden))


def _white_home_observation(path, source, primary, scale, started):
    """Recognize real full-frame white glyphs against a busy Home background."""
    from PIL import Image, ImageChops, ImageOps
    with Image.open(io.BytesIO(source)) as image:
        if (image.size != (primary['width'], primary['height']) or
                image.width * image.height > 16 * 1024 * 1024 or getattr(image, 'n_frames', 1) != 1):
            raise ValueError('White-text bitmap dimensions differ from the native capture.')
        red, green, blue = image.convert('RGB').split()
        low = ImageChops.darker(ImageChops.darker(red, green), blue)
        high = ImageChops.lighter(ImageChops.lighter(red, green), blue)
        bright = low.point(lambda value: 255 if value >= 205 else 0)
        neutral = ImageChops.subtract(high, low).point(lambda value: 255 if value <= 32 else 0)
        mask = ImageOps.invert(ImageChops.multiply(bright, neutral))
    # No crop, geometric transform, synthetic label or inferred coordinates.
    with tempfile.TemporaryDirectory(prefix='apex-ocr-') as temporary:
        transformed = Path(temporary) / 'full-frame-white-text.png'
        mask.save(transformed, format='PNG')
        remaining = 35 - (time.monotonic() - started)
        if remaining <= 0 or path.read_bytes() != source:
            raise ValueError('Capture/deadline changed before white-text OCR.')
        fallback = _native_observation(transformed, scale, timeout=remaining)
    if (fallback['width'], fallback['height']) != (primary['width'], primary['height']) or path.read_bytes() != source:
        raise ValueError('Capture/viewport changed during white-text OCR.')
    # All actionable labels must be recognized independently in this one
    # complete frame. Never merge partial observations or repair guessed text.
    accepted = (_home_scale_candidate(fallback, require_load=True) and _partial_home_candidate(fallback))
    evidence = dict(attempted=True, accepted=accepted, transform='full-frame-white-text',
                    source_sha256=hashlib.sha256(source).hexdigest())
    if not accepted:
        return dict(primary, white_text_fallback=dict(evidence, observation=fallback))
    return dict(fallback, raw_observation=primary, white_text_fallback=evidence)


def recognize(path, scale=2):
    if type(scale) is not int or scale not in (1, 2):
        raise ValueError('Use one- or two-times native OCR scaling.')
    if os.name != 'nt':
        raise RuntimeError('Native image OCR requires Windows.')
    path = unlinked(path)
    if not path.is_file() or not 0 < path.stat().st_size <= 32 * 1024 * 1024:
        raise ValueError('Use one bounded local capture.')
    started = time.monotonic()
    source = path.read_bytes()
    if not 0 < len(source) <= 32 * 1024 * 1024:
        raise ValueError('Capture changed outside the bounded image size.')
    primary = _native_observation(path, scale)
    missing_home_load = scale == 2 and _home_scale_candidate(primary)
    if scale == 2 and (not primary['lines'] or missing_home_load):
        # Native two-times OCR can return an empty inventory for the actual
        # apartment picker. Read the identical complete frame at native size;
        # never infer text, crop a target or repeat game input for an OCR miss.
        remaining = 35 - (time.monotonic() - started)
        if remaining <= 0 or path.read_bytes() != source:
            raise ValueError('Capture/deadline changed before native-size OCR fallback.')
        unscaled = _native_observation(path, 1, timeout=remaining)
        if ((unscaled['width'], unscaled['height']) != (primary['width'], primary['height']) or
                path.read_bytes() != source):
            raise ValueError('Capture/viewport changed during native-size OCR.')
        accepted = bool(unscaled['lines']) and (
            not missing_home_load or _home_scale_candidate(unscaled, require_load=True))
        if accepted:
            return dict(unscaled, raw_observation=primary, scaling_fallback={
                'attempted': True, 'accepted': True, 'scale': 1,
                'reason': 'independent-complete-home-load-label' if missing_home_load else 'empty-two-times-inventory',
                'source_sha256': hashlib.sha256(source).hexdigest()})
        if missing_home_load:
            incomplete = dict(primary, scaling_fallback={'attempted': True, 'accepted': False,
                'scale': 1, 'reason': 'native-size-home-not-complete', 'observation': unscaled,
                'source_sha256': hashlib.sha256(source).hexdigest()})
            # A second incomplete reading is not a reason to skip the existing
            # pixel-only fallback. Both prior observations must independently
            # exclude duplicate controls and known dialogs. The transformed
            # frame must still recognize every exact Home control on its own.
            if _partial_home_candidate(primary, True) and _partial_home_candidate(unscaled, True):
                return _white_home_observation(path, source, incomplete, scale, started)
            return incomplete
    if not _contrast_candidate(primary):
        if _partial_home_candidate(primary, True) and not _home_scale_candidate(primary, require_load=True):
            return _white_home_observation(path, source, primary, scale, started)
        return primary
    if path.read_bytes() != source:
        raise ValueError('Capture changed between native OCR and contrast fallback.')
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(source)) as image:
        if (image.size != (primary['width'], primary['height']) or
                image.width * image.height > 16 * 1024 * 1024 or getattr(image, 'n_frames', 1) != 1):
            raise ValueError('Contrast image dimensions differ from the native capture.')
        image.load()
        # No crop, resize, rotation, replacement text or inferred coordinates.
        # WinRT still recognizes the actual full-frame pixels and owns scaling.
        contrast = ImageOps.autocontrast(ImageOps.grayscale(image))
    with tempfile.TemporaryDirectory(prefix='apex-ocr-') as temporary:
        transformed = Path(temporary) / 'grayscale-autocontrast.png'
        contrast.save(transformed, format='PNG')
        if not 0 < transformed.stat().st_size <= 32 * 1024 * 1024:
            raise ValueError('Contrast bitmap exceeds the bounded image size.')
        remaining = 35 - (time.monotonic() - started)
        if remaining <= 0:
            raise ValueError('Windows OCR contrast fallback exceeded its total deadline.')
        fallback = _native_observation(transformed, scale, timeout=remaining)
    if (fallback['width'], fallback['height']) != (primary['width'], primary['height']) or path.read_bytes() != source:
        raise ValueError('Capture/viewport changed during contrast OCR.')
    labels = _home_labels(fallback)
    # Preserve a complete independently recognized frame. Raw duplicates or
    # forbidden dialog labels never enter this fallback in the first place.
    if labels.count('home') != 1 or _contrast_candidate(dict(fallback, lines=[
            line for line in fallback['lines'] if ' '.join(line['text'].split()).casefold() != 'home'])) is not True:
        return dict(primary, contrast_fallback={'attempted': True, 'accepted': False,
                    'transform': 'full-frame-grayscale-autocontrast', 'observation': fallback})
    return dict(fallback, raw_observation=primary, preprocessing=dict(fallback['preprocessing'],
        color_transform='full-frame-grayscale-autocontrast', source_sha256=hashlib.sha256(source).hexdigest()))
