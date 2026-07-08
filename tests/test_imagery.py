from edgesim.imagery import CropBank, render_strip, split_strip


def test_strip_dimensions_and_split(digits_dir):
    bank = CropBank(digits_dir, seed=1)
    strip = render_strip("12345", bank)
    assert strip.size == (20 * 5, 32)
    crops = split_strip(strip, 5)
    assert len(crops) == 5
    assert all(c.size == (20, 32) for c in crops)


def test_round_trip_reads_back(digits_dir, model_path):
    from edgesim.reader import DigitReader

    bank = CropBank(digits_dir, seed=2)
    reader = DigitReader(model_path)
    strip = render_strip("4071", bank)
    preds = [reader.predict_crop(c) for c in split_strip(strip, 4)]
    read = "".join(str(p.class_index) for p in preds)
    assert read == "4071"  # real crops -> model reads them back


def test_rolling_injects_nan(digits_dir, model_path):
    from edgesim.reader import DigitReader

    bank = CropBank(digits_dir, seed=3)
    reader = DigitReader(model_path)
    strip = render_strip("4071", bank, rolling_index=2)
    preds = [reader.predict_crop(c) for c in split_strip(strip, 4)]
    assert preds[2].class_index == 10  # NaN class at the rolling position
