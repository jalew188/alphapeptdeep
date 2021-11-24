# AUTOGENERATED! DO NOT EDIT! File to edit: nbdev_nbs/spec_lib/translate.ipynb (unless otherwise specified).

__all__ = ['merge_precursor_fragment_df', 'speclib_to_single_df', 'alpha_to_other_mod_dict']

# Cell
import pandas as pd
import numpy as np
import tqdm
import typing
import itertools

from alphabase.spectrum_library.library_base import SpecLibBase
from alphadeep.model.ccs import ccs_to_mobility_pred_df

# Cell

def _get_frag_info_from_column_name(column:str):
    '''
    Only used when convert alphabase libraries into other libraries
    '''
    idx = column.rfind('_')
    frag_type = column[:idx]
    ch_str = column[idx+2:]
    charge = int(ch_str)
    if len(frag_type)==1:
        loss_type = 'noloss'
    else:
        idx = frag_type.find('_')
        loss_type = frag_type[idx+1:]
        frag_type = frag_type[0]
    return frag_type, loss_type, charge

def _get_frag_num(columns, rows, frag_len):
    frag_nums = []
    for r,c in zip(rows, columns):
        if c[0] in 'xyz':
            frag_nums.append(frag_len-r)
        else:
            frag_nums.append(r+1)
    return frag_nums

def _flatten(list_of_lists):
    '''
    Flatten a list of lists
    '''
    return list(
        itertools.chain.from_iterable(list_of_lists)
    )

def merge_precursor_fragment_df(
    precursor_df:pd.DataFrame,
    fragment_mass_df:pd.DataFrame,
    fragment_inten_df:pd.DataFrame,
    top_n_inten:int,
    frag_type_head:str='FragmentType',
    frag_mass_head:str='FragmengMz',
    frag_inten_head:str='RelativeIntensity',
    frag_charge_head:str='FragmentCharge',
    frag_loss_head:str='FragmentLossType',
    frag_num_head:str='FragmentNumber'
):
    '''
    Convert alphabase library into a single dataframe.
    This method is not important, as it will be only
    used by DiaNN, or spectronaut, or others
    '''
    df = precursor_df.copy()
    frag_columns = fragment_mass_df.columns.values.astype('U')
    frag_type_list = []
    frag_loss_list = []
    frag_charge_list = []
    frag_mass_list = []
    frag_inten_list = []
    frag_num_list = []
    for start, end in tqdm.tqdm(df[['frag_start_idx','frag_end_idx']].values):
        intens = fragment_inten_df.iloc[start:end,:].values # is loc[start:end-1,:] faster?
        masses = fragment_mass_df.iloc[start:end,:].values
        sorted_idx = np.argsort(intens.reshape(-1))[-top_n_inten:][::-1]
        idx_in_df = np.unravel_index(sorted_idx, masses.shape)

        frag_len = end-start
        rows = np.arange(frag_len, dtype=np.int32)[idx_in_df[0]]
        columns = frag_columns[idx_in_df[1]]

        frag_types, loss_types, charges = zip(
            *[_get_frag_info_from_column_name(_) for _ in columns]
        )

        frag_nums = _get_frag_num(columns, rows, frag_len)

        frag_type_list.append(frag_types)
        frag_loss_list.append(loss_types)
        frag_charge_list.append(charges)
        frag_mass_list.append(masses[idx_in_df])
        frag_inten_list.append(intens[idx_in_df])
        frag_num_list.append(frag_nums)

    try:
        df[frag_type_head] = frag_type_list
        df[frag_mass_head] = frag_mass_list
        df[frag_inten_head] = frag_inten_list
        df[frag_charge_head] = frag_charge_list
        df[frag_loss_head] = frag_loss_list
        df[frag_num_head] = frag_num_list
        return df.explode([
            frag_type_head,
            frag_mass_head,
            frag_inten_head,
            frag_charge_head,
            frag_loss_head,
            frag_num_head
        ])
    except ValueError:
        # df.explode does not allow mulitple columns before pandas version 1.x.x.
        df[frag_type_head] = frag_type_list
        df = df.explode(frag_type_head)

        df[frag_mass_head] = _flatten(frag_mass_list)
        df[frag_inten_head] = _flatten(frag_inten_list)
        df[frag_charge_head] = _flatten(frag_charge_list)
        df[frag_loss_head] = _flatten(frag_loss_list)
        df[frag_num_head] = _flatten(frag_num_list)
        return df

