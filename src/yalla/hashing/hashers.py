import abc
import random
from xxhash import xxh64_intdigest, xxh32_intdigest


class Hasher(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def hash(self, serialized_item: bytes) -> int:
        pass


class XxHasher64(Hasher):
    def __init__(self, seed=None):
        self.__seed = seed if seed else random.randint(0, 2**32)

    def hash(self, serialized_item):
        return xxh64_intdigest(serialized_item, seed=self.__seed)


class XxHasher32(Hasher):
    def __init__(self, seed=None):
        self.__seed = seed if seed else random.randint(0, 2**16)

    def hash(self, serialized_item):
        return xxh32_intdigest(serialized_item, seed=self.__seed)
