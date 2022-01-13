# AUTOGENERATED! DO NOT EDIT! File to edit: nbdev_nbs/model/building_block.ipynb (unless otherwise specified).

__all__ = ['mod_feature_size', 'max_instrument_num', 'frag_types', 'max_frag_charge', 'num_ion_types',
           'aa_embedding_size', 'SeqCNN', 'aa_embedding', 'aa_one_hot', 'zero_param', 'xavier_param', 'SeqLSTM',
           'init_state', 'SeqGRU', 'SeqTransformer', 'SeqAttentionSum', 'InputMetaNet', 'InputModNet',
           'InputModNetFixFirstK', 'InputAALSTM', 'InputAALSTM_cat_Meta', 'InputAALSTM_cat_Charge', 'InputAAEmbedding',
           'Input_AA_CNN_LSTM_Encoder', 'Input_AA_CNN_Encoder', 'Input_AA_CNN_LSTM_cat_Charge_Encoder',
           'Input_AA_CNN_Encoder', 'Input_AA_LSTM_Encoder', 'SeqLSTMDecoder', 'SeqGRUDecoder', 'OutputLSTM_cat_Meta',
           'OutputLinear_cat_Meta', 'LinearDecoder', 'HiddenTransformer']

# Cell
import torch
torch.set_num_threads(2)

from alphadeep.settings import model_const
from alphadeep.settings import global_settings as settings

mod_feature_size = len(model_const['mod_elements'])
max_instrument_num = model_const['max_instrument_num']
frag_types = settings['model']['frag_types']
max_frag_charge = settings['model']['max_frag_charge']
num_ion_types = len(frag_types)*max_frag_charge
aa_embedding_size = model_const['aa_embedding_size']

# Cell
class SeqCNN(torch.nn.Module):
    def __init__(self, embedding_hidden):
        super().__init__()

        self.cnn_short = torch.nn.Conv1d(
            embedding_hidden, embedding_hidden,
            kernel_size=3, padding=1
        )
        self.cnn_medium = torch.nn.Conv1d(
            embedding_hidden, embedding_hidden,
            kernel_size=5, padding=2
        )
        self.cnn_long = torch.nn.Conv1d(
            embedding_hidden, embedding_hidden,
            kernel_size=7, padding=3
        )

    def forward(self, x):
        x = x.transpose(1, 2)
        x1 = self.cnn_short(x)
        x2 = self.cnn_medium(x)
        x3 = self.cnn_long(x)
        return torch.cat((x, x1, x2, x3), dim=1).transpose(1,2)

# Cell
def aa_embedding(hidden_size):
    return torch.nn.Embedding(aa_embedding_size, hidden_size, padding_idx=0)

def aa_one_hot(aa_indices, *cat_others):
    aa_x = torch.nn.functional.one_hot(
        aa_indices, aa_embedding_size
    )
    return torch.cat((aa_x, *cat_others), 2)

# Cell
def zero_param(*shape):
    return torch.nn.Parameter(torch.zeros(shape), requires_grad=False)

def xavier_param(*shape):
    x = torch.nn.Parameter(torch.empty(shape), requires_grad=False)
    torch.nn.init.xavier_uniform_(x)
    return x

init_state = xavier_param

class SeqLSTM(torch.nn.Module):
    def __init__(self, in_features, out_features,
                 rnn_layer=2, bidirectional=True
        ):
        super().__init__()

        if bidirectional:
            if out_features%2 != 0:
                raise ValueError("'out_features' must be able to be divided by 2")
            hidden = out_features//2
        else:
            hidden = out_features

        self.rnn_h0 = init_state(
            rnn_layer+rnn_layer*bidirectional,
            1, hidden
        )
        self.rnn_c0 = init_state(
            rnn_layer+rnn_layer*bidirectional,
            1, hidden
        )
        self.rnn = torch.nn.LSTM(
            input_size = in_features,
            hidden_size = hidden,
            num_layers = rnn_layer,
            batch_first = True,
            bidirectional = bidirectional,
        )

    def forward(self, x:torch.Tensor):
        h0 = self.rnn_h0.repeat(1, x.size(0), 1)
        c0 = self.rnn_c0.repeat(1, x.size(0), 1)
        x, _ = self.rnn(x, (h0,c0))
        return x

