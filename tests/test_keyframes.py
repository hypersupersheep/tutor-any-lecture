import io
import random

from PIL import Image, ImageDraw

from tutor_any_lecture.keyframes import DUPLICATE_BITS, frame_hash, hamming, select_frames

# ---- K2: a perceptual hash written with Pillow ------------------------------------


def slide_a():
    # local helper: a title bar and three text-like bars
    image = Image.new("RGB", (320, 240), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 320, 50], fill=(20, 40, 120))
    for y, width in ((80, 260), (125, 200), (170, 230)):
        draw.rectangle([30, y, 30 + width, y + 20], fill=(90, 90, 90))
    return image


def slide_b():
    # local helper: the same title bar, a figure and a block
    image = Image.new("RGB", (320, 240), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 320, 50], fill=(20, 40, 120))
    draw.ellipse([170, 70, 300, 200], fill=(200, 60, 40))
    draw.rectangle([30, 90, 140, 180], fill=(90, 90, 90))
    return image


def slide_c():
    # local helper: a dark slide with a light triangle
    image = Image.new("RGB", (320, 240), (30, 30, 30))
    ImageDraw.Draw(image).polygon([(0, 240), (320, 0), (320, 240)], fill=(230, 230, 230))
    return image


def checkerboard():
    # local helper: 64x48 pixels alternating between 100 and 110
    image = Image.new("L", (64, 48))
    image.frombytes(bytes(100 if (x + y) % 2 else 110 for y in range(48) for x in range(64)))
    return image


def test_frame_hash_ignores_size_and_jpeg_noise():
    with slide_a() as a:
        h = frame_hash(a)
        with a.resize((640, 480)) as big:
            assert hamming(h, frame_hash(big)) <= 2
        buffer = io.BytesIO()
        a.save(buffer, "JPEG", quality=30)
    buffer.seek(0)
    with Image.open(buffer) as jpeg:
        assert hamming(h, frame_hash(jpeg)) <= 2


def test_frame_hash_tells_different_slides_apart():
    with slide_a() as a, slide_b() as b, slide_c() as c:
        ha, hb, hc = frame_hash(a), frame_hash(b), frame_hash(c)
    assert hamming(ha, hb) > 6
    assert hamming(ha, hc) > 6
    assert hamming(hb, hc) > 6


def test_blank_frames_have_no_hash():
    with Image.new("L", (64, 48), 0) as black:
        assert frame_hash(black) is None
    with Image.new("RGB", (64, 48), (250, 250, 250)) as white:
        assert frame_hash(white) is None
    with checkerboard() as board:
        assert frame_hash(board) is None
    with slide_a() as a:
        h = frame_hash(a)
    assert isinstance(h, int) and 0 <= h < 2**64


# ---- K3: which candidates are kept ---------------------------------------------


def test_near_duplicates_of_any_kept_frame_are_dropped():
    assert DUPLICATE_BITS == 6
    assert select_frames([(0.0, 0), (10.0, 2**64 - 1), (20.0, 7), (30.0, 127)]) == [0, 1, 3]


def test_kept_frames_are_at_least_8_seconds_apart():
    assert select_frames([(0.0, 0), (4.0, 2**64 - 1), (8.0, 2**64 - 1), (14.0, 2**32 - 1)]) == [0, 2]


def test_blank_candidates_are_never_kept():
    assert select_frames([(0.0, None), (10.0, 0), (20.0, None)]) == [1]


def test_at_most_120_frames_spread_over_the_lecture():
    rng = random.Random(13)
    candidates = [(10.0 * k, rng.getrandbits(64)) for k in range(200)]
    kept = select_frames(candidates)
    assert kept == [round(i * 199 / 119) for i in range(120)]
    assert kept[0] == 0 and kept[-1] == 199
