"""自定义 Transformer 模型，用于彩票号码预测。

架构:
  Number Embedding + 期内位置编码 + 期数位置编码 + 类型编码
  → Transformer Encoder
  → 取最后一期各位置 token 的输出
  → 每个号码位置的独立分类头（普通号和特别号维度不同）

输出: 长度为 7 的 logits 列表，普通号 head 输出 ordinary_range 类，特别号 head 输出 special_range 类。
"""

import math
import torch
import torch.nn as nn


class PositionalEncoding(nn.Module):
    """标准正弦位置编码，为序列中每个位置添加位置信息。"""

    def __init__(self, d_model, max_len=500):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))

    def forward(self, x):
        return x + self.pe[:, :x.size(1), :]


class TypeEmbedding(nn.Module):
    """类型编码，区分普通号和特别号。"""

    def __init__(self, d_model):
        super().__init__()
        self.ordinary_embed = nn.Parameter(torch.randn(1, 1, d_model))
        self.special_embed = nn.Parameter(torch.randn(1, 1, d_model))

    def forward(self, x, ordinary_count):
        type_emb = torch.cat([
            self.ordinary_embed.expand(x.size(0), ordinary_count, -1),
            self.special_embed.expand(x.size(0), x.size(1) - ordinary_count, -1),
        ], dim=1)
        return x + type_emb


class LotteryTransformer(nn.Module):
    """彩票预测 Transformer 模型。

    输入: (batch, n_periods, 7) — n 期，每期 7 个号码
    输出: 长度为 7 的 logits 列表，每个元素形状为 (batch, num_classes)
      - 前 ordinary_count 个: 普通号分类头，输出 ordinary_range 类
      - 后 special_count 个: 特别号分类头，输出 special_range 类
    """

    def __init__(self, config, lottery_config):
        """初始化模型各组件。

        Args:
            config: model_config 字典，含 embed_dim / num_heads / ff_dim / dropout / num_layers
            lottery_config: 彩票规则字典，含 ordinary_count / ordinary_range / special_count / special_range
        """
        super().__init__()
        self.lottery_config = lottery_config
        self.ordinary_count = lottery_config['ordinary_count']
        self.ordinary_range = lottery_config['ordinary_range']
        self.special_count = lottery_config['special_count']
        self.special_range = lottery_config['special_range']
        self.numbers_per_period = self.ordinary_count + self.special_count
        # 词表大小取两种号码范围的最大值 + 2（padding + 预留）
        self.max_vocab = max(self.ordinary_range, self.special_range) + 2

        embed_dim = config['embed_dim']

        # 号码值嵌入
        self.number_embedding = nn.Embedding(self.max_vocab, embed_dim)
        # 期数位置编码（第几期）
        self.period_position_embedding = nn.Embedding(100, embed_dim)
        # 期内位置编码（号码在期内的第几个位置 0~6）
        self.slot_position_embedding = nn.Embedding(self.numbers_per_period, embed_dim)
        # 普通号/特别号类型编码
        self.type_embedding = TypeEmbedding(embed_dim)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=config['num_heads'],
            dim_feedforward=config['ff_dim'],
            dropout=config['dropout'],
            batch_first=True,
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=config['num_layers'],
        )

        self.pos_encoding = PositionalEncoding(embed_dim)

        # 每个号码位置有独立的分类头
        # 普通号: 输出 ordinary_range 个类别（索引 0~ordinary_range-1 对应号码 1~ordinary_range）
        self.ordinary_heads = nn.ModuleList([
            nn.Linear(embed_dim, self.ordinary_range)
            for _ in range(self.ordinary_count)
        ])
        # 特别号: 输出 special_range 个类别
        self.special_heads = nn.ModuleList([
            nn.Linear(embed_dim, self.special_range)
            for _ in range(self.special_count)
        ])

    def forward(self, x):
        """前向传播。

        Args:
            x: (batch, n_periods, 7) 的号码值张量

        Returns:
            长度为 7 的 logits 列表，每个元素形状 (batch, num_classes)。
            前 ordinary_count 个为普通号分类头输出，后 special_count 个为特别号分类头输出。
        """
        batch_size, n_periods, num_per_period = x.shape

        # 展平为 (batch, n_periods * 7) 做嵌入
        x_flat = x.reshape(batch_size, n_periods * num_per_period)

        # 号码值嵌入
        embedded = self.number_embedding(x_flat)

        # + 期内位置编码（0~6 重复 n_periods 次）
        slot_ids = torch.arange(self.numbers_per_period, device=x.device).repeat(n_periods)
        embedded = embedded + self.slot_position_embedding(slot_ids)

        # + 期数位置编码（0~n_periods-1 每个 repeat 7 次）
        period_ids = torch.arange(n_periods, device=x.device).unsqueeze(1).repeat(1, self.numbers_per_period).reshape(-1)
        embedded = embedded + self.period_position_embedding(period_ids[:n_periods * self.numbers_per_period])

        # reshape 回 (batch, seq_len, embed_dim)，加类型编码
        embedded = embedded.reshape(batch_size, n_periods * self.numbers_per_period, -1)
        embedded = self.type_embedding(embedded, self.ordinary_count)

        # Transformer Encoder
        encoded = self.pos_encoding(embedded)
        encoded = self.transformer_encoder(encoded)

        # 取最后一期的 7 个 token 作为预测依据
        last_period_tokens = encoded[:, -self.numbers_per_period:, :]

        # 每个位置通过对应的分类头
        ordinary_outputs = []
        for i in range(self.ordinary_count):
            slot_repr = last_period_tokens[:, i, :]
            ordinary_outputs.append(self.ordinary_heads[i](slot_repr))

        special_outputs = []
        for i in range(self.special_count):
            slot_repr = last_period_tokens[:, self.ordinary_count + i, :]
            special_outputs.append(self.special_heads[i](slot_repr))

        all_outputs = ordinary_outputs + special_outputs
        return all_outputs