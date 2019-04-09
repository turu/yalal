from __future__ import annotations
import abc
import logging
import math
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


class NaiveFilter(ItemFilter):
    def __init__(self) -> None:
        super().__init__()
        self.__items = set()

    def __contains__(self, item: object) -> bool:
        return item in self.__items

    def add(self, item: object):
        self.__items.add(item)

    def merge_with(self, other_filter: NaiveFilter) -> None:
        self.__items = self.__items.union(other_filter.__items)

    def clear(self):
        self.__items.clear()


class BloomFilter(ItemFilter):
    def __init__(self, expected_item_count, target_false_positive_prob, serializer=None) -> None:
        super().__init__()
        self.__logger = logging.getLogger(BloomFilter.__name__)
        self.__size = self.calculate_bit_array_size(expected_item_count, target_false_positive_prob)
        self.__number_of_hashers = self.calculate_number_of_hashing_functions(target_false_positive_prob)
        self.__bit_array = bitarray(self.__size)
        self.__bit_array.setall(False)
        self.__serializer = serializer if serializer else self.__naive_serializer
        self.__hashers = [XxHasher(), XxHasher()]
        self.__logger.info("Initialized bloom filter with %s-bit array and %s hashing functions", self.__size,
                            self.__number_of_hashers)

    @staticmethod
    def calculate_bit_array_size(expected_item_count, target_false_positive_prob):
        return math.ceil(-1. * expected_item_count * math.log(target_false_positive_prob) / (math.log(2) ** 2))

    @staticmethod
    def calculate_number_of_hashing_functions(target_false_positive_prob):
        return math.ceil(-1. * math.log2(target_false_positive_prob))

    @classmethod
    def __naive_serializer(cls, item: object) -> str:
        """
        Extremely naive serializer which simply dumps incoming objects to a string
        :param item:
        :return:
        """
        return repr(item)

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
        lookup_position = (base_hashes[0] + hash_number * base_hashes[1] + hash_number ** 2) % self.__size
        return lookup_position

    def merge_with(self, other_filter: BloomFilter) -> None:
        assert self.__size == other_filter.__size
        self.__bit_array |= other_filter.__bit_array

    def clear(self):
        self.__bit_array.setall(False)
