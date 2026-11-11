"""OpCounter / NullCounter behave exactly as the counting definitions say."""

from sortscope.counter import NullCounter, OpCounter


def test_opcounter_counts_each_operation() -> None:
    c = OpCounter()
    arr = [3, 1, 2]
    assert c.less(1, 2) is True
    assert c.less(2, 2) is False  # strict
    c.swap(arr, 0, 1)
    c.write(arr, 2, 9)
    c.note_depth(3)
    c.note_depth(2)
    assert arr == [1, 3, 9]
    assert c.as_dict() == {"comparisons": 2, "swaps": 1, "writes": 3, "max_depth": 3}


def test_nullcounter_acts_but_records_nothing() -> None:
    c = NullCounter()
    arr = [3, 1, 2]
    assert c.less(1, 2) is True
    c.swap(arr, 0, 1)
    c.write(arr, 2, 9)
    c.note_depth(5)
    assert arr == [1, 3, 9]
    assert c.as_dict() == {"comparisons": 0, "swaps": 0, "writes": 0, "max_depth": 0}
    assert isinstance(c, OpCounter)  # usable wherever an OpCounter is expected
