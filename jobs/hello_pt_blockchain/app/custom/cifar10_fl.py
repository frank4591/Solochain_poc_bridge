# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
# POC job: CIFAR10 FL with NVFlare client API (min_clients=1 for blockchain bridge).

import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms
from net import Net

import nvflare.client as flare
from nvflare.client.tracking import SummaryWriter

DATASET_PATH = "/tmp/nvflare/data"
DEVICE = "cpu"  # Use CPU for POC; set to "cuda:0" if GPU available


def main():
    transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))])
    batch_size = 4
    epochs = 2

    trainset = torchvision.datasets.CIFAR10(root=DATASET_PATH, train=True, download=True, transform=transform)
    trainloader = torch.utils.data.DataLoader(trainset, batch_size=batch_size, shuffle=True, num_workers=0)
    testset = torchvision.datasets.CIFAR10(root=DATASET_PATH, train=False, download=True, transform=transform)
    testloader = torch.utils.data.DataLoader(testset, batch_size=batch_size, shuffle=False, num_workers=0)

    net = Net()
    flare.init()
    summary_writer = SummaryWriter()

    while flare.is_running():
        input_model = flare.receive()
        print(f"current_round={input_model.current_round}")
        net.load_state_dict(input_model.params)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.SGD(net.parameters(), lr=0.001, momentum=0.9)
        net.to(DEVICE)
        steps = epochs * len(trainloader)

        for epoch in range(epochs):
            running_loss = 0.0
            for i, data in enumerate(trainloader, 0):
                inputs, labels = data[0].to(DEVICE), data[1].to(DEVICE)
                optimizer.zero_grad()
                outputs = net(inputs)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()
                running_loss += loss.item()
                if i % 2000 == 1999:
                    print(f"[{epoch + 1}, {i + 1:5d}] loss: {running_loss / 2000:.3f}")
                    global_step = input_model.current_round * steps + epoch * len(trainloader) + i
                    summary_writer.add_scalar(tag="loss_for_each_batch", scalar=running_loss, global_step=global_step)
                    running_loss = 0.0
        print("Finished Training")

        def evaluate(input_weights):
            net_eval = Net()
            net_eval.load_state_dict(input_weights)
            net_eval.to(DEVICE)
            correct = 0
            total = 0
            with torch.no_grad():
                for data in testloader:
                    images, labels = data[0].to(DEVICE), data[1].to(DEVICE)
                    outputs = net_eval(images)
                    _, predicted = torch.max(outputs.data, 1)
                    total += labels.size(0)
                    correct += (predicted == labels).sum().item()
            print(f"Accuracy of the network on the 10000 test images: {100 * correct // total} %")
            return 100 * correct // total

        accuracy = evaluate(input_model.params)
        output_model = flare.FLModel(
            params=net.cpu().state_dict(),
            metrics={"accuracy": accuracy},
            meta={"NUM_STEPS_CURRENT_ROUND": steps},
        )
        flare.send(output_model)


if __name__ == "__main__":
    main()
