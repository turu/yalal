import pytest

from yalla.streamprocessing.item_counters import KeepAllCounter, sample_real_error, HyperLogLog


class TestKeepAllCounter:
    def test_should_add_new_item(self):
        # given
        counter = KeepAllCounter()

        # when
        counter.add("test_item")
        counter.add("test_item")

        # then
        assert counter.unique_count() == 1

    def test_should_merge_two_counters(self):
        # given
        lhs = KeepAllCounter()
        rhs = KeepAllCounter()
        lhs.add("left_item")
        rhs.add("right_item")
        lhs.add("common_item")
        rhs.add("common_item")

        # when
        lhs.merge_with(rhs)

        # then
        assert lhs.unique_count() == 3

    def test_should_produce_exact_results(self):
        # given
        expected_item_count = 1000000
        tolerance = 0.001
        counter = KeepAllCounter()

        # when
        observed_count, error, time_elapsed = sample_real_error(counter, expected_item_count)

        # then
        print("Measured error was %s. Counted %s out of expected %s" % (error, observed_count, expected_item_count))
        print("Test completed in %s sec" % time_elapsed)
        assert observed_count == expected_item_count
        assert error < tolerance


class TestHyperLogLog:
    def test_should_add_new_item_to_small_hll(self):
        # given
        counter = HyperLogLog()

        # when
        counter.add("test_item")
        counter.add("test_item")

        # then
        assert counter.unique_count() == 1

    def test_should_merge_two_small_hlls(self):
        # given
        lhs = HyperLogLog()
        rhs = HyperLogLog()
        lhs.add("left_item")
        rhs.add("right_item")
        lhs.add("common_item")
        rhs.add("common_item")

        # when
        lhs.merge_with(rhs)

        # then
        assert lhs.unique_count() == 3