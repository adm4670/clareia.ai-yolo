import torch

print("CUDA disponível:", torch.cuda.is_available())
print("Qtd de GPUs:", torch.cuda.device_count())

for i in range(torch.cuda.device_count()):
    print(f"GPU {i}:", torch.cuda.get_device_name(i))



import torch

DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Device selecionado: {DEVICE}")

