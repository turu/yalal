from __future__ import annotations
import abc
import math
import uuid
import random
import timeit


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
