# AUTOGENERATED! DO NOT EDIT! File to edit: nbdev_nbs/reader/alphapept_reader.ipynb (unless otherwise specified).

__all__ = ['parse_ap', 'AlphaPeptReader']

# Cell
import numba
import os
import pandas as pd
import h5py

from alphadeep.reader.psm_reader import PSMReaderBase, psm_reader_provider

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

    for i in modseq:
        string += i
        if i.isupper():
            parsed.append(i)
            if len(string) > 1:
                sites.append(str(len(parsed)))
                mods.append(string)
            string = ""

    return ''.join(parsed), ';'.join(mods), ';'.join(sites), charge, decoy

class AlphaPeptReader(PSMReaderBase):
    def __init__(self,
        frag_types=['b','y','b-modloss','y-modloss'],
        max_frag_charge=2,
        frag_tol=20, frag_ppm=True,
    ):
        super().__init__(
            frag_types, max_frag_charge,
            frag_tol, frag_ppm
        )

        self.modification_convert_dict['cC'] = 'Carbamidomethyl@C'
        self.modification_convert_dict['oxM'] = 'Oxidation@M'
        self.modification_convert_dict['pS'] = 'Phospho@S'
        self.modification_convert_dict['pT'] = 'Phospho@T'
        self.modification_convert_dict['pY'] = 'Phospho@Y'
        self.modification_convert_dict['a'] = 'Acetyl@Protein_N-term'

    def _load_file(self, filename):
        with h5py.File(filename, 'r') as _hdf:
            dataset = _hdf['peptide_fdr']
            df = pd.DataFrame({col:dataset[col] for col in dataset.keys()})

        psm_df = pd.DataFrame()

        psm_df['precursor'] = df['precursor'].str.decode('utf-8')

        psm_df['raw_name'] = os.path.basename(filename)[:-len('.ms_data.hdf')]
        psm_df['RT'] = df['rt']*60
        if 'scan_no' in df.columns:
            psm_df['scan'] = df['scan_no'].astype('int')
        else:
            psm_df['scan'] = pd.NA
        if 'mobility' in df.columns:
            psm_df['mobility'] = df['mobility']
        else:
            psm_df['mobility'] = pd.NA

        psm_df['score'] = df['score']

        psm_df['sequence'], psm_df['mods'], \
            psm_df['mod_sites'], psm_df['charge'], \
            psm_df['decoy'] = zip(*psm_df['precursor'].apply(parse_ap))
        psm_df['charge'] = psm_df['charge'].astype(int)
        psm_df['nAA'] = psm_df.sequence.str.len()

        self._psm_df = psm_df

psm_reader_provider.register_reader('alphapept', AlphaPeptReader)