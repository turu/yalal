from __future__ import annotations
import abc
import logging
import math
import uuid

from bitarray import bitarray

from yalla.hashing.hashers import XxHasher


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


def serialize_naively(item: object):
    """
    Extremely naive serializer which simply dumps incoming objects to a string
    """
    return repr(item)


class KeepAllFilter(ItemFilter):
    def __init__(self) -> None:
        super().__init__()
        self.__items = set()

    def __contains__(self, item: object) -> bool:
        return item in self.__items

    def add(self, item: object):
        self.__items.add(item)

    def merge_with(self, other_filter: KeepAllFilter) -> None:
        self.__items = self.__items.union(other_filter.__items)

    def clear(self):
        self.__items.clear()


class NaiveFilter(ItemFilter):
    """
    Naive, bit array based filter implementation. Space and memory efficient, but inaccurate
    """
    DEFAULT_SEED = 2**20 - 3

    def __init__(self, bit_array_size, serializer=None, seed=DEFAULT_SEED) -> None:
        super().__init__()
        self.__size = bit_array_size
        self.__bit_array = bitarray(bit_array_size)
        self.clear()
        self.__serializer = serializer if serializer else serialize_naively
        self.__hasher = XxHasher(seed)

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
    DEFAULT_SEEDS = (2**20 - 3, 2**64 - 59)

    def __init__(self, expected_item_count, target_false_positive_prob, serializer=None, seeds=DEFAULT_SEEDS) -> None:
        super().__init__()
        self.__logger = logging.getLogger(BloomFilter.__name__)
        self.__size = self.__calculate_bit_array_size(expected_item_count, target_false_positive_prob)
        self.__number_of_hashers = self.__calculate_number_of_hashing_functions(target_false_positive_prob)
        self.__bit_array = bitarray(self.__size)
        self.clear()
        self.__serializer = serializer if serializer else serialize_naively
        self.__hashers = [XxHasher(seed) for seed in seeds]
        self.__logger.info("Initialized bloom filter with %s-bit array and %s hashing functions", self.__size,
                           self.__number_of_hashers)

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


def sample_real_false_positive_rate(item_filter: ItemFilter, expected_item_count, target_false_positive_prob):
    total_items_to_test = math.ceil(10 / target_false_positive_prob)
    items_in_filter = [uuid.uuid4() for _ in range(expected_item_count)]
    items_not_in_filter = [uuid.uuid4() for _ in range(total_items_to_test)]

    for item in items_in_filter:
        item_filter.add(item)

    false_positive_counts = sum([1 for test_item in items_not_in_filter if test_item in item_filter])
    observed_false_positive_fraction = false_positive_counts / total_items_to_test
    return observed_false_positive_fraction, total_items_to_test
