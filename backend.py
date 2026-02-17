from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pathlib import Path
import base64
from PIL import Image

# ===============================
# App
# ===============================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent

BASE_DIR = Path(__file__).resolve().parent
ROTULAGEM_FILE = BASE_DIR / "rotulagem.html"

CAPTURE_DIR = BASE_DIR / "captura"

@app.get("/rotulagem", response_class=HTMLResponse)
def serve_capture():
    return ROTULAGEM_FILE.read_text(encoding="utf-8")


class LabelPayload(BaseModel):
    filename: str              # Nome da imagem temporária
    labels: list               # Lista de dicts: {class_id, x, y, w, h} normalizados



# ===============================
# Endpoint /label – salvar rotulagem YOLO
# ===============================
DATASET_DIR = BASE_DIR / "dataset_full"
IMAGES_DIR = DATASET_DIR / "images"
LABELS_DIR = DATASET_DIR / "labels"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
LABELS_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/next")
def next_label():
    """
    Retorna a próxima imagem para rotulagem.
    """
    # Lista as imagens temporárias
    images = sorted(CAPTURE_DIR.glob("*.png"))

    if not images:
        return {"status": "empty", "message": "Não há imagens para rotular"}

    next_image = images[0]  # pega a primeira da lista

    # Abre e converte para base64
    with open(next_image, "rb") as f:
        image_bytes = f.read()
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    return {
        "status": "ok",
        "filename": next_image.name,
        "image": f"data:image/jpeg;base64,{encoded_image}"
    }

@app.post("/label")
def label_image(payload: LabelPayload):
    """
    Recebe a imagem temporária e os labels do front, salva no formato YOLO e remove a imagem temporária.
    """
    tmp_file = CAPTURE_DIR / payload.filename
    if not tmp_file.exists():
        return {"status": "error", "message": "Imagem não encontrada"}

    # Abrir imagem
    image = Image.open(tmp_file)
    w, h = image.width, image.height

    # Salvar imagem no dataset
    dst_image_path = IMAGES_DIR / payload.filename
    image.save(dst_image_path, format="JPEG", quality=90)

    # Criar arquivo YOLO .txt
    txt_path = LABELS_DIR / (payload.filename.replace(".png", ".txt"))
    with open(txt_path, "w") as f:
        for label in payload.labels:
            # class_id, x, y, w, h (normalizados)
            f.write(f"{label['class_id']} {label['x']} {label['y']} {label['w']} {label['h']}\n")

    # Remover imagem temporária
    tmp_file.unlink()
    print(f"✅ Imagem rotulada e movida para dataset: {payload.filename}")

    return {"status": "ok", "image": str(dst_image_path.name), "labels": len(payload.labels)}



# ===============================
# Endpoint /delete – mover imagem para delete/
# ===============================
DELETE_DIR = BASE_DIR / "delete"
DELETE_DIR.mkdir(exist_ok=True)

class DeletePayload(BaseModel):
    filename: str

@app.post("/delete")
def delete_image(payload: DeletePayload):
    tmp_file = CAPTURE_DIR / payload.filename
    if not tmp_file.exists():
        return {"status": "error", "message": "Imagem não encontrada"}

    dst_file = DELETE_DIR / payload.filename
    tmp_file.rename(dst_file)  # move para delete/

    print(f"🗑 Imagem movida para delete/: {payload.filename}")
    return {"status": "ok", "message": f"{payload.filename} movida para delete/"}
