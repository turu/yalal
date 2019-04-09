import pytest
from yalla.streamprocessing.item_filters import BloomFilter, sample_real_false_positive_rate, NaiveFilter


class TestBloomFilter:
    def test_should_add_new_item(self):
        # given
        bloom_filter = BloomFilter(expected_item_count=100000000, target_false_positive_prob=0.01)

        # when
        bloom_filter.add("test_item")

        # then
        assert "test_item" in bloom_filter
        assert "other_item" not in bloom_filter

    def test_should_merge_two_filters(self):
        # given
        lhs = BloomFilter(expected_item_count=100000000, target_false_positive_prob=0.01)
        rhs = BloomFilter(expected_item_count=100000000, target_false_positive_prob=0.01)
        lhs.add("left_item")
        rhs.add("right_item")
        lhs.add("common_item")
        rhs.add("common_item")

        # when
        lhs.merge_with(rhs)

        # then
        assert all(item in lhs for item in ["left_item", "right_item", "common_item"])

    def test_should_keep_false_positive_probability_close_to_target(self):
        # given
        expected_item_count = 1000000
        target_false_positive_prob = 0.01
        tolerance = 1.25
        bloom_filter = BloomFilter(expected_item_count=expected_item_count,
                                   target_false_positive_prob=target_false_positive_prob)
        naive_filter = NaiveFilter(bloom_filter.get_bit_array_size())

        observed_false_positive_fraction, total_items_tested = \
            sample_real_false_positive_rate(bloom_filter, expected_item_count, target_false_positive_prob)
        naive_false_positive_fraction, total_items_tested = \
            sample_real_false_positive_rate(naive_filter, expected_item_count, target_false_positive_prob)

        print("False positive rate was %s out of %s" % (observed_false_positive_fraction, total_items_tested))
        print("Reference false positive rate was %s out of %s" % (naive_false_positive_fraction, total_items_tested))
        assert observed_false_positive_fraction <= target_false_positive_prob * tolerance
        assert observed_false_positive_fraction < naive_false_positive_fraction
