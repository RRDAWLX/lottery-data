import json
import os

from model.lottery_gpt2 import BOS_TOKEN, EOS_TOKEN, number_to_token, token_to_number

LOTTERY_CONFIG = {
    'unionLotto': {
        'ordinary_count': 6,
        'ordinary_range': 33,
        'special_count': 1,
        'special_range': 16,
    },
    'superLotto': {
        'ordinary_count': 5,
        'ordinary_range': 35,
        'special_count': 2,
        'special_range': 12,
    },
}


def get_lottery_config(lottery_type):
    return LOTTERY_CONFIG[lottery_type]


def load_db(db_path):
    with open(db_path, 'r', encoding='utf-8') as f:
        raw_db = json.load(f)
    result = {}
    for lottery_type, data_arr in raw_db.items():
        if isinstance(data_arr, list) and len(data_arr) > 0 and isinstance(data_arr[0], str):
            result[lottery_type] = [json.loads(item) for item in data_arr]
        else:
            result[lottery_type] = data_arr
    return result


def extract_numbers(data_arr):
    numbers_list = []
    for item in data_arr:
        numbers_list.append(item['numbers'])
    return numbers_list


def serialize_period(numbers):
    tokens = [BOS_TOKEN]
    for num in numbers:
        tokens.append(number_to_token(num))
    tokens.append(EOS_TOKEN)
    return tokens


def build_lm_samples(numbers_list, n):
    input_ids_list = []
    labels_list = []
    for i in range(len(numbers_list) - n):
        context_numbers = numbers_list[i:i + n]
        target_numbers = numbers_list[i + n]
        context_tokens = []
        for nums in context_numbers:
            context_tokens.extend(serialize_period(nums))
        target_tokens = serialize_period(target_numbers)
        full_tokens = context_tokens + target_tokens
        input_ids = full_tokens[:-1]
        labels = full_tokens[1:]
        target_start = len(context_tokens)
        padded_labels = input_ids[:]
        for j in range(len(padded_labels)):
            if j < target_start - 1:
                padded_labels[j] = -100
        labels = padded_labels
        input_ids_list.append(input_ids)
        labels_list.append(labels)
    return input_ids_list, labels_list


def build_incremental_lm_samples(numbers_list, n, latest_trained_issue, data_arr):
    start_idx = None
    for i, item in enumerate(data_arr):
        if item['issue'] > latest_trained_issue:
            start_idx = i
            break
    if start_idx is None:
        return [], []

    first_new_end = start_idx + n
    if first_new_end > len(numbers_list):
        return [], []

    begin = max(0, start_idx - n)
    subset = numbers_list[begin:]
    offset = begin
    all_input_ids, all_labels = build_lm_samples(subset, n)

    adjusted_input_ids = []
    adjusted_labels = []
    seen = set()
    for idx, (inp, lab) in enumerate(zip(all_input_ids, all_labels)):
        window_start_in_original = begin + idx
        target_idx = window_start_in_original + n
        if target_idx >= len(numbers_list):
            continue
        if target_idx < start_idx:
            continue
        key = tuple(inp)
        if key in seen:
            continue
        seen.add(key)
        adjusted_input_ids.append(inp)
        adjusted_labels.append(lab)

    return adjusted_input_ids, adjusted_labels