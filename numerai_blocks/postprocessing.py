# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/05_postprocessing.ipynb (unless otherwise specified).

__all__ = ['MeanEnsembler', 'FeatureNeutralizer', 'AwesomePostProcessor']

# Cell
import numpy as np
import pandas as pd
import scipy.stats as sp
from rich import print as rich_print
from sklearn.preprocessing import MinMaxScaler

from .preprocessing import BaseProcessor, display_processor_info
from .dataset import Dataset

# Cell
class MeanEnsembler(BaseProcessor):
    def __init__(self):
        super(MeanEnsembler, self).__init__()

    @display_processor_info
    def transform(self, dataset: Dataset, cols: list, final_col: str, *args, **kwargs) -> Dataset:
        assert final_col.startswith("prediction"), f"final_col name should start with 'prediction'. Got {final_col}"
        dataset.dataf.loc[:, [cols]][final_col] = dataset.dataf.loc[:, cols].mean(axis=1)
        rich_print(f":stew: Ensembled '{cols}' with simple mean and saved in '{final_col}' :stew:")
        return Dataset(**dataset.__dict__)

# Cell
class FeatureNeutralizer(BaseProcessor):
    def __init__(self, proportion=0.5):
        super(FeatureNeutralizer, self).__init__()
        self.proportion = proportion

    @display_processor_info
    def transform(self, dataset: Dataset, feature_names: list, pred_name: str = "prediction"):
        new_col_name = f"{pred_name}_neutralized_{self.proportion}"
        neutralized_preds = dataset.dataf.groupby("era").apply(lambda x: self.normalize_and_neutralize(x, [pred_name], feature_names))
        min_max_scaled_preds = MinMaxScaler().fit_transform(neutralized_preds)
        dataset.dataf.loc[:, new_col_name] = min_max_scaled_preds
        rich_print(f":robot: Neutralized [bold]'{pred_name}'[bold] with proportion [bold]'{self.proportion}'[/bold] :robot:")
        rich_print(f"New neutralized column is named: [bold green]'{new_col_name}'[/bold green]")
        return Dataset(**dataset.__dict__)

    def _neutralize(self, scores, exposures):
        neutral_scores = scores - self.proportion * exposures.dot(np.linalg.pinv(exposures).dot(scores))
        return neutral_scores / scores.std()

    @staticmethod
    def _normalize(dataf: pd.DataFrame):
        normalized_ranks = (dataf.rank(method="first") - 0.5) / len(dataf)
        return sp.norm.ppf(normalized_ranks)

    def normalize_and_neutralize(self, dataf: pd.DataFrame, pred_cols, by):
        # Convert the scores to a normal distribution
        preds, by_matrix = dataf[pred_cols], dataf[by].values
        preds = self._normalize(preds)
        preds = self._neutralize(preds, by_matrix)
        return preds

# Cell
class AwesomePostProcessor(BaseProcessor):
    """
    - TEMPLATE -
    Do some awesome postprocessing.
    """
    def __init__(self, *args, **kwargs):
        super(AwesomePostProcessor, self).__init__()

    @display_processor_info
    def transform(self, dataset: Dataset, *args, **kwargs) -> Dataset:
        # Do processing
        ...
        # Add new column for manipulated data (optional)
        new_column_name = "NEW_COLUMN_NAME"
        dataset.dataf.loc[:, f"prediction_{new_column_name}"] = ...
        return Dataset(**dataset.__dict__)