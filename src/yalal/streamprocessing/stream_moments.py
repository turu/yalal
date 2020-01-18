from __future__ import annotations
import abc
import timeit
import numpy as np
from scipy import stats


class StreamMoments(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def add(self, value: float) -> None:
        pass

    @abc.abstractmethod
    def merge_with(self, other_moments: StreamMoments) -> None:
        pass

    @abc.abstractmethod
    def mean(self) -> float:
        pass

    @abc.abstractmethod
    def variance(self) -> float:
        pass

    @abc.abstractmethod
    def standard_deviation(self) -> float:
        pass

    @abc.abstractmethod
    def skewness(self) -> float:
        pass

    @abc.abstractmethod
    def kurtosis(self) -> float:
        pass


class KeepAllMoments(StreamMoments):
    def __init__(self):
        self.__values = np.array([], dtype=np.float)

    def add(self, value: float) -> None:
        self.__values = np.append(self.__values, value)

    def merge_with(self, other_moments: KeepAllMoments) -> None:
        self.__values = np.append(self.__values, other_moments.__values)

    def mean(self) -> float:
        return self.__values.mean()

    def variance(self) -> float:
        return self.__values.var()

    def standard_deviation(self) -> float:
        return self.__values.std()

    def skewness(self) -> float:
        return stats.skew(self.__values)[0]

    def kurtosis(self) -> float:
        return stats.kurtosis(self.__values)
