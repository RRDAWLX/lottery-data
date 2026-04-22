"""训练和预测的核心逻辑。

负责读取配置和历史数据、判断全量/增量训练、管理 checkpoint、贪心解码预测。
"""

import os
import sys
import json
import torch

sys.path.insert(0, os.path.dirname(__file__))

from data.processor import load_db, extract_numbers, create_sliding_windows, create_incremental_windows, get_lottery_config
from model.transformer import LotteryTransformer
from model.trainer import train


def get_project_root():
    """返回项目根目录的绝对路径（llm-prediction 的上一级目录）。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_config():
    """读取项目根目录的 config.json，返回配置字典。"""
    config_path = os.path.join(get_project_root(), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_checkpoint_dir(lottery_type):
    """返回指定彩票类型的 checkpoint 目录路径。"""
    return os.path.join(get_project_root(), 'llm-prediction', 'checkpoint', lottery_type)


def get_latest_json_path(lottery_type):
    """返回指定彩票类型的 latest.json 文件路径，用于记录训练状态。"""
    return os.path.join(get_checkpoint_dir(lottery_type), 'latest.json')


def load_latest_state(lottery_type):
    """加载最新训练状态（n、最后训练期号等），用于增量训练判断。"""
    path = get_latest_json_path(lottery_type)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_latest_state(lottery_type, state):
    """将训练状态字典保存到 latest.json，自动创建目录。"""
    path = get_latest_json_path(lottery_type)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_model(lottery_type, config, lottery_config):
    """从 checkpoint 加载模型权重，模型不存在返回 None。"""
    checkpoint_dir = get_checkpoint_dir(lottery_type)
    model_path = os.path.join(checkpoint_dir, 'model.pt')
    if not os.path.exists(model_path):
        return None
    model = LotteryTransformer(config['model_config'], lottery_config)
    model.load_state_dict(torch.load(model_path, map_location='cpu'))
    return model


def run_training(lottery_type, force_full=False):
    """执行训练，自动判断全量或增量。

    增量条件：模型存在 + latest_state 存在 + n 未改变 + 有新数据。
    任何条件不满足则退化为全量训练。
    """
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
    model_state_dict = None

    model_path = os.path.join(checkpoint_dir, 'model.pt')

    # 尝试增量训练
    if not force_full and latest_state is not None and os.path.exists(model_path):
        # n 改变时必须全量重训，因为滑动窗口大小不同
        if latest_state.get('n') != n:
            print(f"[{lottery_type}] n changed from {latest_state.get('n')} to {n}, retraining from scratch")
            force_full = True
        else:
            model_state_dict = torch.load(model_path, map_location='cpu')
            latest_trained_issue = latest_state.get('latest_trained_issue')
            samples_x, samples_y = create_incremental_windows(
                numbers_list, n, latest_trained_issue, data_arr
            )
            if len(samples_x) == 0:
                print(f"[{lottery_type}] No new data for incremental training")
                return
            print(f"[{lottery_type}] Incremental training with {len(samples_x)} new samples")

    # 全量训练
    if force_full or latest_state is None or not os.path.exists(model_path):
        if len(numbers_list) <= n:
            print(f"[{lottery_type}] Not enough data (need > {n} periods, got {len(numbers_list)})")
            return
        samples_x, samples_y = create_sliding_windows(numbers_list, n)
        model_state_dict = None
        print(f"[{lottery_type}] Full training with {len(samples_x)} samples")

    model = train(
        lottery_type, samples_x, samples_y,
        prediction_config, lottery_config,
        checkpoint_dir, model_state_dict,
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
    """用最近 n 期数据作为输入，贪心解码预测下一期号码。

    返回: 号码列表 (普通号升序 + 特别号)，如 [2,6,17,25,27,32,1]
    """
    config = get_config()
    prediction_config = config.get('prediction', {})
    n = prediction_config.get('n', 10)
    lottery_config = get_lottery_config(lottery_type)

    model = load_model(lottery_type, prediction_config, lottery_config)
    if model is None:
        return None

    db_path = os.path.join(get_project_root(), 'server', 'db', 'db.json')
    db = load_db(db_path)
    data_arr = db.get(lottery_type, [])
    numbers_list = extract_numbers(data_arr)

    if len(numbers_list) < n:
        return None

    # 取最近 n 期作为模型输入
    last_n = numbers_list[-n:]
    input_tensor = torch.tensor([last_n], dtype=torch.long)

    model.eval()
    with torch.no_grad():
        logits_list = model(input_tensor)

    ordinary_count = lottery_config['ordinary_count']
    ordinary_range = lottery_config['ordinary_range']
    special_count = lottery_config['special_count']
    special_range = lottery_config['special_range']

    # 贪心解码普通号：逐位取概率最大的，已选号码 mask 掉
    ordinary_numbers = []
    used = set()
    for i in range(ordinary_count):
        probs = torch.softmax(logits_list[i][0, :ordinary_range], dim=0)
        probs_list = probs.tolist()
        for j in list(used):
            if j < len(probs_list):
                probs_list[j] = 0
        # 重新归一化
        total = sum(probs_list)
        if total > 0:
            probs_list = [p / total for p in probs_list]
        best_idx = max(range(len(probs_list)), key=lambda x: probs_list[x])
        used.add(best_idx)
        # logits 索引 0 对应号码 1，所以 +1
        ordinary_numbers.append(best_idx + 1)

    # 特别号直接取 argmax（不做去重）
    special_numbers = []
    for i in range(special_count):
        probs = torch.softmax(logits_list[ordinary_count + i][0, :special_range], dim=0)
        best_idx = torch.argmax(probs).item()
        special_numbers.append(best_idx + 1)

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