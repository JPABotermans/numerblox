# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/05_postprocessing.ipynb (unless otherwise specified).

__all__ = ['MeanEnsembler', 'FeatureNeutralizer', 'AwesomePostProcessor']

# Cell
import numpy as np
import pandas as pd
import scipy.stats as sp
from typeguard import typechecked
from rich import print as rich_print
from sklearn.preprocessing import MinMaxScaler

from .preprocessing import BaseProcessor, display_processor_info
from .dataset import Dataset

# Cell
@typechecked
class MeanEnsembler(BaseProcessor):
    """ Take simple mean of multiple cols and store in new col. """
    def __init__(self, cols: list, final_col_name: str):
        super(MeanEnsembler, self).__init__()
        self.cols = cols
        self.final_col_name = final_col_name
        assert final_col_name.startswith("prediction"), f"final_col name should start with 'prediction'. Got {final_col_name}"

    @display_processor_info
    def transform(self, dataset: Dataset, *args, **kwargs) -> Dataset:
        dataset.dataf.loc[:, self.final_col_name] = dataset.dataf.loc[:, self.cols].mean(axis=1)
        rich_print(f":stew: Ensembled [blue]'{self.cols}'[blue] with simple mean and saved in [bold]'{self.final_col_name}'[bold] :stew:")
        return Dataset(**dataset.__dict__)

# Cell
@typechecked
class FeatureNeutralizer(BaseProcessor):
    """ Feature """
    def __init__(self, feature_names: list,
                 pred_name: str = "prediction",
                 proportion=0.5):
        super(FeatureNeutralizer, self).__init__()
        self.proportion = proportion
        self.feature_names = feature_names
        self.pred_name = pred_name
        self.new_col_name = f"{self.pred_name}_neutralized_{self.proportion}"

    @display_processor_info
    def transform(self, dataset: Dataset, *args, **kwargs) -> Dataset:
        neutralized_preds = dataset.dataf.groupby("era")\
            .apply(lambda x: self.normalize_and_neutralize(x, [self.pred_name], self.feature_names))
        dataset.dataf.loc[:, self.new_col_name] = MinMaxScaler().fit_transform(neutralized_preds)
        rich_print(f":robot: Neutralized [bold blue]'{self.pred_name}'[bold blue] with proportion [bold]'{self.proportion}'[/bold] :robot:")
        rich_print(f"New neutralized column = [bold green]'{self.new_col_name}'[/bold green].")
        return Dataset(**dataset.__dict__)

    def _neutralize(self, df, columns, by):
        scores = df[columns]
        exposures = df[by].values
        scores = scores - self.proportion * exposures.dot(np.linalg.pinv(exposures).dot(scores))
        return scores / scores.std()

    @staticmethod
    def _normalize(dataf: pd.DataFrame):
        normalized_ranks = (dataf.rank(method="first") - 0.5) / len(dataf)
        return sp.norm.ppf(normalized_ranks)

    def normalize_and_neutralize(self, df, columns, by):
        # Convert the scores to a normal distribution
        df[columns] = self._normalize(df[columns])
        df[columns] = self._neutralize(df, columns, by)
        return df[columns]

# Cell
@typechecked
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
        ...
        # Parse all contents of Dataset to the next pipeline step
        return Dataset(**dataset.__dict__)