# AUTOGENERATED! DO NOT EDIT! File to edit: nbdev_nbs/reader/maxquant_reader.ipynb (unless otherwise specified).

__all__ = ['parse_mq', 'MaxQuantReader']

# Cell
import pandas as pd
import numba
import numpy as np

from alphadeep.reader.psm_reader import PSMReaderBase, psm_reader_provider

from alphabase.peptide.fragment import \
    init_fragment_by_precursor_dataframe

@numba.njit
def parse_mq(
    modseq,
    fixed_C=True
):
    PeptideModSeq = modseq.strip('_')
    mod_list = []
    site_list = []
    if PeptideModSeq.startswith('('):
        site_list.append('0')
        site_end = PeptideModSeq.find(')')+1
        mod_list.append(PeptideModSeq[:site_end])
        PeptideModSeq = PeptideModSeq[site_end:]
    site = PeptideModSeq.find('(')
    while site != -1:
        site_end = PeptideModSeq.find(')',site+1)+1
        if site_end < len(PeptideModSeq) and PeptideModSeq[site_end] == ')':
            site_end += 1
        site_list.append(str(site+1))
        mod_list.append(PeptideModSeq[site-1:site_end])
        PeptideModSeq = PeptideModSeq[:site] + PeptideModSeq[site_end:]
        site = PeptideModSeq.find('(', site)
    if fixed_C:
        site = PeptideModSeq.find('C')
        while site != -1:
            site_list.append(str(site+1))
            mod_list.append('C(Carbamidomethyl (C))')
            site = PeptideModSeq.find('C',site+1)
    return ';'.join(mod_list), ';'.join(site_list)

class MaxQuantReader(PSMReaderBase):
    def __init__(self,
        frag_types=['b','y','b-modloss','y-modloss'],
        max_frag_charge=2,
        frag_tol=20, frag_ppm=True,
        load_frag_inten=False,
    ):
        super().__init__(
            frag_types, max_frag_charge,
            frag_tol, frag_ppm
        )

        self.if_load_frag_inten = load_frag_inten

        self.modification_convert_dict = {}
        self.modification_convert_dict['(Acetyl (Protein N-term))'] = 'Acetyl@Protein N-term'
        self.modification_convert_dict['C(Carbamidomethyl (C))'] = 'Carbamidomethyl@C'
        self.modification_convert_dict['M(Oxidation (M))'] = 'Oxidation@M'
        self.modification_convert_dict['S(Phospho (S))'] = 'Phospho@S'
        self.modification_convert_dict['T(Phospho (T))'] = 'Phospho@T'
        self.modification_convert_dict['Y(Phospho (Y))'] = 'Phospho@Y'
        self.modification_convert_dict['S(Phospho (ST))'] = 'Phospho@S'
        self.modification_convert_dict['T(Phospho (ST))'] = 'Phospho@T'
        self.modification_convert_dict['S(Phospho (STY))'] = 'Phospho@S'
        self.modification_convert_dict['T(Phospho (STY))'] = 'Phospho@T'
        self.modification_convert_dict['Y(Phospho (STY))'] = 'Phospho@Y'
        self.modification_convert_dict['N(Deamidation (NQ))'] = 'Deamidated@N'
        self.modification_convert_dict['Q(Deamidation (NQ))'] = 'Deamidated@Q'
        self.modification_convert_dict['K(GlyGly (K))'] = 'GlyGly@K'
        self.modification_convert_dict['(ac)'] = 'Acetyl@Protein N-term'
        self.modification_convert_dict['M(ox)'] = 'Oxidation@M'
        self.modification_convert_dict['S(ph)'] = 'Phospho@S'
        self.modification_convert_dict['T(ph)'] = 'Phospho@T'
        self.modification_convert_dict['Y(ph)'] = 'Phospho@Y'
        self.modification_convert_dict['K(gl)'] = 'GlyGly@K'

    def _load_file(self, filename):
        df = pd.read_csv(filename, sep='\t')
        df = df[(df['Reverse']!='+')&(~pd.isna(df['Retention time']))]
        df = df.reset_index(drop=True)
        psm_df = pd.DataFrame()
        psm_df['sequence'] = df['Sequence']
        psm_df['nAA'] = psm_df.sequence.str.len()
        psm_df['mods'], psm_df['mod_sites'] = zip(*df['Modified sequence'].apply(parse_mq))
        psm_df['charge'] = df['Charge']
        psm_df['RT'] = df['Retention time']*60
        if 'Scan number' in df.columns:
            # msms.txt
            psm_df['scan'] = df['Scan number']
        else:
            # evidence.txt
            psm_df['scan'] = df['MS/MS scan number']
        if 'K0' in df.columns:
            psm_df['mobility'] = 1/df['K0']
        else:
            psm_df['mobility'] = pd.NA
        if 'CCS' in df.columns:
            psm_df['CCS'] = df['CCS']
        else:
            psm_df['CCS'] = pd.NA
        psm_df['raw_name'] = df['Raw file']
        psm_df['score'] = df['Score']
        psm_df['proteins'] = df['Proteins']
        if 'Gene Names' in df.columns:
            psm_df['genes'] = df['Gene Names']
        elif 'Gene names' in df.columns:
            psm_df['genes'] = df['Gene names']
        else:
            psm_df['genes'] = ''
        self._psm_df = psm_df

        if self.if_load_frag_inten:
            self._load_fragment_inten(df)

    def _load_fragment_inten(self, mq_df):
        self._fragment_inten_df = init_fragment_by_precursor_dataframe(
            self._psm_df, self.charged_ion_types
        )

        frag_col_dict = dict(zip(
            self.charged_ion_types,
            range(len(self.charged_ion_types))
        ))

        for ith_psm, (nAA, start,end) in enumerate(
            self.psm_df[['nAA','frag_start_idx','frag_end_idx']].values
        ):
            intens = np.zeros((nAA-1, len(self.charged_ion_types)))

            frag_types = mq_df.loc[ith_psm,'Matches'].split(';')
            if len(frag_types) < 5: continue
            frag_intens = mq_df.loc[ith_psm,'Intensities']
            for frag_type, frag_inten in zip(
                frag_types, frag_intens.split(';')
            ):
                if '-' in frag_type: continue
                idx = frag_type.find('(')
                charge = '1+'
                if idx > 0:
                    frag_type, charge = frag_type[:idx], frag_type[idx+1:-1]
                frag_type, frag_pos = frag_type[0], int(frag_type[1:])
                if frag_type in 'xyz':
                    frag_pos = nAA - frag_pos -1
                else:
                    frag_pos -= 1
                frag_type += '_'+charge
                if frag_type not in frag_col_dict: continue
                frag_col = frag_col_dict[frag_type]

                intens[frag_pos,frag_col] = float(frag_inten)

            if np.any(intens==0):
                intens /= np.max(intens)
            self._fragment_inten_df.iloc[
                start:end,:
            ] = intens

    def load_fragment_inten_df(self, ms_files=None):
        pass

psm_reader_provider.register_reader('maxquant', MaxQuantReader)