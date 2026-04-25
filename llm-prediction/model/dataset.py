import torch
from torch.utils.data import Dataset

PAD_TOKEN = 0


class LotteryLMDataset(Dataset):
    def __init__(self, input_ids_list, labels_list):
        self.input_ids = input_ids_list
        self.labels = labels_list

    def __len__(self):
        return len(self.input_ids)

    def __getitem__(self, idx):
        return {
            'input_ids': torch.tensor(self.input_ids[idx], dtype=torch.long),
            'labels': torch.tensor(self.labels[idx], dtype=torch.long),
        }


def collate_fn(batch):
    max_len = max(item['input_ids'].size(0) for item in batch)
    input_ids = []
    labels = []
    attention_mask = []
    for item in batch:
        seq_len = item['input_ids'].size(0)
        pad_len = max_len - seq_len
        input_ids.append(
            torch.cat([item['input_ids'], torch.full((pad_len,), PAD_TOKEN, dtype=torch.long)])
        )
        labels.append(
            torch.cat([item['labels'], torch.full((pad_len,), -100, dtype=torch.long)])
        )
        attention_mask.append(
            torch.cat([torch.ones(seq_len, dtype=torch.long), torch.zeros(pad_len, dtype=torch.long)])
        )
    return {
        'input_ids': torch.stack(input_ids),
        'labels': torch.stack(labels),
        'attention_mask': torch.stack(attention_mask),
    }