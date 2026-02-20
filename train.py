"""
Treinamento YOLOv8 para detecção estrutural de questões do ENEM

Assume que o dataset já está no formato:

dataset/
 ├── images/
 │    ├── train/
 │    ├── val/
 │    └── test/
 ├── labels/
 │    ├── train/
 │    ├── val/
 │    └── test/
 └── data.yaml

Classes:
0: question_block
1: statement_text
2: statement_image
3: alternative_text
4: alternative_image

Framework:
- ultralytics (YOLOv8)

Instalação:
  pip install ultralytics

Recomendado GPU (CUDA).
"""

from ultralytics import YOLO
from pathlib import Path

# ============================
# CONFIGURAÇÕES
# ============================

DATASET_YAML = Path("dataset/data.yaml")

# Modelo base (pré-treinado)
MODEL_NAME = "yolov8m.pt"  # yolov8n.pt | yolov8s.pt | yolov8m.pt

# Hiperparâmetros principais
EPOCHS = 100
IMG_SIZE = 1280
BATCH = 8
WORKERS = 8

PROJECT_NAME = "enem_yolo"
RUN_NAME = "v1_structural_detection"

# ============================
# TREINAMENTO
# ============================

def train():
    model = YOLO(MODEL_NAME)

    model.train(
        data=str(DATASET_YAML),
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=BATCH,
        workers=WORKERS,
        device="cpu",               # 0 = primeira GPU | 'cpu' para CPU
        project=PROJECT_NAME,
        name=RUN_NAME,
        pretrained=True,
        optimizer="AdamW",
        lr0=1e-3,
        cos_lr=True,
        patience=20,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=0.0,
        translate=0.05,
        scale=0.5,
        shear=0.0,
        perspective=0.0,
        flipud=0.0,
        fliplr=0.0,
        mosaic=0.2,
        mixup=0.0,
        copy_paste=0.0,
        close_mosaic=10,
    )


# ============================
# VALIDAÇÃO
# ============================

def validate():
    model = YOLO(f"runs/detect/{RUN_NAME}/weights/best.pt")

    metrics = model.val(
        data=str(DATASET_YAML),
        imgsz=IMG_SIZE,
        batch=BATCH,
        device=0,
    )

    print("Validação concluída")
    print(metrics)


# ============================
# INFERÊNCIA DE TESTE
# ============================

def infer_sample():
    model = YOLO(f"runs/detect/{RUN_NAME}/weights/best.pt")

    model.predict(
        source="dataset/images/test",
        imgsz=IMG_SIZE,
        conf=0.25,
        iou=0.5,
        save=True,
        project=PROJECT_NAME,
        name="inference_test",
    )


# ============================
# EXECUÇÃO
# ============================

if __name__ == "__main__":
    train()
    validate()
    infer_sample()
