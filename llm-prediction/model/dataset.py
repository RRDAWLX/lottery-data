"""PyTorch Dataset，封装滑动窗口训练样本。"""

import torch
from torch.utils.data import Dataset


class LotteryDataset(Dataset):
    """将滑动窗口样本 (samples_x, samples_y) 包装为 PyTorch Dataset。

    每个样本:
      x: (n, 7) — n 期号码
      y: (7,) — 目标期号码
    """

    def __init__(self, samples_x, samples_y):
        self.samples_x = samples_x
        self.samples_y = samples_y

    def __len__(self):
        """返回样本总数。"""
        return len(self.samples_x)

    def __getitem__(self, idx):
        """按索引返回一组训练样本 (x, y)，均为 long 类型张量。"""
        x = torch.tensor(self.samples_x[idx], dtype=torch.long)
        y = torch.tensor(self.samples_y[idx], dtype=torch.long)
        return x, y