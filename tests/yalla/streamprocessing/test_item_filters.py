import pytest
from yalla.streamprocessing.item_filters import BloomFilter


def test_should_add_new_item():
    # given
    bloom_filter = BloomFilter(expected_item_count=1000000, target_false_positive_prob=0.01)

    # when
    bloom_filter.add("test_item")

    # then
    assert "test_item" in bloom_filter