# Cell
class SeqGRU(torch.nn.Module):
    def __init__(self, in_features, out_features,
                 rnn_layer=2, bidirectional=True
        ):
        super().__init__()

        if bidirectional:
            if out_features%2 != 0:
                raise ValueError("'out_features' must be able to be divided by 2")
            # to make sure that output dim is out_features
            # as `bidirectional` will cat forward and reverse RNNs
            hidden = out_features//2
        else:
            hidden = out_features

        self.rnn_h0 = init_state(
            rnn_layer+rnn_layer*bidirectional,
            1, hidden
        )
        self.rnn = torch.nn.GRU(
            input_size = in_features,
            hidden_size = hidden,
            num_layers = rnn_layer,
            batch_first = True,
            bidirectional = bidirectional,
        )

    def forward(self, x:torch.Tensor):
        h0 = self.rnn_h0.repeat(1, x.size(0), 1)
        x, _ = self.rnn(x, h0)
        return x

class SeqTransformer(torch.nn.Module):
    def __init__(self,
        in_features,
        out_features,
        nhead=8,
        nlayers=2,
        dropout=0.2
    ):
        super().__init__()
        encoder_layers = torch.nn.TransformerEncoderLayer(
            in_features, nhead, out_features, dropout
        )
        self.transformer_encoder = torch.nn.TransformerEncoder(
            encoder_layers, nlayers
        )

    def forward(self, x):
        return self.transformer_encoder(x.permute(1,0,2)).permute(1,0,2)

# Cell
class SeqAttentionSum(torch.nn.Module):
    def __init__(self, in_features):
        super().__init__()
        self.attn = torch.nn.Sequential(
            torch.nn.Linear(in_features, 1, bias=False),
            torch.nn.Softmax(dim=1),
        )

    def forward(self, x):
        attn = self.attn(x)
        return torch.sum(torch.mul(x, attn), dim=1)

# Cell
class InputMetaNet(torch.nn.Module):
    # Meta = Charge, NCE and Instrument
    def __init__(self,
        out_features,
    ):
        super().__init__()
        self.nn = torch.nn.Linear(
            max_instrument_num+1, out_features-1
        )

    def forward(self,
        charges, NCEs, instrument_indices,
    ):
        inst_x = torch.nn.functional.one_hot(
            instrument_indices, max_instrument_num
        )
        meta_x = self.nn(torch.cat((inst_x, NCEs), 1))
        meta_x = torch.cat((meta_x, charges), 1)
        return meta_x

class InputModNet(torch.nn.Module):
    def __init__(self,
        out_features,
    ):
        super().__init__()
        self.nn = torch.nn.Linear(
            mod_feature_size, out_features,
            bias=False
        )

    def forward(self,
        mod_x,
    ):
        return self.nn(mod_x)

class InputModNetFixFirstK(torch.nn.Module):
    def __init__(self,
        out_features,
    ):
        super().__init__()
        self.k = 6
        self.nn = torch.nn.Linear(
            mod_feature_size-self.k, out_features-self.k,
            bias=False
        )

    def forward(self,
        mod_x,
    ):
        return torch.cat((
            mod_x[:,:,:self.k],
            self.nn(mod_x[:,:,self.k:])
        ), 2)

class InputAALSTM(torch.nn.Module):
    def __init__(self,
        out_features,
    ):
        super().__init__()
        mod_hidden = 8
        self.mod_nn = InputModNetFixFirstK(mod_hidden)
        self.lstm = SeqLSTM(
            aa_embedding_size+mod_hidden,
            out_features,
            rnn_layer=1, bidirectional=True
        )
    def forward(self, aa_indices, mod_x):
        mod_x = self.mod_nn(mod_x)
        x = aa_one_hot(aa_indices, mod_x)
        return self.lstm(x)

class InputAALSTM_cat_Meta(torch.nn.Module):
    def __init__(self,
        out_features,
    ):
        super().__init__()
        meta_dim = 4
        mod_hidden = 8
        self.mod_nn = InputModNetFixFirstK(mod_hidden)
        self.meta_nn = InputMetaNet(meta_dim)
        self.nn = SeqLSTM(
            aa_embedding_size+mod_hidden,
            out_features-meta_dim,
            rnn_layer=1, bidirectional=True
        )

    def forward(self,
        aa_indices, mod_x, charges, NCEs, instrument_indices
    ):
        mod_x = self.mod_nn(mod_x)
        x = aa_one_hot(aa_indices, mod_x)
        x = self.nn(x)
        meta_x = self.meta_nn(
            charges, NCEs, instrument_indices
        ).unsqueeze(1).repeat(1, mod_x.size(1), 1)
        return torch.cat((x, meta_x), 2)

