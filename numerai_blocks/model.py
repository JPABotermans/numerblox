# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/04_model.ipynb (unless otherwise specified).

__all__ = ['BaseModel', 'DirectoryModel', 'SingleModel', 'WandbKerasModel', 'JoblibModel', 'CatBoostModel', 'LGBMModel',
           'ConstantModel', 'RandomModel', 'AwesomeModel', 'AwesomeDirectoryModel']

# Cell
import gc
import uuid
import wandb
import joblib
import pickle
import numpy as np
import pandas as pd
import lightgbm as lgb
import tensorflow as tf
from pathlib import Path
from typing import Union
from tqdm.auto import tqdm
from functools import partial
from catboost import CatBoost
from typeguard import typechecked
from abc import ABC, abstractmethod
from sklearn.dummy import DummyRegressor

from .numerframe import NumerFrame, create_numerframe
from .preprocessing import display_processor_info

# Cell
class BaseModel(ABC):
    """
    Setup for model prediction on a Dataset.

    :param model_directory: Main directory from which to read in models.
    :param model_name: Name that will be used to create column names and for display purposes.
    """
    def __init__(self, model_directory: str, model_name: str = None):
        self.model_directory = Path(model_directory)
        self.model_name = model_name if model_name else uuid.uuid4().hex
        self.prediction_col_name = f"prediction_{self.model_name}"
        self.description = f"{self.__class__.__name__}: '{self.model_name}' prediction"

    @abstractmethod
    def predict(self, dataf: Union[pd.DataFrame, NumerFrame]) -> NumerFrame:
        """ Return NumerFrame with column added for prediction. """
        ...
        return NumerFrame(dataf)

    def __call__(self, dataf: Union[pd.DataFrame, NumerFrame]) -> NumerFrame:
        return self.predict(dataf=dataf)

# Cell
class DirectoryModel(BaseModel):
    """
    Base class implementation for JoblibModel, CatBoostModel, LGBMModel, etc.
    Walks through every file with given file_suffix in a directory.
    :param model_directory: Main directory from which to read in models.
    :param file_suffix: File format to load (For example, .joblib, .pkl, .cbm or .lgb)
    :param model_name: Name that will be used to create column names and for display purposes.
    """
    def __init__(self, model_directory: str, file_suffix: str, model_name: str = None):
        super().__init__(model_directory=model_directory,
                         model_name=model_name,
                         )
        self.file_suffix = file_suffix
        self.model_paths = list(self.model_directory.glob(f'*.{self.file_suffix}'))
        if self.file_suffix:
            assert self.model_paths, f"No {self.file_suffix} files found in {self.model_directory}."
        self.total_models = len(self.model_paths)

    @display_processor_info
    def predict(self, dataf: NumerFrame, *args, **kwargs) -> NumerFrame:
        """
        Use all recognized models to make predictions and average them out.
        :param dataf: A Preprocessed DataFrame where all its features can be passed to the model predict method.
        *args, **kwargs will be parsed into the model.predict method.
        :return: A new dataset with prediction column added.
        """
        dataf.loc[:, self.prediction_col_name] = np.zeros(len(dataf))
        models = self.load_models()
        for model in tqdm(models, desc=self.description, position=1):
            predictions = model.predict(dataf.get_feature_data, *args, **kwargs)
            dataf.loc[:, self.prediction_col_name] += predictions / self.total_models
        del models; gc.collect()
        return NumerFrame(dataf)

    @abstractmethod
    def load_models(self) -> list:
        """ Instantiate all models detected in self.model_paths. """
        ...


