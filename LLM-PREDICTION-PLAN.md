# LLM预测下一期中奖号码 - 技术方案

## 1. 功能需求

- 基于历史中奖数据，使用 GPT-2 Decoder-only 架构训练模型，预测下一期中奖号码
- 两种彩票（unionLotto / superLotto）各自独立训练专有模型
- 模型训练触发时机：
  - 首次启动：模型不存在 → 从零训练（全部数据）
  - 非首次启动：模型存在 → 增量训练（新增数据）
  - 爬取数据后：新数据入库 → 增量训练（新增数据）
- llm-prediction 独立启动，不依赖 server
- llm-prediction 训练状态变化后通过 SSE 通知观察者
- server 通过 SSE 监听 llm-prediction 的状态变化，再通过 SSE 推送给 frontend
- 前端根据状态显示：预测号码 / 模型更新中... / 预测服务未启动 / 训练失败

## 2. 架构设计

```
lottery-data/
├── config.json              # 共享配置（含 prediction.port）
├── frontend/                # Vue3 前端
├── server/                  # Koa 后端
├── llm-prediction/          # Python 模型服务（独立进程）
│   ├── model/
│   │   ├── lottery_gpt2.py  # GPT-2 模型适配层（token 映射、config 构建、模型创建/加载）
│   │   ├── dataset.py       # 数据集定义
│   │   └── trainer.py       # 训练器
│   ├── data/
│   │   └── processor.py     # 数据预处理/编码
│   ├── checkpoint/
│   │   ├── unionLotto/
│   │   │   ├── model.pt     # 模型权重
│   │   │   └── latest.json  # 训练状态
│   │   └── superLotto/
│   │       ├── model.pt
│   │       └── latest.json
│   ├── server.py            # Flask HTTP 服务 + SSE 事件推送
│   ├── train.py             # 训练/预测逻辑
│   └── pyproject.toml       # uv 项目配置
```

交互链路：

```
llm-prediction  ──SSE──»  server  ──SSE──»  frontend
   ↑                           ↑                    ↑
 Flask服务                   Koa中转              Vue3页面
 port 5006                  port 5005            port 8080
```

- llm-prediction 独立运行，不依赖 server 启动
- server 通过 SSE 监听 llm-prediction 的 `/api/events`，断线后 2s 自动重连
- server 生成唯一 observerId，llm-prediction 通过 observerId 去重，同一 id 替换旧观察者
- frontend 不直接与 llm-prediction 交互

## 3. llm-prediction API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/predict/<lotteryType>` | 获取预测结果 |
| POST | `/api/train/<lotteryType>?forceFull=true` | 触发训练（异步） |
| GET | `/api/status/<lotteryType>` | 查询训练状态 |
| GET | `/api/events?observerId=xxx` | SSE 事件流（训练状态变更通知） |

SSE 事件格式：

```
data: {"lotteryType":"unionLotto","status":"training"}
data: {"lotteryType":"unionLotto","status":"ready","prediction":[2,6,17,25,27,32,1]}
```

观察者去重：`observerId` 相同时替换旧观察者队列，防止重复监听。

## 4. 训练数据设计

### 4.1 滑动窗口

用前 n 期号码预测下一期号码，n 可配置：

```
n=5，总共 T=7 期数据:

训练样本:
  [1,2,3,4,5] → 预测第6期
  [2,3,4,5,6] → 预测第7期

预测: [3,4,5,6,7] → 预测第8期
```

增量训练（新增第8、9期后）：

```
  [3,4,5,6,7] → 预测第8期  (新增样本)
  [4,5,6,7,8] → 预测第9期  (新增样本)

预测: [5,6,7,8,9] → 预测第10期
```

### 4.2 数据编码

Token 映射：

```
PAD_TOKEN = 0
BOS_TOKEN = 1
EOS_TOKEN = 2
号码 → token: number_to_token(num) = num + 2
token → 号码: token_to_number(tok) = tok - 2
词表大小 VOCAB_SIZE = 39 (0~2 特殊 + 3~38 号码)
```

单期号码序列化：

```
[5, 15, 25, 26, 33, 6, 11]
  → [BOS, 7, 17, 27, 28, 35, 8, 13, EOS]
```

多期拼接为长序列：`BOS n₁ n₂ ... n₇ EOS BOS n₁ n₂ ... n₇ EOS ...`

### 4.3 模型输入/输出

GPT-2 语言模型范式（next-token prediction）：

```
输入: context 期 token 序列 + 目标期 BOS + n₁ n₂ ...
标签: 左偏移 1 位，context 部分置 -100（不计算 loss），目标部分为下一个 token

例: n=2, 序列 [BOS a₁...a₇ EOS BOS b₁...b₇ EOS BOS c₁]
    input_ids = [BOS a₁...a₇ EOS BOS b₁...b₇ EOS BOS c₁]
    labels    = [-100 -100...-100 -100  b₁...b₇ EOS BOS  c₂]  (context 部分全 -100)

模型输出: next-token logits, shape (batch, seq_len, VOCAB_SIZE=39)
```

### 4.4 普通号去重约束

自回归生成中的 masked greedy 解码：

```
输入: n 期 context + BOS → 逐步生成
步骤1: 取 logits，mask 掉非普通号 token → argmax → 得 a₁
步骤2: 取 logits，mask 掉 a₁ 对应 token → argmax → 得 a₂
...
普通号部分: 去重 mask，排序输出
特别号部分: 直接 argmax（不去重）
```

## 5. 两种彩票独立模型

| | unionLotto | superLotto |
|---|---|---|
| 普通号 | 6个 (1-33) | 5个 (1-35) |
| 特别号 | 1个 (1-16) | 2个 (1-12) |
| 每期号码数 | 7 | 7 |
| 词表大小 | 39 | 39 |
| 独立模型 | 有 | 有 |

## 6. 配置管理

config.json 统一管理：

```json
{
  "server": { "port": 5005 },
  "frontend": { "port": 8080 },
  "prediction": {
    "port": 5006,
    "n": 10,
    "model_config": {
      "vocab_size": 39,
      "n_positions": 128,
      "n_embd": 64,
      "n_head": 4,
      "n_layer": 4,
      "n_inner": 256,
      "resid_pdrop": 0.1,
      "embd_pdrop": 0.1,
      "attn_pdrop": 0.1,
      "activation_function": "gelu-new"
    },
    "training_config": {
      "epochs": 50,
      "batch_size": 32,
      "learning_rate": 0.001
    }
  }
}
```

n 改变后删除模型，重新从零训练。

## 7. Checkpoint 管理

```json
// checkpoint/superLotto/latest.json
{
  "n": 10,
  "latest_trained_issue": 22041,
  "total_periods_used": 15,
  "model_updated_at": "2024-01-01T00:00:00"
}
```

## 8. 前端交互

- 预测服务未启动：显示"预测服务未启动"
- 训练中：显示"模型更新中..."
- 训练完成：显示预测号码（普通号蓝球，特别号橙球）
- 训练失败：显示"模型训练失败，请稍后重试"
- 加载中：显示"加载中..."

## 9. 技术选型

| 类别 | 选择 |
|---|---|
| 语言 | Python 3.13+ |
| 包管理 | uv |
| 深度学习框架 | PyTorch |
| Transformer | GPT-2（HuggingFace Transformers） |
| 模型服务 | Flask |
| 事件推送 | SSE（观察者模式 + observerId 去重） |
| 后端 | Koa + koa-bodyparser |
| 前端 | Vue3 + Element Plus |