"""数据预处理模块：加载 db.json、构建滑动窗口、增量窗口、贪心解码预测。"""

import json
import os

# 两种彩票的规则配置
# ordinary_range / special_range: 号码取值范围（1-based），也作为分类头的类别数
LOTTERY_CONFIG = {
    'unionLotto': {
        'ordinary_count': 6,    # 普通号个数
        'ordinary_range': 33,   # 普通号范围 1-33
        'special_count': 1,     # 特别号个数
        'special_range': 16,    # 特别号范围 1-16
    },
    'superLotto': {
        'ordinary_count': 5,
        'ordinary_range': 35,
        'special_count': 2,
        'special_range': 12,
    },
}


def get_lottery_config(lottery_type):
    """根据彩票类型返回规则配置（号码个数、取值范围等）。"""
    return LOTTERY_CONFIG[lottery_type]


def load_db(db_path):
    """加载 db.json，将 stringified 的内部对象解析为真正对象。"""
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
    """从数据数组中提取号码列表。"""
    numbers_list = []
    for item in data_arr:
        numbers_list.append(item['numbers'])
    return numbers_list


def create_sliding_windows(numbers_list, n):
    """用滑动窗口构建全量训练样本。

    例如 n=10, 共 100 期数据:
      输入 [0:10] → 目标 [10], 输入 [1:11] → 目标 [11], ...
    """
    samples_x = []
    samples_y = []
    for i in range(len(numbers_list) - n):
        window = numbers_list[i:i + n]
        target = numbers_list[i + n]
        samples_x.append(window)
        samples_y.append(target)
    return samples_x, samples_y


def create_incremental_windows(numbers_list, n, latest_trained_issue, data_arr):
    """用滑动窗口构建增量训练样本，只包含训练过的期号之后出现的新数据对应的窗口。

    通过 latest_trained_issue 找到新数据起始位置，只构造包含新数据的窗口。
    """
    start_idx = None
    for i, item in enumerate(data_arr):
        if item['issue'] > latest_trained_issue:
            start_idx = i
            break
    if start_idx is None:
        return [], []

    # 数据不足以构成新窗口
    first_new_end = start_idx + n
    if first_new_end > len(numbers_list):
        return [], []

    new_numbers = numbers_list[max(0, start_idx - n):]
    samples_x = []
    samples_y = []
    for i in range(len(new_numbers) - n):
        window = new_numbers[i:i + n]
        target = new_numbers[i + n]
        # 只保留目标期在原始数据范围内的样本
        window_start_in_original = max(0, start_idx - n) + i
        if window_start_in_original + n < len(numbers_list):
            samples_x.append(window)
            samples_y.append(target)

    # 去重：相同输入和目标的样本只保留一个
    filtered_x = []
    filtered_y = []
    for x, y in zip(samples_x, samples_y):
        exists = False
        for fx, fy in zip(filtered_x, filtered_y):
            if fx == x and fy == y:
                exists = True
                break
        if not exists:
            filtered_x.append(x)
            filtered_y.append(y)

    return filtered_x, filtered_y