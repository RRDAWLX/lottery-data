import os
import sys
import json
import torch

sys.path.insert(0, os.path.dirname(__file__))

from data.processor import (
    load_db, extract_numbers, build_lm_samples, build_incremental_lm_samples,
    get_lottery_config,
)
from model.lottery_gpt2 import (
    create_model, load_model_from_checkpoint, save_model,
    BOS_TOKEN, EOS_TOKEN, number_to_token, token_to_number, VOCAB_SIZE,
)


def get_project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_config():
    config_path = os.path.join(get_project_root(), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_checkpoint_dir(lottery_type):
    return os.path.join(get_project_root(), 'llm-prediction', 'checkpoint', lottery_type)


def get_latest_json_path(lottery_type):
    return os.path.join(get_checkpoint_dir(lottery_type), 'latest.json')


def load_latest_state(lottery_type):
    path = get_latest_json_path(lottery_type)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_latest_state(lottery_type, state):
    path = get_latest_json_path(lottery_type)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_model(lottery_type, prediction_config):
    from model.lottery_gpt2 import build_gpt2_config
    checkpoint_dir = get_checkpoint_dir(lottery_type)
    model_path = os.path.join(checkpoint_dir, 'model.pt')
    if not os.path.exists(model_path):
        return None
    model_config = prediction_config.get('model_config', {})
    config = build_gpt2_config(model_config)
    from transformers import GPT2LMHeadModel
    model = GPT2LMHeadModel(config)
    state_dict = torch.load(model_path, map_location='cpu')
    model.load_state_dict(state_dict)
    return model


def run_training(lottery_type, force_full=False):
    from model.trainer import train

    config = get_config()
    prediction_config = config.get('prediction', {})
    n = prediction_config.get('n', 10)
    lottery_config = get_lottery_config(lottery_type)

    db_path = os.path.join(get_project_root(), 'server', 'db', 'db.json')
    db = load_db(db_path)
    data_arr = db.get(lottery_type, [])
    numbers_list = extract_numbers(data_arr)

    checkpoint_dir = get_checkpoint_dir(lottery_type)
    latest_state = load_latest_state(lottery_type)
    model_path = os.path.join(checkpoint_dir, 'model.pt')

    model_state_dict_path = None
    is_incremental = False

    if not force_full and latest_state is not None and os.path.exists(model_path):
        if latest_state.get('n') != n:
            print(f"[{lottery_type}] n changed from {latest_state.get('n')} to {n}, retraining from scratch")
            force_full = True
        else:
            model_state_dict_path = model_path
            latest_trained_issue = latest_state.get('latest_trained_issue')
            input_ids_list, labels_list = build_incremental_lm_samples(
                numbers_list, n, latest_trained_issue, data_arr
            )
            if len(input_ids_list) == 0:
                print(f"[{lottery_type}] No new data for incremental training")
                return None
            print(f"[{lottery_type}] Incremental training with {len(input_ids_list)} new samples")
            is_incremental = True

    if force_full or latest_state is None or not os.path.exists(model_path):
        if len(numbers_list) <= n:
            print(f"[{lottery_type}] Not enough data (need > {n} periods, got {len(numbers_list)})")
            return None
        input_ids_list, labels_list = build_lm_samples(numbers_list, n)
        model_state_dict_path = None
        print(f"[{lottery_type}] Full training with {len(input_ids_list)} samples")

    model = train(
        lottery_type, input_ids_list, labels_list,
        prediction_config, checkpoint_dir,
        model_state_dict_path=model_state_dict_path,
    )

    last_item = data_arr[-1]
    save_latest_state(lottery_type, {
        'n': n,
        'latest_trained_issue': last_item['issue'],
        'total_periods_used': len(data_arr),
        'model_updated_at': last_item['date'],
    })

    print(f"[{lottery_type}] Training complete, checkpoint saved")
    return model


def run_prediction(lottery_type):
    config = get_config()
    prediction_config = config.get('prediction', {})
    n = prediction_config.get('n', 10)
    lottery_config = get_lottery_config(lottery_type)

    model = load_model(lottery_type, prediction_config)
    if model is None:
        return None

    db_path = os.path.join(get_project_root(), 'server', 'db', 'db.json')
    db = load_db(db_path)
    data_arr = db.get(lottery_type, [])
    numbers_list = extract_numbers(data_arr)

    if len(numbers_list) < n:
        return None

    from data.processor import serialize_period
    context_tokens = []
    for nums in numbers_list[-n:]:
        context_tokens.extend(serialize_period(nums))
    context_tokens.append(BOS_TOKEN)

    input_ids = torch.tensor([context_tokens], dtype=torch.long)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = model.to(device)
    input_ids = input_ids.to(device)

    model.eval()
    generated = list(context_tokens)

    ordinary_count = lottery_config['ordinary_count']
    special_count = lottery_config['special_count']
    total_numbers = ordinary_count + special_count

    ordinary_numbers = []
    special_numbers = []

    with torch.no_grad():
        for step in range(total_numbers):
            input_tensor = torch.tensor([generated], dtype=torch.long, device=device)
            outputs = model(input_ids=input_tensor)
            next_token_logits = outputs.logits[0, -1, :]

            if step < ordinary_count:
                ordinary_range = lottery_config['ordinary_range']
                mask = torch.full((VOCAB_SIZE,), float('-inf'), device=device)
                for num in range(1, ordinary_range + 1):
                    tok = number_to_token(num)
                    if num not in set(ordinary_numbers):
                        mask[tok] = 0.0
                masked_logits = next_token_logits + mask
                next_token = torch.argmax(masked_logits).item()
                number_val = token_to_number(next_token)
                ordinary_numbers.append(number_val)
            else:
                special_range = lottery_config['special_range']
                mask = torch.full((VOCAB_SIZE,), float('-inf'), device=device)
                for num in range(1, special_range + 1):
                    tok = number_to_token(num)
                    mask[tok] = 0.0
                masked_logits = next_token_logits + mask
                next_token = torch.argmax(masked_logits).item()
                number_val = token_to_number(next_token)
                special_numbers.append(number_val)

            generated.append(next_token)

    prediction = sorted(ordinary_numbers) + special_numbers
    return prediction


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery-type', type=str, required=True, choices=['unionLotto', 'superLotto'])
    parser.add_argument('--force-full', action='store_true')
    parser.add_argument('--action', type=str, default='train', choices=['train', 'predict', 'both'])
    args = parser.parse_args()

    if args.action in ('train', 'both'):
        run_training(args.lottery_type, force_full=args.force_full)

    if args.action in ('predict', 'both'):
        result = run_prediction(args.lottery_type)
        if result is not None:
            print(f"Prediction: {result}")
        else:
            print("No model available for prediction")