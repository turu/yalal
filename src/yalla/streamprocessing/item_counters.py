from __future__ import annotations
import abc
import math
import uuid
import random
import timeit
import numpy as np
from bitarray import bitarray

from yalla.hashing.hashers import XxHasher64


class ItemCounter(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def unique_count(self) -> int:
        pass

    @abc.abstractmethod
    def add(self, item: object):
        pass

    @abc.abstractmethod
    def merge_with(self, other_counter: ItemCounter) -> None:
        pass

    @abc.abstractmethod
    def clear(self):
        pass


def serialize_naively(item: object):
    """
    Extremely naive serializer which simply dumps incoming objects to a string
    """
    return repr(item).encode('utf-8')


class KeepAllCounter(ItemCounter):
    def __init__(self) -> None:
        super().__init__()
        self.__items = set()

    def unique_count(self) -> int:
        return len(self.__items)

    def add(self, item: object):
        self.__items.add(item)

    def merge_with(self, other_counter: KeepAllCounter) -> None:
        self.__items = self.__items.union(other_counter.__items)

    def clear(self):
        self.__items.clear()


class HyperLogLog(ItemCounter):
    """
    Implementation of HyperLogLog algorithm described in https://storage.googleapis.com/pub-tools-public-publication-data/pdf/40671.pdf
    Utilizes Linear Counting for small range correction, as described in http://dblab.kaist.ac.kr/Prof/pdf/ACM90_TODS_v15n2.pdf
    """
    DEFAULT_SEED = 2 ** 64 - 59
    DEFAULT_NUMBER_OF_BUCKETS = 1024
    HASH_BIT_SIZE = 64

    def __init__(self,
                 requested_number_of_buckets=DEFAULT_NUMBER_OF_BUCKETS,
                 serializer=None,
                 seed=DEFAULT_SEED) -> None:
        super().__init__()
        # the number of buckets (b) must be a power of two, because p-bit prefix of every hash decides the bucket
        # for a given item. So there there must be b = 2^p buckets so that every possible prefix has a
        # corresponding bucket
        self.__number_of_buckets = self.__calculate_nearest_power_of_two(requested_number_of_buckets)
        self.__bucket_prefix_length = int(math.log2(self.__number_of_buckets))
        # we want to extract first p bits of each hash so we need an AND mask of the form: '1' * N <=> bin(2^p - 1)
        self.__bucket_prefix_mask = (1 << self.__bucket_prefix_length) - 1

        # each bucket contains an 8-bit number which holds the length of the longest all-zeroes prefix among all items
        # belonging to that bucket. 8 bits are enough because they allow to express values up to 255, which means
        # that it can track hashes with 255 leading zeros -> 2^255 / 255-bit hashes. It's more than enough
        self.__buckets = np.zeros(self.__number_of_buckets, dtype=np.int8)

        self.__hasher = XxHasher64(seed)
        self.__serializer = serializer if serializer else serialize_naively

        self.__bucket_activations = bitarray(self.__number_of_buckets)
        self.__bucket_activations.setall(False)
        self.__number_of_activated_buckets = 0
        # 2.5 factor is the recommended Linear Counting load factor as per Flajolet et al
        self.__small_range_correction_threshold = 2.5 * self.__number_of_buckets
        self.__bias_correction_factor = self.__calculate_bias_correction_factor(self.__number_of_buckets)
        print("Initialized HyperLogLog with %s buckets and %s bits of storage" %
              (self.__number_of_buckets, self.get_size_in_bits()))

    @staticmethod
    def __calculate_nearest_power_of_two(requested_number_of_buckets):
        return math.ceil(requested_number_of_buckets / 2) * 2

    @staticmethod
    def __calculate_bias_correction_factor(number_of_buckets):
        """
        Calculate a factor to correct bias caused by hash collisions, introduced as per empirically obtained values
        from the paper
        """
        if number_of_buckets <= 16:
            return 0.673
        elif number_of_buckets <= 32:
            return 0.697
        elif number_of_buckets <= 64:
            return 0.709
        else:
            return 0.7213 / (1 + 1.079/number_of_buckets)

    def unique_count(self) -> int:
        """
        (1) At scale (once the HLL is reasonably saturated), each of (b) buckets holds approximately 1/b of input items.
        Each bucket in isolation, estimates cardinality of a random sample of 1/b of input items.

        (2) Cardinality of each bucket sample (i) is estimated to be equal to 2^z_i, where z_i is the longest run of
        leading zeros (excluding the bucket-selecting p-bit prefix; note that b = 2^p) of any item belonging to bucket i

        To calculate cardinality of the whole input set, we take an average of per-bucket estimates from (2) and
        scale it to the whole input set by multiplying it by the number of buckets. This is acceptable thanks to (1).

        Harmonic mean is used, because it's very good at smoothing drastic outliers. This helps avoid producing a
        grossly overinflated final estimate.

        (3) When the HLL is not yet saturated with items (some buckets were not used yet; activation threshold was not
        reached), using (1) and (2) could strongly over-estimate the cardinality of the input set (not enough data
        for the beauty of averages at scale to kick in). In that case, an arguably better estimate is to apply Linear
        Counting algorithm, which approximates the number of unique items based on the fraction of activated buckets.
        The estimate distinct count is equal to -b * log e_n, where e_n denotes the fraction of empty buckets
        """
        raw_estimate = self.__bias_correction_factor * self.__number_of_buckets * self.__harmonic_mean_of_bucket_estimates()
        if raw_estimate > self.__small_range_correction_threshold:
            return raw_estimate
        return self.__small_range_liner_counting_estimate(raw_estimate)

    def __harmonic_mean_of_bucket_estimates(self):
        """
        Calculate harmonic mean of bucket estimates of the form 2^z_i following the usual formula for harmonic mean.
        """
        return self.__number_of_activated_buckets / np.sum(1 / (2 ** self.__buckets))

    def __small_range_liner_counting_estimate(self, raw_estimate):
        deactivated_buckets = self.__number_of_buckets - self.__number_of_activated_buckets
        if deactivated_buckets == 0:
            # we cannot use Linear Counting approximation since all buckets are already used (occupancy factor == 1)
            return raw_estimate
        fraction_of_deactivated_buckets = deactivated_buckets / self.__number_of_buckets
        return -self.__number_of_buckets * math.log(fraction_of_deactivated_buckets)

    def add(self, item: object):
        # hash the item and calculate target bucket id
        serialized_item = self.__serializer(item)
        hashed_item = self.__hasher.hash(serialized_item)
        bucket_id = hashed_item & self.__bucket_prefix_mask

        if not self.__bucket_activations[bucket_id]:
            self.__bucket_activations[bucket_id] = True
            self.__number_of_activated_buckets += 1

        # strip bucket prefix from the hash - it's not needed anymore
        hash_without_bucket_prefix = hashed_item >> self.__bucket_prefix_length
        leading_zeros = self.__calculate_number_of_leading_zeros(hash_without_bucket_prefix)
        # update max number of leading zeros in bucket
        self.__buckets[bucket_id] = max(self.__buckets[bucket_id], leading_zeros)

    def __calculate_number_of_leading_zeros(self, integer: int) -> int:
        if integer == 0:
            return self.HASH_BIT_SIZE - self.__bucket_prefix_length
        leading_zeros = 0
        while integer & 1 == 0:
            leading_zeros += 1
            integer >>= 1
        return leading_zeros

    def merge_with(self, other_counter: HyperLogLog) -> None:
        assert self.__number_of_buckets == other_counter.__number_of_buckets
        assert self.__bucket_prefix_length == other_counter.__bucket_prefix_length
        self.__buckets = np.maximum(self.__buckets, other_counter.__buckets)
        self.__bucket_activations |= other_counter.__bucket_activations
        self.__number_of_activated_buckets = self.__bucket_activations.count(True)

    def clear(self):
        self.__buckets.fill(0)
        self.__bucket_activations.setall(False)
        self.__number_of_activated_buckets = 0

    def get_size_in_bits(self):
        return self.__buckets.nbytes * 8 + self.__bucket_activations.length()


def sample_real_error(item_counter: ItemCounter, unique_item_count, total_items_to_test=None):
    total_items_to_test = total_items_to_test if total_items_to_test else 2 * unique_item_count
    items = [uuid.uuid4() for _ in range(unique_item_count)]
    test_set = items + random.choices(items, k=total_items_to_test - unique_item_count)

    start_time = timeit.default_timer()
    for item in test_set:
        item_counter.add(item)
    observed_count = item_counter.unique_count()
    end_time = timeit.default_timer()
    error = math.fabs((observed_count - unique_item_count) / unique_item_count)

    return observed_count, error, end_time - start_time