class InputAALSTM_cat_Charge(torch.nn.Module):
    def __init__(self,
        out_features,
    ):
        super().__init__()
        self.charge_dim = 2
        mod_hidden = 8
        self.mod_nn = InputModNetFixFirstK(mod_hidden)
        self.nn = SeqLSTM(
            aa_embedding_size+mod_hidden,
            out_features-self.charge_dim,
            rnn_layer=1, bidirectional=True
        )

    def forward(self, aa_indices, mod_x, charges):
        mod_x = self.mod_nn(mod_x)
        x = aa_one_hot(aa_indices, mod_x)
        x = self.nn(x)
        charge_x = charges.unsqueeze(1).repeat(
            1, mod_x.size(1), self.charge_dim
        )
        return torch.cat((x, charge_x), 2)

class InputAAEmbedding(torch.nn.Module):
    def __init__(self,
        out_features,
    ):
        super().__init__()
        self.aa_embedding = aa_embedding(
            out_features-mod_feature_size
        )
    def forward(self, aa_indices, mod_x):
        aa_x = self.aa_embedding(aa_indices)
        return torch.cat((aa_x, mod_x), 2)

# Cell
class Input_AA_CNN_LSTM_Encoder(torch.nn.Module):
    """
    Encode a peptide sequence into a single hidden representation
    """
    def __init__(self, out_features):
        super().__init__()

        mod_hidden = 8
        self.mod_nn = InputModNetFixFirstK(mod_hidden)

        input_dim = aa_embedding_size+mod_hidden
        self.input_cnn = SeqCNN(input_dim)
        self.hidden_nn = SeqLSTM(
            input_dim*4, out_features, rnn_layer=2
        ) #SeqCNN outputs 4*input_dim
        self.attn_sum = SeqAttentionSum(out_features)

    def forward(self, aa_indices, mod_x):
        mod_x = self.mod_nn(mod_x)
        x = aa_one_hot(aa_indices, mod_x)
        x = self.input_cnn(x)
        x = self.hidden_nn(x)
        x = self.attn_sum(x)
        return x

class Input_AA_CNN_Encoder(torch.nn.Module):
    def __init__(self, out_features):
        super().__init__()

        mod_hidden = 8
        self.mod_nn = InputModNetFixFirstK(mod_hidden)
        input_dim = aa_embedding_size+mod_hidden
        self.input_cnn = SeqCNN(input_dim)
        self.hidden_nn = SeqLSTM(
            input_dim*4, out_features, rnn_layer=1
        ) #SeqCNN outputs 4*input_dim

    def forward(self, aa_indices, mod_x):
        mod_x = self.mod_nn(mod_x)
        x = aa_one_hot(aa_indices, mod_x)
        x = self.input_cnn(x)
        x = self.hidden_nn(x)
        return x

class Input_AA_CNN_LSTM_cat_Charge_Encoder(torch.nn.Module):
    """
    Encode a peptide sequence into a single hidden representation
    """
    def __init__(self, out_features):
        super().__init__()

        mod_hidden = 8
        self.mod_nn = InputModNetFixFirstK(mod_hidden)

        input_dim = aa_embedding_size+mod_hidden+1
        self.input_cnn = SeqCNN(input_dim)
        self.hidden_nn = SeqLSTM(
            input_dim*4, out_features, rnn_layer=2
        ) #SeqCNN outputs 4*input_dim
        self.attn_sum = SeqAttentionSum(out_features)

    def forward(self, aa_indices, mod_x, charges):
        mod_x = self.mod_nn(mod_x)
        x = aa_one_hot(
            aa_indices, mod_x,
            charges.unsqueeze(1).repeat(1,mod_x.size(1),1)
        )
        x = self.input_cnn(x)
        x = self.hidden_nn(x)
        x = self.attn_sum(x)
        return x