# Cell
@typechecked
class SingleModel(BaseModel):
    """
    Load single model from file and perform prediction logic.
    :param model_directory: Main directory from which to read in models.
    :param model_name: Name that will be used to create column names and for display purposes.
    :param combine_preds: Whether to average predictions along column axis.
    Convenient when you want to predict the main target by averaging a multi-target model.
    :param autoencoder_mlp: Whether your model is an autoencoder + MLP model.
    Will take the 3rd of tuple output in this case. Only relevant for NN models.
    More info on autoencoders:
    https://forum.numer.ai/t/autoencoder-and-multitask-mlp-on-new-dataset-from-kaggle-jane-street/4338
    """
    def __init__(self, model_file_path: str, model_name: str = None,
                 combine_preds = False, autoencoder_mlp = False):
        self.model_file_path = Path(model_file_path)
        assert self.model_file_path.exists(), f"File path '{self.model_file_path}' does not exist."
        assert self.model_file_path.is_file(), f"File path must point to file. Not valid for '{self.model_file_path}'."
        super().__init__(model_directory=str(self.model_file_path.parent),
                         model_name=model_name,
                         )
        self.model_suffix = self.model_file_path.suffix
        self.suffix_to_model_mapping = {".joblib": joblib.load,
                                        ".cbm": CatBoost().load_model,
                                        ".pkl": pickle.load,
                                        ".pickle": pickle.load,
                                        ".h5": partial(tf.keras.models.load_model, compile=False)
                                        }
        self.__check_valid_suffix()
        self.combine_preds = combine_preds
        self.autoencoder_mlp = autoencoder_mlp

    def predict(self, dataf: NumerFrame, *args, **kwargs) -> NumerFrame:
        model = self._load_model(*args, **kwargs)
        predictions = model.predict(dataf.get_feature_data)
        predictions = predictions[2] if self.autoencoder_mlp else predictions
        predictions = predictions.mean(axis=1) if self.combine_preds else predictions
        prediction_cols = self.get_prediction_col_names(predictions.shape)
        dataf.loc[:, prediction_cols] = predictions
        del model; gc.collect()
        return NumerFrame(dataf)

    def _load_model(self, *args, **kwargs):
        """ Load arbitrary model from path using suffix to model mapping. """
        return self.suffix_to_model_mapping[self.model_suffix](str(self.model_file_path), *args, **kwargs)

    def get_prediction_col_names(self, pred_shape: tuple) -> list:
        """ Create multiple columns if predictions are multi-target. """
        if len(pred_shape) > 1:
            # Multi target
            prediction_cols = [f"{self.prediction_col_name}_{i}" for i in range(pred_shape[1])]
        else:
            # Single target
            prediction_cols = [self.prediction_col_name]
        return prediction_cols

    def __check_valid_suffix(self):
        """ Detailed message if model is not supported in this class. """
        try:
            self.suffix_to_model_mapping[self.model_suffix]
        except KeyError:
            raise NotImplementedError(
                f"Format '{self.model_suffix}' is not available. Available versions are {list(self.suffix_to_model_mapping.keys())}"
            )


