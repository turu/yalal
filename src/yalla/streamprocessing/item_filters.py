from __future__ import annotations
import abc
import logging
import math
import uuid
import random

from bitarray import bitarray

from yalla.hashing.hashers import XxHasher64, XxHasher32


class ItemFilter(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __contains__(self, item: object) -> bool:
        pass

    @abc.abstractmethod
    def add(self, item: object):
        pass

    @abc.abstractmethod
    def merge_with(self, other_filter: ItemFilter) -> None:
        pass

    @abc.abstractmethod
    def clear(self):
        pass


class ShrinkableFilter(ItemFilter, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def delete(self, item: object):
        pass


def serialize_naively(item: object):
    """
    Extremely naive serializer which simply dumps incoming objects to a string
    """
    return repr(item)


class KeepAllFilter(ShrinkableFilter):
    def __init__(self) -> None:
        super().__init__()
        self.__items = set()

    def __contains__(self, item: object) -> bool:
        return item in self.__items

    def add(self, item: object):
        self.__items.add(item)

    def merge_with(self, other_filter: KeepAllFilter) -> None:
        self.__items = self.__items.union(other_filter.__items)

    def delete(self, item: object):
        self.__items.remove(item)

    def clear(self):
        self.__items.clear()


class NaiveFilter(ItemFilter):
    """
    Naive, bit array based filter implementation. Space and memory efficient, but inaccurate
    """
    DEFAULT_SEED = 2 ** 20 - 3

    def __init__(self, bit_array_size, serializer=None, seed=DEFAULT_SEED) -> None:
        super().__init__()
        self.__size = bit_array_size
        self.__bit_array = bitarray(bit_array_size)
        self.clear()
        self.__serializer = serializer if serializer else serialize_naively
        self.__hasher = XxHasher64(seed)

    def __contains__(self, item: object) -> bool:
        serialized_item = self.__serializer(item)
        lookup_position = self.__hasher.hash(serialized_item) % self.__size
        return self.__bit_array[lookup_position]

    def add(self, item: object):
        serialized_item = self.__serializer(item)
        lookup_position = self.__hasher.hash(serialized_item) % self.__size
        self.__bit_array[lookup_position] = True

    def merge_with(self, other_filter: NaiveFilter) -> None:
        assert self.__size == other_filter.__size
        self.__bit_array |= other_filter.__bit_array

    def clear(self):
        self.__bit_array.setall(False)


class BloomFilter(ItemFilter):
    """
    Implementation of Bloom Filter utilizing Enhanced Double Hashing Scheme described in
    https://www.eecs.harvard.edu/~michaelm/postscripts/rsa2008.pdf.
    """
    # Taking a leap of faith here and assuming that 2 instances of XxHash64 are independent given different seeds
    DEFAULT_SEEDS = (2 ** 20 - 3, 2 ** 64 - 59)

    def __init__(self, expected_item_count, target_false_positive_prob, serializer=None, seeds=DEFAULT_SEEDS) -> None:
        super().__init__()
        self.__logger = logging.getLogger(BloomFilter.__name__)
        self.__size = self.__calculate_bit_array_size(expected_item_count, target_false_positive_prob)
        self.__number_of_hashers = self.__calculate_number_of_hashing_functions(target_false_positive_prob)
        self.__bit_array = bitarray(self.__size)
        self.clear()
        self.__serializer = serializer if serializer else serialize_naively
        self.__hashers = [XxHasher64(seed) for seed in seeds]
        self.__logger.info("Initialized bloom filter with %s-bit array, target false positive prob. %s "
                           "and %s hashing functions", self.__size, target_false_positive_prob, self.__number_of_hashers)

    @staticmethod
    def __calculate_number_of_hashing_functions(target_false_positive_prob):
        """
        False positive probability (p) after adding all expected items is equal to:
        p = [1 - (1 - 1/m)^kn]^k  ~  (1 - e^-kn/m)^k
        where:
          * n - expected number of items
          * k - number of hash functions
          * m - size of bit array

        We can then find the minimum of this function with regard to k - number of hash functions. It is minimized when
        k = m/n * ln(2).

        After substituting m (see __calculate_bit_array_size) we arrive at the final formula: k = -log2(p).
        """
        return math.ceil(-1. * math.log2(target_false_positive_prob))

    @staticmethod
    def __calculate_bit_array_size(expected_item_count, target_false_positive_prob):
        """
        Formula for false positive probability (p) described above can be solved for m, after substituting k to arrive at:
        m = -n * ln(p) / log2(2)^2
        """
        return math.ceil(-1. * expected_item_count * math.log(target_false_positive_prob) / (math.log(2) ** 2))

    def __contains__(self, item: object) -> bool:
        serialized_item = self.__serializer(item)
        return all([self.__bit_at_ith_hash(hash_number, serialized_item)
                    for hash_number in range(self.__number_of_hashers)])

    def __bit_at_ith_hash(self, hash_number, serialized_item) -> bool:
        base_hashes = [hasher.hash(serialized_item) for hasher in self.__hashers]
        lookup_position = self.__calculate_lookup_position(base_hashes, hash_number)
        return self.__bit_array[lookup_position]

    def add(self, item: object):
        serialized_item = self.__serializer(item)
        base_hashes = [hasher.hash(serialized_item) for hasher in self.__hashers]
        for hash_number in range(self.__number_of_hashers):
            lookup_position = self.__calculate_lookup_position(base_hashes, hash_number)
            self.__bit_array[lookup_position] = True

    def __calculate_lookup_position(self, base_hashes, hash_number) -> int:
        """
        Calculates lookup position according to the enhanced double hashing formula: (h1(u) + i * h2(u) + i^2) mod m
        where:
          * u - item to be hashed;
          * h1, h2 - two independent, random hashing functions;
          * i - ith hashing function
          * m - size of bit array
        """
        lookup_position = (base_hashes[0] + hash_number * base_hashes[1] + hash_number ** 2) % self.__size
        return lookup_position

    def merge_with(self, other_filter: BloomFilter) -> None:
        assert self.__size == other_filter.__size
        self.__bit_array |= other_filter.__bit_array

    def clear(self):
        self.__bit_array.setall(False)

    def get_bit_array_size(self):
        return self.__bit_array.length()


class CuckooInsertionFailure(Exception):
    """
    Unlike Bloom Filter, Cuckoo Filter can fail to insert a new item due to being full. When faced with such situation
    an implementer can either decide to loose information by removing an item to make place for the new one, or raise an
    exception.
    """
    pass


class CuckooFilter(ShrinkableFilter):
    """
    Implementation of Cuckoo hashing table-based filter as described in
    http://www.eecs.harvard.edu/~michaelm/postscripts/cuckoo-conext2014.pdf
    """
    # Taking a leap of faith here and assuming that instances of XxHash are independent given different seeds
    DEFAULT_SEEDS = (2 ** 11 - 9, 2 ** 20 - 3)
    DEFAULT_ITEMS_PER_BUCKET = 4
    DEFAULT_MAX_ITEM_RELOCATIONS = 2 ** 10
    MAX_FINGERPRINT_SIZE = 32

    def __init__(self, expected_item_count,
                 target_total_size,
                 target_false_positive_prob,
                 items_per_bucket=DEFAULT_ITEMS_PER_BUCKET,
                 max_item_relocations=DEFAULT_MAX_ITEM_RELOCATIONS,
                 fingerprint_size=None,
                 serializer=None,
                 seeds=DEFAULT_SEEDS) -> None:
        super().__init__()
        assert len(seeds) >= 2
        self.__logger = logging.getLogger(CuckooFilter.__name__)
        self.__fingerprint_size = fingerprint_size if fingerprint_size else \
            self.__calculate_fingerprint_size(expected_item_count, target_false_positive_prob, items_per_bucket)
        self.__max_items_per_bucket = items_per_bucket
        self.__bucket_size = self.__max_items_per_bucket * self.__fingerprint_size
        self.__number_of_buckets = math.floor(target_total_size / self.__bucket_size)
        self.__bucket_size = self.__max_items_per_bucket * self.__fingerprint_size
        self.__total_size = self.__number_of_buckets * self.__bucket_size
        self.__max_item_relocations = max_item_relocations

        self.__serializer = serializer if serializer else serialize_naively
        self.__fingerprinting_hasher = XxHasher32(seeds[0])
        self.__hasher = XxHasher64(seeds[1])

        self.__bit_array = bitarray(self.__total_size, endian='little')
        # WARN: since this is a reference/educational implementation, we are ok with cheating slightly and keeping
        # bucket-item counts in a separate list. In a more refined implementation these counts should be encoded
        # in the main table storage
        self.__current_items_per_bucket = [0] * self.__number_of_buckets
        # we want to extract N bits of fingerprint so we need an AND mask of the form: '1' * N <=> bin(2^N - 1)
        self.__fingerprint_mask = (1 << self.__fingerprint_size) - 1
        self.__logger.info("Initialized Cuckoo Filter with %s-bit array, target false positive prob. %s, "
                           "fingerprint size %s, max items per bucket %s, number of buckets %s "
                           "and max item relocations %s", self.__total_size, target_false_positive_prob,
                           self.__fingerprint_size, self.__max_items_per_bucket, self.__number_of_buckets,
                           self.__max_item_relocations)

    @classmethod
    def __calculate_fingerprint_size(cls, expected_item_count, target_false_positive_prob, items_per_bucket):
        return \
            min(cls.MAX_FINGERPRINT_SIZE,
                math.ceil(max(
                    cls.__fingerprint_lower_bound_for_expected_item_count(expected_item_count, items_per_bucket),
                    cls.__fingerprint_lower_bound_for_target_false_positive_prob(target_false_positive_prob, items_per_bucket)
                ))
            )

    @classmethod
    def __fingerprint_lower_bound_for_expected_item_count(cls, expected_item_count, items_per_bucket):
        return math.log(expected_item_count / items_per_bucket)

    @classmethod
    def __fingerprint_lower_bound_for_target_false_positive_prob(cls, target_false_positive_prob, items_per_bucket):
        return math.log2(items_per_bucket / target_false_positive_prob)

    def __contains__(self, item: object) -> bool:
        serialized_item = self.__serializer.serialize(item)
        fingerprint = self.__fingerprint(serialized_item)
        locations = self.__get_locations(serialized_item, fingerprint)
        return any([self.__get_item_id_in_bucket(location, fingerprint) >= 0 for location in locations])

    def __get_item_id_in_bucket(self, bucket_id, fingerprint):
        for item_id in range(self.__current_items_per_bucket[bucket_id]):
            item = self.__get_item(bucket_id, item_id)
            if item == fingerprint:
                return item_id
        return -1

    def __get_locations(self, serialized_item, fingerprint):
        location1 = self.__hasher.hash(serialized_item) % self.__number_of_buckets
        location2 = (location1 ^ self.__hasher.hash(fingerprint)) % self.__number_of_buckets
        return [location1, location2]

    def __fingerprint(self, serialized_item):
        raw_fingerprint = self.__fingerprinting_hasher.hash(serialized_item)
        fingerprint_bits = raw_fingerprint & self.__fingerprint_mask
        return fingerprint_bits

    def add(self, item: object):
        serialized_item = self.__serializer.serialize(item)
        fingerprint = self.__fingerprint(serialized_item)
        locations = self.__get_locations(serialized_item, fingerprint)
        available_locations = [location for location in locations if self.__is_bucket_available(location)]
        if len(available_locations) > 0:
            self.__append_item_to_bucket(locations[0], fingerprint)
            return
        current_location = random.choice(locations)
        item_relocations = 0
        while item_relocations < self.__max_item_relocations:
            fingerprint = self.__swap_with_random_item_from_bucket(current_location, fingerprint)
            current_location = (current_location ^ self.__hasher.hash(fingerprint)) % self.__number_of_buckets
            if self.__is_bucket_available(current_location):
                self.__append_item_to_bucket(current_location, fingerprint)
                return
            item_relocations += 1
        raise CuckooInsertionFailure("CuckooFilter is full. Increase max_item_relocations or target_total_size")

    def __swap_with_random_item_from_bucket(self, bucket_id, fingerprint):
        id_to_swap = random.randrange(0, self.__current_items_per_bucket[bucket_id])
        item_to_swap = self.__get_item(bucket_id, id_to_swap)
        self.__set_item(bucket_id, id_to_swap, fingerprint)
        return item_to_swap

    def __is_bucket_available(self, bucket_id):
        return self.__current_items_per_bucket[bucket_id] < self.__max_items_per_bucket

    def __append_item_to_bucket(self, bucket_id, fingerprint):
        self.__set_item(bucket_id, self.__current_items_per_bucket[bucket_id], fingerprint)
        self.__current_items_per_bucket[bucket_id] += 1

    def __get_item(self, bucket_id, item_id):
        item_start, item_end = self.__item_bit_coordinates(bucket_id, item_id)
        return self.__bit_array_to_int(self.__bit_array[item_start:item_end])

    @staticmethod
    def __bit_array_to_int(bit_array):
        integer = 0
        for bit in bit_array:
            integer = (integer << 1) | bit
        return integer

    def __set_item(self, bucket_id, item_id, fingerprint):
        item_start, item_end = self.__item_bit_coordinates(bucket_id, item_id)
        fingerprint_bits = format(fingerprint, '0%sb' % self.__fingerprint_size)
        self.__bit_array[item_start, item_end] = bitarray(fingerprint_bits, endian='little')

    def __item_bit_coordinates(self, bucket_id, item_id):
        item_start = bucket_id * self.__bucket_size + item_id * self.__fingerprint_size
        item_end = item_start + self.__fingerprint_size
        return item_start, item_end

    def clear(self):
        self.__bit_array.setall(False)

    def merge_with(self, other_filter: CuckooFilter) -> None:
        raise NotImplementedError("Oops, Cuckoo Filters are not easily composable. Consider using Bloom Filter instead")

    def delete(self, item: object):
        serialized_item = self.__serializer.serialize(item)
        fingerprint = self.__fingerprint(serialized_item)
        locations = self.__get_locations(serialized_item, fingerprint)
        for location in locations:
            item_id = self.__get_item_id_in_bucket(location, fingerprint)
            if item_id >= 0:
                last_item_in_bucket = self.__get_item(location, self.__current_items_per_bucket[location] - 1)
                self.__set_item(location, item_id, last_item_in_bucket)
                self.__current_items_per_bucket[location] -= 1


def sample_real_false_positive_rate(item_filter: ItemFilter, expected_item_count, target_false_positive_prob):
    total_items_to_test = math.ceil(10 / target_false_positive_prob)
    items_in_filter = [uuid.uuid4() for _ in range(expected_item_count)]
    items_not_in_filter = [uuid.uuid4() for _ in range(total_items_to_test)]

    for item in items_in_filter:
        item_filter.add(item)

    false_positive_counts = sum([1 for test_item in items_not_in_filter if test_item in item_filter])
    observed_false_positive_fraction = false_positive_counts / total_items_to_test
    return observed_false_positive_fraction, total_items_to_test
