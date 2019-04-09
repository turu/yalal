import abc
import random
from xxhash import xxh64_intdigest


class Hasher(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def hash(self, serialized_item: str) -> int:
        pass


class XxHasher(Hasher):
    def __init__(self, seed=None):
        self.__seed = seed if seed else random.randint(0, 2**32)

    def hash(self, serialized_item):
        return xxh64_intdigest(serialized_item, seed=self.__seed)
