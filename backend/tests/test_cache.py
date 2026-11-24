from datetime import timedelta

from app.data.cache import FileCache
from app.utils.timing import utc_now


def test_write_then_read_fresh(tmp_path):
    cache = FileCache(tmp_path)
    cache.write("prices", "RELIANCE.NS_1y", [{"a": 1}])
    data, fetched_at = cache.read("prices", "RELIANCE.NS_1y", timedelta(hours=1))
    assert data == [{"a": 1}] and fetched_at.tzinfo is not None


def test_expired_entry_is_a_miss(tmp_path):
    cache = FileCache(tmp_path)
    cache.write("news", "k", {"x": 1}, fetched_at=utc_now() - timedelta(hours=2))
    assert cache.read("news", "k", timedelta(hours=1)) is None


def test_corrupt_entry_is_a_miss(tmp_path):
    cache = FileCache(tmp_path)
    path = cache._path("news", "k")
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    assert cache.read("news", "k", timedelta(hours=1)) is None


def test_keys_cannot_escape_cache_dir(tmp_path):
    cache = FileCache(tmp_path)
    path = cache._path("../..", "../../etc/passwd")
    assert tmp_path in path.resolve().parents
    assert cache._path("prices", "^NSEI").name == "_NSEI.json"


def test_concurrent_writes_of_the_same_key(tmp_path):
    """Phase 12: parallel requests for the same data must not fail (Windows rename lock)."""
    import threading

    cache = FileCache(tmp_path)
    errors = []

    def write(i):
        try:
            cache.write("prices", "_NSEI_2y", [{"close": i}])
        except Exception as exc:  # pragma: no cover - the failure being tested
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert cache.read("prices", "_NSEI_2y", timedelta(hours=1)) is not None
    assert not list((tmp_path / "prices").glob("*.tmp"))
