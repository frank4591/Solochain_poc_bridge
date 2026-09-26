#!/usr/bin/env python3
# Centralized MNIST + SimpleCNN training (no FL, no NVFlare).

import os
import time

import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms

from jobs.mnist_simplecnn.app.custom.simple_cnn import SimpleCNN


def main():
    device = os.environ.get("FL_DEVICE", "cpu")
    data_root = os.environ.get("MNIST_ROOT", "/tmp/nvflare/data")
    batch_size = int(os.environ.get("CENTRAL_BATCH_SIZE", "64"))
    epochs = int(os.environ.get("CENTRAL_EPOCHS", "5"))

    transform = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize((0.1307,), (0.3081,)),
        ]
    )

    trainset = torchvision.datasets.MNIST(root=data_root, train=True, download=True, transform=transform)
    testset = torchvision.datasets.MNIST(root=data_root, train=False, download=True, transform=transform)

    trainloader = torch.utils.data.DataLoader(trainset, batch_size=batch_size, shuffle=True, num_workers=0)
    testloader = torch.utils.data.DataLoader(testset, batch_size=batch_size, shuffle=False, num_workers=0)

    net = SimpleCNN().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(net.parameters(), lr=1e-3)

    print(f"Device: {device}, epochs={epochs}, batch_size={batch_size}")
    start = time.time()

    for epoch in range(epochs):
        net.train()
        running_loss = 0.0
        for i, data in enumerate(trainloader, 0):
            inputs, labels = data[0].to(device), data[1].to(device)
            optimizer.zero_grad()
            outputs = net(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()

            if (i + 1) % 100 == 0:
                print(f"[epoch {epoch + 1}, step {i + 1}] loss: {running_loss / 100:.4f}")
                running_loss = 0.0

        # Epoch-end evaluation
        net.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for data in testloader:
                images, labels = data[0].to(device), data[1].to(device)
                outputs = net(images)
                _, predicted = torch.max(outputs.data, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()
        acc = 100.0 * correct / total
        print(f"Epoch {epoch + 1}: test accuracy = {acc:.2f}% ({correct}/{total})")

    end = time.time()
    total_time = end - start
    print(f"\nCentralized training finished in {total_time:.2f} seconds.")


if __name__ == "__main__":
    main()

