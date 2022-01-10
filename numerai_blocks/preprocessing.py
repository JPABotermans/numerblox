# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/03_preprocessing.ipynb (unless otherwise specified).

__all__ = ['BaseProcessor']

# Cell
import uuid
import inspect
import numpy as np
import pandas as pd
from functools import wraps
from typeguard import typechecked
from abc import ABC, abstractmethod

from .dataset import Dataset

# Cell
@typechecked
class BaseProcessor(ABC):
    def __init__(self):
        ...

    @abstractmethod
    def transform(self, dataset: Dataset) -> Dataset:
        ...

    def __call__(self, dataset: Dataset) -> Dataset:
        return self.transform(dataset=dataset)