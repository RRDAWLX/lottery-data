import os
import torch
from torch.utils.data import DataLoader
from .lottery_gpt2 import create_model, load_model_from_checkpoint, save_model
from .dataset import LotteryLMDataset, collate_fn


def train(lottery_type, input_ids_list, labels_list, prediction_config, checkpoint_dir, model_state_dict_path=None):
    os.makedirs(checkpoint_dir, exist_ok=True)

    model_config = prediction_config['model_config']
    training_config = prediction_config['training_config']

    if model_state_dict_path is not None and os.path.exists(model_state_dict_path):
        model = load_model_from_checkpoint(model_state_dict_path, model_config)
    else:
        model = create_model(model_config)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = model.to(device)

    dataset = LotteryLMDataset(input_ids_list, labels_list)
    dataloader = DataLoader(
        dataset,
        batch_size=training_config['batch_size'],
        shuffle=True,
        drop_last=False,
        collate_fn=collate_fn,
    )

    optimizer = torch.optim.AdamW(model.parameters(), lr=training_config['learning_rate'])

    model.train()
    for epoch in range(training_config['epochs']):
        total_loss = 0.0
        for batch in dataloader:
            batch = {k: v.to(device) for k, v in batch.items()}
            optimizer.zero_grad()
            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        avg_loss = total_loss / len(dataloader) if len(dataloader) > 0 else 0
        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"[{lottery_type}] Epoch {epoch+1}/{training_config['epochs']}, Loss: {avg_loss:.4f}")

    model_path = os.path.join(checkpoint_dir, 'model.pt')
    save_model(model, model_path)

    return model