# Cell
@typechecked
class WandbKerasModel(SingleModel):
    """
    Load best .h5 model from Weights & Biases (W&B) run and make predictions.
    More info on W&B: https://wandb.ai/site
    :param model_directory: Main directory from which to read in models.
    :param entity_name: Profile or team name (For example 'crowdcent')
    :param project_name: Name of project where run is located (For example, 'numerai-classi').
    :param wandb_run_id: hash of run within given project (For example, '1234abcd')
    Entity, project and id can be found in Overview tab of W&B run.
    :param file_name: Name of .h5 file as saved in W&B run.
    'model-best.h5' by default.
    File name can be found under files tab of W&B run.
    :param combine_preds: Whether to average predictions along column axis.
    Convenient when you want to predict the main target by averaging a multi-target model.
    :param autoencoder_mlp: Whether your model is an autoencoder + MLP model.
    Will take the 3rd of tuple output in this case. Only relevant for NN models.
    More info on autoencoders:
    https://forum.numer.ai/t/autoencoder-and-multitask-mlp-on-new-dataset-from-kaggle-jane-street/4338

    To authenticate your W&B account you are given several options:
    1. Run wandb login in terminal and follow instructions.
    2. Configure global environment variable "WANDB_API_KEY".
    3. Run wandb.init(project=PROJECT_NAME, entity=ENTITY_NAME) and
    pass API key from https://wandb.ai/authorize
    """
    def __init__(self, model_directory: str,
                 entity_name: str,
                 project_name: str,
                 wandb_run_id: str,
                 file_name: str = None,
                 combine_preds = True,
                 autoencoder_mlp = True):
        self.entity_name = entity_name
        self.project_name = project_name
        self.wandb_run_id = wandb_run_id
        self.file_name = file_name

        self.dir = Path(model_directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._download_model()
        super().__init__(model_file_path=self.full_file_path,
                         model_name=wandb_run_id,
                         combine_preds=combine_preds,
                         autoencoder_mlp=autoencoder_mlp
                         )

    @property
    def wandb_path(self) -> str:
        """
        Path for W&B API. Can be found in the Overview tab of a W&B run.
        More info: https://docs.wandb.ai/ref/app/pages/run-page#overview-tab
        """
        return f"{self.entity_name}/{self.project_name}/{self.wandb_run_id}"

    @property
    def full_file_path(self) -> str:
        """ Full path for downloading file. """
        file_name = "model-best.h5" if not self.file_name else self.file_name
        return str(self.dir / file_name)

    def _download_model(self):
        """
        Use W&B API to download file.
        More info on API: https://docs.wandb.ai/guides/track/public-api-guide
        """
        run = wandb.Api().run(self.wandb_path)
        run.file(self.full_file_path).download()

# Cell
@typechecked
class JoblibModel(DirectoryModel):
    """
    Load and predict for arbitrary models in directory saved as .joblib.
    All loaded models should have a .predict method and accept the features present in the data.
    :param model_directory: Main directory from which to read in models.
    :param model_name: Name that will be used to create column names and for display purposes.
    """
    def __init__(self, model_directory: str, model_name: str = None):
        file_suffix = 'joblib'
        super().__init__(model_directory=model_directory,
                         file_suffix=file_suffix,
                         model_name=model_name,
                         )

    def load_models(self) -> list:
        return [joblib.load(path) for path in self.model_paths]

# Cell
@typechecked
class CatBoostModel(DirectoryModel):
    """
    Load and predict with all .cbm models (CatBoostRegressor) in directory.
    :param model_directory: Main directory from which to read in models.
    :param model_name: Name that will be used to create column names and for display purposes.
    """
    def __init__(self, model_directory: str, model_name: str = None):
        file_suffix = 'cbm'
        super().__init__(model_directory=model_directory,
                         file_suffix=file_suffix,
                         model_name=model_name,
                         )

    def load_models(self) -> list:
        return [CatBoost().load_model(path) for path in self.model_paths]

# Cell
@typechecked
class LGBMModel(DirectoryModel):
    """ Load and predict with all .lgb models (LightGBM) in directory. """
    def __init__(self, model_directory: str, model_name: str = None):
        file_suffix = 'lgb'
        super().__init__(model_directory=model_directory,
                         file_suffix=file_suffix,
                         model_name=model_name,
                         )

    def load_models(self) -> list:
        return [lgb.Booster(model_file=str(path)) for path in self.model_paths]

# Cell
class ConstantModel(BaseModel):
    """
    WARNING: Only use this Model for testing purposes.
    Create constant prediction.
    :param constant: Value for constant prediction.
    :param model_name: Name that will be used to create column names and for display purposes.
    """
    def __init__(self, constant: float = 0.5, model_name: str = None):
        self.constant = constant
        model_name = model_name if model_name else f"constant_{self.constant}"
        super().__init__(model_directory="",
                         model_name=model_name
                         )
        self.clf = DummyRegressor(strategy='constant', constant=constant).fit([0.], [0.])

    def predict(self, dataf: NumerFrame) -> NumerFrame:
        dataf.loc[:, self.prediction_col_name] = self.clf.predict(dataf.get_feature_data)
        return NumerFrame(dataf)

# Cell
class RandomModel(BaseModel):
    """
    WARNING: Only use this Model for testing purposes.
    Create uniformly distributed predictions.
    :param model_name: Name that will be used to create column names and for display purposes.
    """
    def __init__(self, model_name: str = None):
        model_name = model_name if model_name else "random"
        super().__init__(model_directory="",
                         model_name=model_name
                         )

    def predict(self, dataf: Union[pd.DataFrame, NumerFrame]) -> NumerFrame:
        dataf.loc[:, self.prediction_col_name] = np.random.uniform(size=len(dataf))
        return NumerFrame(dataf)

# Cell
@typechecked
class AwesomeModel(BaseModel):
    """
    - TEMPLATE -
    Predict with arbitrary prediction logic and model formats.
    """
    def __init__(self, model_directory: str, model_name: str = None):
        super().__init__(model_directory=model_directory,
                         model_name=model_name,
                         )

    @display_processor_info
    def predict(self, dataf: NumerFrame) -> NumerFrame:
        """ Return NumerFrame with column(s) added for prediction(s). """
        # Get all features
        feature_df = dataf.get_feature_data
        # Predict and add to new column
        ...
        # Parse all contents of NumerFrame to the next pipeline step
        return NumerFrame(dataf)

# Cell
@typechecked
class AwesomeDirectoryModel(DirectoryModel):
    """
    - TEMPLATE -
    Load in all models of arbitrary file format and predict for all.
    """
    def __init__(self, model_directory: str, model_name: str = None):
        file_suffix = '.anything'
        super().__init__(model_directory=model_directory,
                         file_suffix=file_suffix,
                         model_name=model_name,
                         )

    def load_models(self) -> list:
        """ Instantiate all models and return as a list. (abstract method) """
        ...