alpha_to_other_mod_dict = {
    "Carbamidomethyl@C": "Carbamidomethyl (C)",
    "Oxidation@M": "Oxidation (M)",
    "Phospho@S": "Phospho (STY)",
    "Phospho@T": "Phospho (STY)",
    "Phospho@Y": "Phospho (STY)",
    "GlyGly@K": "GlyGly (K)",
    "Acetyl@Protein N-term": "Acetyl (Protein N-term)",
}

def speclib_to_single_df(
    speclib:SpecLibBase,
    translate_mod_dict:dict = alpha_to_other_mod_dict,
    keep_k_highest_inten:int=12,
    frag_type_head:str='FragmentType',
    frag_mass_head:str='FragmengMz',
    frag_inten_head:str='RelativeIntensity',
    frag_charge_head:str='FragmentCharge',
    frag_loss_head:str='FragmentLossType',
    frag_num_head:str='FragmentNumber'
):
    '''
    Convert alphabase library to diann (or Spectronaut) library dataframe
    This method is not important, as it will be only
    used by DiaNN, or spectronaut, or others
    Args:
        translate_mod_dict (dict): a dict map modifications from alphabase to other software. Default: build-in `alpha_to_other_mod_dict`
        keep_k_highest_inten (int): only keep highest fragment intensities for each precursor. Default: 12
    Returns:
        pd.DataFrame: a single-file dataframe which contains precursors and fragments
    '''
    df = pd.DataFrame()
    df['ModifiedPeptide'] = speclib._precursor_df[
        ['sequence','mods','mod_sites']
    ].apply(
        create_modified_sequence,
        axis=1,
        translate_mod_dict=translate_mod_dict,
        mod_sep='[]'
    )

    df['frag_start_idx'] = speclib._precursor_df['frag_start_idx']
    df['frag_end_idx'] = speclib._precursor_df['frag_end_idx']

    df['PrecursorCharge'] = speclib._precursor_df['charge']
    if 'irt_pred' in speclib._precursor_df.columns:
        df['iRT'] = speclib._precursor_df['irt_pred']
    elif 'rt_pred' in speclib._precursor_df.columns:
        df['iRT'] = speclib._precursor_df['rt_pred']

    ccs_to_mobility_pred_df(speclib._precursor_df)
    df['IonMobility'] = speclib._precursor_df.mobility_pred

    df['LabelModifiedSequence'] = df['ModifiedPeptide']
    df['StrippedPeptide'] = speclib._precursor_df['sequence']

    df['PrecursorMz'] = speclib._precursor_df['precursor_mz']

    if 'protein_name' in speclib._precursor_df.columns:
        df['ProteinName'] = speclib._precursor_df['protein_name']
        df['UniprotID'] = df['ProteinName']
        df['ProteinGroups'] = df['ProteinName']

    if 'uniprot_id' in speclib._precursor_df.columns:
        df['UniprotID'] = speclib._precursor_df['uniprot_id']
        if 'ProteinName' not in df.columns:
            df['ProteinName'] = df['UniprotID']
            df['ProteinGroups'] = df['UniprotID']

    if 'genes' in speclib._precursor_df.columns:
        df['Genes'] = speclib._precursor_df['genes']

    if 'protein_group' in speclib._precursor_df.columns:
        df['ProteinGroups'] = speclib._precursor_df['protein_group']

    frag_inten = speclib.clip_inten_by_fragment_mz()

    df = merge_precursor_fragment_df(
        df,
        speclib._fragment_mass_df,
        frag_inten,
        top_n_inten=keep_k_highest_inten,
        frag_type_head=frag_type_head,
        frag_mass_head=frag_mass_head,
        frag_inten_head=frag_inten_head,
        frag_charge_head=frag_charge_head,
        frag_loss_head=frag_loss_head,
        frag_num_head=frag_num_head,
    )
    df = df[df['RelativeIntensity']>0]

    return df.drop(['frag_start_idx','frag_end_idx'], axis=1)