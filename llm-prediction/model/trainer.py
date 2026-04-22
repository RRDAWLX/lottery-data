"""训练器，支持全量训练和增量训练（加载已有模型权重继续训练）。"""

import os
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from .transformer import LotteryTransformer
from .dataset import LotteryDataset


def train(lottery_type, samples_x, samples_y, config, lottery_config, checkpoint_dir, model_state_dict=None):
    """训练模型并保存 checkpoint。

    Args:
        lottery_type: 彩票类型 (unionLotto / superLotto)
        samples_x: 输入样本列表，每个形状 (n, 7)
        samples_y: 目标样本列表，每个形状 (7,)
        config: prediction 配置字典，包含 model_config 和 training_config
        lottery_config: 彩票规则配置
        checkpoint_dir: checkpoint 保存目录
        model_state_dict: 已有模型权重（增量训练时传入），None 表示全量训练
    """
    os.makedirs(checkpoint_dir, exist_ok=True)

    model_config = config['model_config']
    training_config = config['training_config']

    model = LotteryTransformer(model_config, lottery_config)

    # 增量训练时加载已有权重
    if model_state_dict is not None:
        model.load_state_dict(model_state_dict)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = model.to(device)

    dataset = LotteryDataset(samples_x, samples_y)
    dataloader = DataLoader(
        dataset,
        batch_size=training_config['batch_size'],
        shuffle=True,
        drop_last=False,
    )

    ordinary_count = lottery_config['ordinary_count']
    special_count = lottery_config['special_count']
    ordinary_range = lottery_config['ordinary_range']
    special_range = lottery_config['special_range']

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=training_config['learning_rate'])

    model.train()
    for epoch in range(training_config['epochs']):
        total_loss = 0.0
        for batch_x, batch_y in dataloader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)

            optimizer.zero_grad()
            logits_list = model(batch_x)

            # 对每个号码位置分别计算交叉熵损失，然后取平均
            # target 为 1-based 号码值，转为 0-based 索引: 号码 1 → 索引 0
            loss = torch.tensor(0.0, device=device)
            for i in range(ordinary_count + special_count):
                target = batch_y[:, i] - 1
                if i < ordinary_count:
                    target = target.clamp(0, ordinary_range - 1)
                else:
                    target = target.clamp(0, special_range - 1)
                loss = loss + criterion(logits_list[i], target)

            loss = loss / (ordinary_count + special_count)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        avg_loss = total_loss / len(dataloader) if len(dataloader) > 0 else 0
        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"[{lottery_type}] Epoch {epoch+1}/{training_config['epochs']}, Loss: {avg_loss:.4f}")

    model_path = os.path.join(checkpoint_dir, 'model.pt')
    torch.save(model.state_dict(), model_path)

    return model