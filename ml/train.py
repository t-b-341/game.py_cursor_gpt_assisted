"""Training script for the DDA model.

Usage:
    python -m ml.train                          # Train with default settings
    python -m ml.train --db my_telemetry.db     # Use specific database
    python -m ml.train --epochs 500 --lr 0.001  # Custom hyperparameters
    python -m ml.train --gpu                     # Use GPU (4080 Super)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Try to import PyTorch
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("PyTorch not installed. Install with: pip install torch")
    print("For GPU support with your 4080 Super:")
    print("  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121")
    sys.exit(1)

from .features import load_training_data, get_training_stats, FEATURE_NAMES
from .dda_model import DDAModel, DEFAULT_MODEL_PATH


def train_dda_model(
    db_path: str = "game_telemetry.db",
    epochs: int = 200,
    batch_size: int = 32,
    learning_rate: float = 0.001,
    use_gpu: bool = False,
    validation_split: float = 0.2,
    verbose: bool = True,
) -> tuple[DDAModel, dict]:
    """Train the DDA model on telemetry data.
    
    Args:
        db_path: Path to telemetry SQLite database
        epochs: Number of training epochs
        batch_size: Batch size for training
        learning_rate: Learning rate for optimizer
        use_gpu: Whether to use GPU (requires CUDA)
        validation_split: Fraction of data for validation
        verbose: Print training progress
    
    Returns:
        Tuple of (trained model, training stats dict)
    """
    # Check data availability
    stats = get_training_stats(db_path)
    if verbose:
        print(f"\n=== Training Data Statistics ===")
        print(f"Total waves: {stats['total_waves']}")
        print(f"Total runs: {stats['total_runs']}")
        print(f"Avg wave duration: {stats.get('avg_wave_duration', 0):.1f}s")
        print(f"Outcome distribution: {stats.get('outcomes', {})}")
    
    if stats["total_waves"] < 10:
        print(f"\nInsufficient training data ({stats['total_waves']} waves).")
        print("Play more games with telemetry enabled to collect data!")
        return None, stats
    
    # Load data
    features, targets = load_training_data(db_path)
    
    if len(features) < 10:
        print(f"\nInsufficient valid samples ({len(features)}).")
        return None, stats
    
    # Convert to tensors
    X = torch.tensor(features, dtype=torch.float32)
    y = torch.tensor(targets, dtype=torch.float32)
    
    # Split into train/val
    n_val = int(len(X) * validation_split)
    n_train = len(X) - n_val
    
    indices = torch.randperm(len(X))
    train_idx = indices[:n_train]
    val_idx = indices[n_train:]
    
    X_train, y_train = X[train_idx], y[train_idx]
    X_val, y_val = X[val_idx], y[val_idx]
    
    if verbose:
        print(f"\nTraining samples: {len(X_train)}")
        print(f"Validation samples: {len(X_val)}")
    
    # Create data loaders
    train_dataset = TensorDataset(X_train, y_train)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    
    # Setup device
    device = torch.device("cuda" if use_gpu and torch.cuda.is_available() else "cpu")
    if verbose:
        print(f"\nTraining on: {device}")
        if device.type == "cuda":
            print(f"GPU: {torch.cuda.get_device_name()}")
    
    # Create model
    model = DDAModel()._create_model().to(device)
    
    # Setup training
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=20, verbose=verbose
    )
    loss_fn = nn.MSELoss()
    
    # Training loop
    best_val_loss = float("inf")
    best_state_dict = None
    training_history = {"train_loss": [], "val_loss": []}
    
    if verbose:
        print(f"\n=== Training for {epochs} epochs ===\n")
    
    for epoch in range(epochs):
        # Training phase
        model.train()
        train_losses = []
        
        for batch_X, batch_y in train_loader:
            batch_X = batch_X.to(device)
            batch_y = batch_y.to(device)
            
            optimizer.zero_grad()
            pred = model(batch_X)
            loss = loss_fn(pred, batch_y)
            loss.backward()
            optimizer.step()
            
            train_losses.append(loss.item())
        
        avg_train_loss = sum(train_losses) / len(train_losses)
        
        # Validation phase
        model.eval()
        with torch.no_grad():
            X_val_dev = X_val.to(device)
            y_val_dev = y_val.to(device)
            val_pred = model(X_val_dev)
            val_loss = loss_fn(val_pred, y_val_dev).item()
        
        training_history["train_loss"].append(avg_train_loss)
        training_history["val_loss"].append(val_loss)
        
        # Learning rate scheduling
        scheduler.step(val_loss)
        
        # Save best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state_dict = model.state_dict().copy()
        
        # Print progress
        if verbose and (epoch + 1) % 20 == 0:
            print(f"Epoch {epoch + 1:3d}/{epochs}: "
                  f"train_loss={avg_train_loss:.4f}, val_loss={val_loss:.4f}")
    
    # Load best model
    if best_state_dict is not None:
        model.load_state_dict(best_state_dict)
    
    # Save model
    DEFAULT_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), DEFAULT_MODEL_PATH)
    
    if verbose:
        print(f"\n=== Training Complete ===")
        print(f"Best validation loss: {best_val_loss:.4f}")
        print(f"Model saved to: {DEFAULT_MODEL_PATH}")
    
    # Create DDAModel wrapper with trained weights
    dda_model = DDAModel()
    dda_model._model.load_state_dict(model.cpu().state_dict())
    
    training_stats = {
        "epochs": epochs,
        "final_train_loss": training_history["train_loss"][-1],
        "final_val_loss": training_history["val_loss"][-1],
        "best_val_loss": best_val_loss,
        "training_samples": len(X_train),
        "validation_samples": len(X_val),
    }
    
    return dda_model, training_stats


def main():
    """CLI entry point for training."""
    parser = argparse.ArgumentParser(description="Train the DDA model")
    parser.add_argument("--db", default="game_telemetry.db", help="Telemetry database path")
    parser.add_argument("--epochs", type=int, default=200, help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--lr", type=float, default=0.001, help="Learning rate")
    parser.add_argument("--gpu", action="store_true", help="Use GPU (CUDA)")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")
    
    args = parser.parse_args()
    
    train_dda_model(
        db_path=args.db,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        use_gpu=args.gpu,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