class Input_AA_CNN_Encoder(torch.nn.Module):
    def __init__(self, out_features):
        super().__init__()

        mod_hidden = 8
        self.mod_nn = InputModNetFixFirstK(mod_hidden)
        input_dim = aa_embedding_size+mod_hidden
        self.input_cnn = SeqCNN(input_dim)
        self.hidden_nn = SeqLSTM(
            input_dim*4, out_features, rnn_layer=1
        ) #SeqCNN outputs 4*input_dim

    def forward(self, aa_indices, mod_x):
        mod_x = self.mod_nn(mod_x)
        x = aa_one_hot(aa_indices, mod_x)
        x = self.input_cnn(x)
        x = self.hidden_nn(x)
        return x

class Input_AA_LSTM_Encoder(torch.nn.Module):
    def __init__(self, out_features):
        super().__init__()

        self.input_nn = InputAALSTM(out_features)
        self.nn = SeqLSTM(
            out_features, out_features, rnn_layer=1
        )

    def forward(self, aa_indices, mod_x):
        x = self.input_nn(aa_indices, mod_x)
        x = self.nn(x)
        return x

# Cell
class SeqLSTMDecoder(torch.nn.Module):
    """
    Decode hidden representation into the sequence
    """
    def __init__(self, in_features, out_features):
        super().__init__()

        hidden = 128
        self.rnn = SeqLSTM(
            in_features, out_features,
            rnn_layer=1, bidirectional=False,
        )

        self.output_nn = torch.nn.Linear(
            hidden, out_features, bias=False
        )

    def forward(self, x:torch.tensor, output_len):
        x = self.rnn(
            x.unsqueeze(1).repeat(1,output_len,1)
        )
        x = self.output_nn(x)
        return x

class SeqGRUDecoder(torch.nn.Module):
    """
    Decode hidden representation into the sequence
    """
    def __init__(self, in_features, out_features):
        super().__init__()

        hidden = 128
        self.rnn = SeqGRU(
            in_features, out_features,
            rnn_layer=1, bidirectional=False,
        )

        self.output_nn = torch.nn.Linear(
            hidden, out_features, bias=False
        )

    def forward(self, x:torch.tensor, output_len):
        x = self.rnn(
            x.unsqueeze(1).repeat(1,output_len,1)
        )
        x = self.output_nn(x)
        return x

# Cell
class OutputLSTM_cat_Meta(torch.nn.Module):
    def __init__(self,
        in_features,
        out_features,
    ):
        super().__init__()
        meta_dim = 4
        self.meta_nn = InputMetaNet(meta_dim)
        self.nn = SeqLSTM(
            in_features+meta_dim,
            out_features,
            rnn_layer=1, bidirectional=False
        )

    def forward(self, x, charges, NCEs, instrument_indices):
        meta_x = self.meta_nn(
            charges, NCEs, instrument_indices
        ).unsqueeze(1).repeat(1, x.size(1), 1)
        return self.nn(torch.cat((x, meta_x), 2))


class OutputLinear_cat_Meta(torch.nn.Module):
    def __init__(self,
        in_features,
        out_features,
    ):
        super().__init__()
        meta_dim = 4
        self.meta_nn = InputMetaNet(meta_dim)
        self.nn = torch.nn.Linear(
            in_features+meta_dim,
            out_features,
            bias=False
        )

    def forward(self, x, charges, NCEs, instrument_indices):
        meta_x = self.meta_nn(
            charges, NCEs, instrument_indices
        ).unsqueeze(1).repeat(1, x.size(1), 1)
        return self.nn(torch.cat((x, meta_x), 2))

# Cell
class LinearDecoder(torch.nn.Module):
    def __init__(self, in_features, out_features):
        super().__init__()

        self.nn = torch.nn.Sequential(
            torch.nn.Linear(in_features, 64),
            torch.nn.PReLU(),
            torch.nn.Linear(64, out_features),
        )

    def forward(self, x):
        return self.nn(x)

# Cell
class HiddenTransformer(torch.nn.Module):
    def __init__(self, hidden, nlayers=1, dropout=0.2):
        super().__init__()
        self.transormer = SeqTransformer(
            hidden, hidden, nhead=8,
            nlayers=nlayers, dropout=dropout
        )
    def forward(self, x):
        return self.transormer(x)