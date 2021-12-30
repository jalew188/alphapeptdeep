# AUTOGENERATED! DO NOT EDIT! File to edit: nbdev_nbs/model/rt.ipynb (unless otherwise specified).

__all__ = ['uniform_sampling', 'mod_feature_size', 'EncDecModelRT', 'AlphaRTModel', 'evaluate_linear_regression',
           'evaluate_linear_regression_plot', 'convert_predicted_rt_to_irt', 'irt_pep']

# Cell
import torch
import pandas as pd
import numpy as np

from alphadeep.model.featurize import (
    parse_aa_indices,
    get_batch_mod_feature
)

from alphadeep._settings import model_const

import alphadeep.model.base as model_base

mod_feature_size = len(model_const['mod_elements'])

def uniform_sampling(psm_df:pd.DataFrame,
    target:str='rt_norm', n_train:int=1000,
    return_test_df:bool=False
)->pd.DataFrame:
    """
    Sampling training PSMs (rows) uniformly from the
    `target` columns in `psm_df` for transfer learning.

    Args:
        psm_df (pd.DataFrame): Dataframe of PSMs.
        target (str, optional): Target columns to sample.
            Defaults to 'rt_norm'.
        n_train (int, optional): The number of training PSMs
            to sample. Defaults to 1000.
        return_test_df (bool, optional): If also return `test_df`.
            `test_df` contains the PSMs that are not sampled.
            Defaults to False.

    Returns:
        pd.DataFrame: The sampled training PSMs (dataframe)
        [pd.DataFrame]: The not sampled PSMs (dataframe) for testing.
            Returned only if `return_test_df==True` in the arguments.
    """
    x = np.arange(0, 11)/10*psm_df[target].max()
    sub_n = n_train//(len(x)-1)
    df_list = []
    for i in range(len(x)-1):
        _df = psm_df[
            (psm_df[target]>=x[i])&(psm_df[target]<x[i+1])
        ]
        if len(_df) == 0: pass
        elif len(_df)//2 < sub_n:
            df_list.append(_df.sample(len(_df)//2))
        else:
            df_list.append(_df.sample(sub_n))
    train_df = pd.concat(df_list)
    if return_test_df:
        test_df = psm_df.drop(train_df.index)
        return train_df, test_df
    else:
        return train_df


# Cell
class EncDecModelRT(torch.nn.Module):
    def __init__(self,
        dropout=0.2
    ):
        super().__init__()

        self.dropout = torch.nn.Dropout(dropout)

        hidden = 256
        self.rt_encoder = model_base.Input_AA_CNN_LSTM_Encoder(
            hidden
        )

        self.rt_decoder = model_base.LinearDecoder(
            hidden,
            1
        )

    def forward(self,
        aa_indices,
        mod_x,
    ):
        x = self.rt_encoder(aa_indices, mod_x)
        x = self.dropout(x)

        return self.rt_decoder(x).squeeze(1)

# Cell
class AlphaRTModel(model_base.ModelImplBase):
    def __init__(self,
        dropout=0.1, lr=0.001,
    ):
        super().__init__()
        self.build(
            EncDecModelRT, lr=lr,
            dropout=dropout,
        )
        self.loss_func = torch.nn.L1Loss()

    def _prepare_predict_data_df(self,
        precursor_df:pd.DataFrame,
    ):
        precursor_df['rt_pred'] = 0.
        self.predict_df = precursor_df

    def _get_features_from_batch_df(self,
        batch_df: pd.DataFrame,
        nAA
    ):
        aa_indices = torch.LongTensor(
            parse_aa_indices(
                batch_df['sequence'].values.astype('U')
            )
        )

        mod_x_batch = get_batch_mod_feature(batch_df, nAA)
        mod_x = torch.Tensor(mod_x_batch)

        return aa_indices, mod_x

    def _get_targets_from_batch_df(self,
        batch_df: pd.DataFrame,
        **kwargs,
    ) -> torch.Tensor:
        return torch.Tensor(batch_df['rt_norm'].values)

    def _set_batch_predict_data(self,
        batch_df: pd.DataFrame,
        predicts: np.array,
    ):
        predicts[predicts<0] = 0.0
        if self._predict_in_order:
            self.predict_df.loc[:,'rt_pred'].values[
                batch_df.index.values[0]:batch_df.index.values[-1]+1
            ] = predicts
        else:
            self.predict_df.loc[
                batch_df.index,'rt_pred'
            ] = predicts

    def rt_to_irt_pred(self,
        precursor_df: pd.DataFrame
    ):
        convert_predicted_rt_to_irt(precursor_df, self)

# Cell
import statsmodels.api as sm
import matplotlib.pyplot as plt
import seaborn as sns

def evaluate_linear_regression(df, x='rt_pred', y='rt_norm', ci=95):
    gls = sm.GLS(df[y], sm.add_constant(df[x]))
    res = gls.fit()
    summary = res.summary(alpha=1-ci/100.0)
    dfs = []
    results_as_html = summary.tables[0].as_html()
    dfs.append(pd.read_html(results_as_html, index_col=None)[0])
    results_as_html = summary.tables[1].as_html()
    dfs.append(pd.read_html(results_as_html, index_col=None)[0])
    summary = pd.concat(dfs).reset_index(drop=True)
    R_square = float(summary.loc[0,3])
    R = np.sqrt(R_square)
    n,b,w = summary.loc[[5,10,11],1].values.astype(float)
    return pd.DataFrame(
        dict(
            R_square=[R_square],R=[R],
            slope=[w],intercept=[b],n_sample=[n]
        )
    )

def evaluate_linear_regression_plot(df, x='rt_pred', y='rt_norm', ci=95):
    sns.regplot(data=df, x=x, y=y, color='r', ci=ci, scatter_kws={'s':0.05, 'alpha':0.05, 'color':'b'})
    plt.show()

# Cell
irt_pep = pd.DataFrame(
    [['LGGNEQVTR', 'RT-pep a', -24.92, '', ''],
    ['GAGSSEPVTGLDAK', 'RT-pep b', 0.00, '', ''],
    ['VEATFGVDESNAK', 'RT-pep c', 12.39, '', ''],
    ['YILAGVENSK', 'RT-pep d', 19.79, '', ''],
    ['TPVISGGPYEYR', 'RT-pep e', 28.71, '', ''],
    ['TPVITGAPYEYR', 'RT-pep f', 33.38, '', ''],
    ['DGLDAASYYAPVR', 'RT-pep g', 42.26, '', ''],
    ['ADVTPADFSEWSK', 'RT-pep h', 54.62, '', ''],
    ['GTFIIDPGGVIR', 'RT-pep i', 70.52, '', ''],
    ['GTFIIDPAAVIR', 'RT-pep k', 87.23, '', ''],
    ['LFLQFGAQGSPFLK', 'RT-pep l', 100.00, '', '']],
    columns=['sequence','pep_name','irt', 'mods', 'mod_sites']
)
irt_pep['nAA'] = irt_pep.sequence.str.len()

def convert_predicted_rt_to_irt(
    df:pd.DataFrame, rt_model:AlphaRTModel
)->pd.DataFrame:
    rt_model.predict(irt_pep)
    # simple linear regression
    rt_pred_mean = irt_pep.rt_pred.mean()
    irt_mean = irt_pep.irt.mean()
    x = irt_pep.rt_pred.values - rt_pred_mean
    y = irt_pep.irt.values - irt_mean
    slope = np.sum(x*y)/np.sum(x*x)
    intercept = irt_mean - slope*rt_pred_mean
    # end linear regression
    df['irt_pred'] = df.rt_pred*slope + intercept
    return df