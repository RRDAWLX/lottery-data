import torch
from transformers import GPT2Config, GPT2LMHeadModel


PAD_TOKEN = 0
BOS_TOKEN = 1
EOS_TOKEN = 2
NUM_OFFSET = 2
VOCAB_SIZE = 39


def number_to_token(num):
    return num + NUM_OFFSET


def token_to_number(token):
    return token - NUM_OFFSET


def build_gpt2_config(model_config):
    return GPT2Config(
        vocab_size=model_config.get('vocab_size', VOCAB_SIZE),
        n_positions=model_config.get('n_positions', 128),
        n_embd=model_config.get('n_embd', 64),
        n_head=model_config.get('n_head', 4),
        n_layer=model_config.get('n_layer', 4),
        n_inner=model_config.get('n_inner', 256),
        activation_function=model_config.get('activation_function', 'gelu_new'),
        resid_pdrop=model_config.get('resid_pdrop', 0.1),
        embd_pdrop=model_config.get('embd_pdrop', 0.1),
        attn_pdrop=model_config.get('attn_pdrop', 0.1),
        bos_token_id=BOS_TOKEN,
        eos_token_id=EOS_TOKEN,
        pad_token_id=PAD_TOKEN,
    )


def create_model(model_config):
    config = build_gpt2_config(model_config)
    model = GPT2LMHeadModel(config)
    return model


def load_model_from_checkpoint(model_path, model_config):
    config = build_gpt2_config(model_config)
    model = GPT2LMHeadModel(config)
    state_dict = torch.load(model_path, map_location='cpu')
    model.load_state_dict(state_dict)
    return model


def save_model(model, model_path):
    torch.save(model.state_dict(), model_path)