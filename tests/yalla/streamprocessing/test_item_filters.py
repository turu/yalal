import pytest
from yalla.streamprocessing.item_filters import BloomFilter, sample_real_false_positive_rate, NaiveFilter, CuckooFilter


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

        # when
        # NOTE that when doing proper comparison we should repeat this procedure many times
        observed_false_positive_fraction, total_items_tested, bloom_time = \
            sample_real_false_positive_rate(bloom_filter, expected_item_count, target_false_positive_prob)
        naive_false_positive_fraction, total_items_tested, naive_time = \
            sample_real_false_positive_rate(naive_filter, expected_item_count, target_false_positive_prob)

        # then
        print("False positive rate was %s out of %s" % (observed_false_positive_fraction, total_items_tested))
        print("Reference false positive rate was %s out of %s" % (naive_false_positive_fraction, total_items_tested))
        print("Bloom test completed in %s sec" % bloom_time)
        print("Reference test completed in %s sec" % naive_time)
        assert observed_false_positive_fraction <= target_false_positive_prob * tolerance
        assert observed_false_positive_fraction < naive_false_positive_fraction


class TestCuckooFilter:
    def test_should_add_new_item(self):
        # given
        cuckoo_filter = CuckooFilter(100000000, 100 * 1024 * 1024 * 8, 0.01)

        # when
        cuckoo_filter.add("test_item")

        # then
        assert "test_item" in cuckoo_filter
        assert "other_item" not in cuckoo_filter

    def test_should_should_delete_item(self):
        # given
        cuckoo_filter = CuckooFilter(100000000, 100 * 1024 * 1024 * 8, 0.01)
        cuckoo_filter.add("test_item")
        cuckoo_filter.add("other_item")

        # when
        cuckoo_filter.delete("test_item")

        # then
        assert "test_item" not in cuckoo_filter
        assert "other_item" in cuckoo_filter

    def test_should_throw_when_attempting_to_merge_since_cuckoo_filters_dont_support_merging(self):
        # given
        cuckoo_filter = CuckooFilter(100000000, 100 * 1024 * 1024 * 8, 0.01)
        other_filter = CuckooFilter(100000000, 100 * 1024 * 1024 * 8, 0.01)

        # when
        with pytest.raises(NotImplementedError):
            cuckoo_filter.merge_with(other_filter)

    def test_should_achieve_comparable_accuracy_to_bloom_filter_at_similar_space_requirements(self):
        # given
        expected_item_count = 1000000
        target_false_positive_prob = 0.01
        tolerance = 2
        bloom_filter = BloomFilter(expected_item_count=expected_item_count,
                                   target_false_positive_prob=target_false_positive_prob)
        # Cuckoo Filter is much harder to tune; 10 is an empirically determined value of fingerprint_size
        cuckoo_filter = CuckooFilter(expected_item_count=expected_item_count,
                                     target_total_size=bloom_filter.get_bit_array_size(),
                                     target_false_positive_prob=target_false_positive_prob,
                                     fingerprint_size=10)

        # when
        # NOTE that when doing proper comparison we should repeat this procedure many times
        observed_false_positive_fraction, total_items_tested, cuckoo_time = \
            sample_real_false_positive_rate(cuckoo_filter, expected_item_count, target_false_positive_prob)
        bloom_false_positive_fraction, total_items_tested, bloom_time = \
            sample_real_false_positive_rate(bloom_filter, expected_item_count, target_false_positive_prob)

        # then
        print("False positive rate was %s out of %s" % (observed_false_positive_fraction, total_items_tested))
        print("Reference false positive rate was %s out of %s" % (bloom_false_positive_fraction, total_items_tested))
        print("Cuckoo test completed in %s sec" % cuckoo_time)
        print("Reference test completed in %s sec" % bloom_time)
        assert observed_false_positive_fraction <= bloom_false_positive_fraction * tolerance
