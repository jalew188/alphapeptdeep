# AUTOGENERATED! DO NOT EDIT! File to edit: nbdev_nbs/reader/alphapept_reader.ipynb (unless otherwise specified).

__all__ = ['parse_ap', 'AlphaPeptReader']

# Cell
import numba
import os
import pandas as pd
import h5py

from alphadeep.reader.psm_reader import PSMReader_w_FragBase, psm_reader_provider
from alphadeep.mass_spec.ms_reader import ms2_reader_provider, ms1_reader_provider

@numba.njit
def parse_ap(precursor):
    """
    Parser to parse peptide strings
    """
    items = precursor.split('_')
    if len(items) == 3:
        decoy = 1
    else:
        decoy = 0
    modseq = items[0]
    charge = items[-1]

    parsed = []
    mods = []
    sites = []
    string = ""

    if modseq[0] == 'a':
        sites.append('0')
        mods.append('a')
        modseq = modseq[1:]
    elif modseq.startswith('tmt'):
        for l in modseq[3:]:
            if modseq[l].isupper():
                break
        sites.append('0')
        mods.append(modseq[:l])
        modseq = modseq[l:]

    for i in modseq:
        string += i
        if i.isupper():
            parsed.append(i)
            if len(string) > 1:
                sites.append(str(len(parsed)))
                mods.append(string)
            string = ""

    return ''.join(parsed), ';'.join(mods), ';'.join(sites), charge, decoy

class AlphaPeptReader(PSMReader_w_FragBase):
    def __init__(self):
        super().__init__()

        self.modification_convert_dict['cC'] = 'Carbamidomethyl@C'
        self.modification_convert_dict['oxM'] = 'Oxidation@M'
        self.modification_convert_dict['pS'] = 'Phospho@S'
        self.modification_convert_dict['pT'] = 'Phospho@T'
        self.modification_convert_dict['pY'] = 'Phospho@Y'
        self.modification_convert_dict['a'] = 'Acetyl@Protein N-term'

        self.column_mapping = {
            'sequence': 'naked_sequence',
            'RT':'rt',
            'scan_no': 'scan_no',
            'scan_idx': 'raw_idx', #idx in ms2 list
            'mobility': 'mobility',
            'score': 'score',
            'charge': 'charge',
            'raw_name': 'raw_name',
        }

        self.hdf_dataset = 'peptide_fdr'

    def _load_file(self, filename):
        with h5py.File(filename, 'r') as _hdf:
            dataset = _hdf[self.hdf_dataset]
            df = pd.DataFrame({col:dataset[col] for col in dataset.keys()})
            df['raw_name'] = os.path.basename(filename)[:-len('.ms_data.hdf')]
            df['precursor'] = df['precursor'].str.decode('utf-8')
            if 'scan_no' in df.columns:
                df['scan_no'] = df['scan_no'].astype('int')
            df['charge'] = df['charge'].astype(int)
        return df

    def _translate_columns(self, df: pd.DataFrame):
        super()._translate_columns(df)

        self._psm_df['sequence'], self._psm_df['mods'], \
            self._psm_df['mod_sites'], self._psm_df['charge'], \
            self._psm_df['decoy'] = zip(*df['precursor'].apply(parse_ap))

    def load_fragment_inten_df(self, psm_df, ms_paths=None):
        if isinstance(ms_paths, (list,tuple)):
            ms_file = ms_paths[0]
        else:
            ms_file = ms_paths

psm_reader_provider.register_reader('alphapept', AlphaPeptReader)