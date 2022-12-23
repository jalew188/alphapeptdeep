from alphabase.protein.fasta import SpecLibFasta
from peptdeep.spec_lib.predict_lib import PredictSpecLib
from peptdeep.pretrained_models import ModelManager


class PredictSpecLibFasta(SpecLibFasta, PredictSpecLib):
    def __init__(self,
        model_manager:ModelManager = None,
        charged_frag_types:list = ['b_z1','b_z2','y_z1','y_z2'],
        protease:str = 'trypsin/P',
        max_missed_cleavages:int = 2,
        peptide_length_min:int = 7,
        peptide_length_max:int = 35,
        precursor_charge_min:int = 2,
        precursor_charge_max:int = 4,
        precursor_mz_min:float = 200.0, 
        precursor_mz_max:float = 2000.0,
        var_mods:list = ['Acetyl@Protein N-term','Oxidation@M'],
        max_var_mod_num:int = 2,
        fix_mods:list = ['Carbamidomethyl@C'],
        decoy: str = None, # or pseudo_reverse or diann
        I_to_L=False,
    ):
        SpecLibFasta.__init__(self,
            charged_frag_types=charged_frag_types,
            protease=protease,
            max_missed_cleavages=max_missed_cleavages,
            peptide_length_min=peptide_length_min,
            peptide_length_max=peptide_length_max,
            precursor_charge_min=precursor_charge_min,
            precursor_charge_max=precursor_charge_max,
            precursor_mz_min=precursor_mz_min, 
            precursor_mz_max=precursor_mz_max,
            var_mods=var_mods,
            max_var_mod_num=max_var_mod_num,
            fix_mods=fix_mods,
            decoy=decoy,
            I_to_L=I_to_L,
        )

        PredictSpecLib.__init__(self,
            model_manager=model_manager,
            charged_frag_types=self.charged_frag_types,
            precursor_mz_min=self.min_precursor_mz,
            precursor_mz_max=self.max_precursor_mz,
            decoy=self.decoy,
        )
