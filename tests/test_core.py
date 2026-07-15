import sys, traceback
sys.path.insert(0, ".")
try:
    from src.screen_capture import split_jpeg_frames
    from src.stream_server import make_app

    j1 = b"\xff\xd8JPEG1\xff\xd9"
    j2 = b"\xff\xd8JPEG2\xff\xd9"
    buf = j1 + j2 + b"\xff\xd8partial"
    frames, rem = split_jpeg_frames(buf)
    assert frames == [j1, j2], frames
    assert rem == b"\xff\xd8partial", rem
    frames2, rem2 = split_jpeg_frames(rem + b"\xff\xd9end")
    # FFD9 ends the frame; trailing 'end' correctly remains as remainder.
    assert frames2 == [b"\xff\xd8partial\xff\xd9"], frames2
    assert rem2 == b"end", rem2

    app = make_app()
    n = len(app.router.routes())
    assert n >= 8, n
    print("routes=%d project3 OK" % n)
except Exception:
    traceback.print_exc()
    raise
