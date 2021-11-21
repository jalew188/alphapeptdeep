# AUTOGENERATED! DO NOT EDIT! File to edit: nbdev_nbs/model/base.ipynb (unless otherwise specified).

__all__ = ['ModelImplBase']

# Cell
import os
import numpy as np
import pandas as pd
import torch
from tqdm import tqdm

from zipfile import ZipFile
from typing import IO, Tuple, List, Union
from alphabase.yaml_utils import save_yaml
from alphadeep._settings import model_const

from alphadeep.model.building_block import *

# Cell
class ModelImplBase(object):
    def __init__(self, **kwargs):
        self.model = None
        if 'GPU' in kwargs:
            self.use_GPU(kwargs['GPU'])
        else:
            self.use_GPU(True)

    def use_GPU(self, GPU=True):
        if not torch.cuda.is_available():
            GPU=False
        self.device = torch.device('cuda' if GPU else 'cpu')
        if self.model:
            self.model.to(self.device)

    def _init_for_train(self, lr=0.001):
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        self.loss_func = torch.nn.L1Loss()

    def build_from_py_codes(self,
        model_code_file:str,
        code_file_in_zip:str=None,
        lr = 0.001,
        **kwargs
    ):
        if model_code_file.lower().endswith('.zip'):
            with ZipFile(model_code_file, 'r') as model_zip:
                with model_zip.open(code_file_in_zip) as f:
                    codes = f.read()
        else:
            with open(model_code_file, 'r') as f:
                codes = f.read()
        codes = compile(
            codes,
            filename='model_file_py',
            mode='exec'
        )
        exec(codes) #codes must contains torch model codes 'class Model(...'
        self.model = Model(**kwargs)
        self.model_params = kwargs
        self.model.to(self.device)
        self._init_for_train(lr)

    def build(self,
        model_class: torch.nn.Module,
        lr = 0.001,
        **kwargs
    ):
        self.model = model_class(**kwargs)
        self.model_params = kwargs
        self.model.to(self.device)
        self._init_for_train(lr)

    def get_parameter_num(self):
        return np.sum([p.numel() for p in self.model.parameters()])

    def _save_codes(self, save_as):
        import inspect
        code = '''import torch\nimport alphadeep.model.base as model_base\n'''
        class_code = inspect.getsource(self.model.__class__)
        code += 'class Model' + class_code[class_code.find('('):]
        with open(save_as, 'w') as f:
            f.write(code)

    def save(self, save_as):
        dir = os.path.dirname(save_as)
        if not dir: dir = './'
        if not os.path.exists(dir): os.makedirs(dir)
        torch.save(self.model.state_dict(), save_as)
        with open(save_as+'.txt','w') as f: f.write(str(self.model))
        save_yaml(save_as+'.model_const.yaml', model_const)
        self._save_codes(save_as+'.model.py')
        save_yaml(save_as+'.param.yaml', self.model_params)

    def _load_model_file(self, stream):
        (
            missing_keys, unexpect_keys
        ) = self.model.load_state_dict(torch.load(
            stream, map_location=self.device),
            strict=False
        )

    def load(
        self,
        model_file: Tuple[str, IO],
        model_path_in_zip: str = None,
        **kwargs
    ):
        if isinstance(model_file, str):
            # We may release all models (msms, rt, ccs, ...) in a single zip file
            if model_file.lower().endswith('.zip'):
                with ZipFile(model_file) as model_zip:
                    with model_zip.open(model_path_in_zip,'r') as pt_file:
                        self._load_model_file(pt_file)
            else:
                with open(model_file,'rb') as pt_file:
                    self._load_model_file(pt_file)
        else:
            self._load_model_file(model_file)

    def _train_one_batch(
        self,
        targets:Union[torch.Tensor,List[torch.Tensor]],
        *features,
    ):
        self.optimizer.zero_grad()
        predicts = self.model(*[fea.to(self.device) for fea in features])
        if isinstance(targets, list):
            # predicts must be a list or tuple as well
            cost = self.loss_func(
                predicts,
                [t.to(self.device) for t in targets]
            )
        else:
            cost = self.loss_func(predicts, targets.to(self.device))
        cost.backward()
        self.optimizer.step()
        return cost.item()

    def _predict_one_batch(self,
        *features
    ):
        predicts = self.model(*[fea.to(self.device) for fea in features])
        if isinstance(predicts, torch.Tensor):
            return predicts.cpu().detach().numpy()
        else:
            return [p.cpu().detach().numpy() for p in predicts]

    def _get_targets_from_batch_df(self,
        batch_df:pd.DataFrame,
        nAA, **kwargs,
    )->Union[torch.Tensor,List]:
        raise NotImplementedError(
            'Must implement _get_targets_from_batch_df() method'
        )

    def _get_features_from_batch_df(self,
        batch_df:pd.DataFrame,
        nAA, **kwargs,
    )->Tuple[torch.Tensor]:
        raise NotImplementedError(
            'Must implement _get_features_from_batch_df() method'
        )

    def _prepare_predict_data_df(self,
        precursor_df:pd.DataFrame,
        **kwargs
    ):
        '''
        This method must create a `self.predict_df` dataframe.
        '''
        self.predict_df = pd.DataFrame()

    def _prepare_train_data_df(self,
        precursor_df:pd.DataFrame,
        **kwargs
    ):
        pass

    def _set_batch_predict_data(self,
        batch_df:pd.DataFrame,
        predicts:Union[torch.Tensor, List],
        **kwargs
    ):
        raise NotImplementedError(
            'Must implement _set_batch_predict_data_df() method'
        )

    def train(self,
        precursor_df: pd.DataFrame,
        batch_size=1024,
        epoch=20,
        verbose=False,
        verbose_each_epoch=False,
        **kwargs
    ):
        if 'nAA' not in precursor_df.columns:
            precursor_df['nAA'] = precursor_df.sequence.str.len()
        self._prepare_train_data_df(precursor_df, **kwargs)
        self.model.train()

        for epoch in range(epoch):
            batch_cost = []
            _grouped = list(precursor_df.sample(frac=1).groupby('nAA'))
            rnd_nAA = np.random.permutation(len(_grouped))
            if verbose_each_epoch:
                batch_tqdm = tqdm(rnd_nAA)
            else:
                batch_tqdm = rnd_nAA
            for i_group in batch_tqdm:
                nAA, df_group = _grouped[i_group]
                df_group = df_group.reset_index(drop=True)
                for i in range(0, len(df_group), batch_size):
                    batch_end = i+batch_size-1 # DataFrame.loc[start:end] inlcudes the end

                    batch_df = df_group.loc[i:batch_end,:]
                    targets = self._get_targets_from_batch_df(batch_df,nAA,**kwargs)
                    features = self._get_features_from_batch_df(batch_df,nAA,**kwargs)

                    cost = self._train_one_batch(
                        targets,
                        *features,
                    )
                    batch_cost.append(cost)
                if verbose_each_epoch:
                    batch_tqdm.set_description(
                        f'Epoch={epoch+1}, nAA={nAA}, Batch={len(batch_cost)}, Loss={cost:.4f}'
                    )
            if verbose: print(f'[Training] Epoch={epoch+1}, Mean Loss={np.mean(batch_cost)}')

        torch.cuda.empty_cache()

    def predict(self,
        precursor_df:pd.DataFrame,
        batch_size=1024,
        verbose=False,**kwargs
    )->pd.DataFrame:
        if 'nAA' not in precursor_df.columns:
            precursor_df['nAA'] = precursor_df.sequence.str.len()
        self._prepare_predict_data_df(precursor_df,**kwargs)
        self.model.eval()

        _grouped = precursor_df.groupby('nAA')
        if verbose:
            batch_tqdm = tqdm(_grouped)
        else:
            batch_tqdm = _grouped

        for nAA, df_group in batch_tqdm:
            for i in range(0, len(df_group), batch_size):
                batch_end = i+batch_size

                batch_df = df_group.iloc[i:batch_end,:]

                features = self._get_features_from_batch_df(
                    batch_df, nAA, **kwargs
                )

                predicts = self._predict_one_batch(*features)

                self._set_batch_predict_data(
                    batch_df, predicts,
                    **kwargs
                )

        torch.cuda.empty_cache()
        return self.predict_df