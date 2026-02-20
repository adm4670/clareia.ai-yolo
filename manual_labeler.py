# manual_labeler.py
# --------------------------------------------------
# PDF -> imagens -> labeling YOLO (train/val/test)
# Script corrigido com inicialização segura do session_state
# --------------------------------------------------

import streamlit as st
from pathlib import Path
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import fitz  # PyMuPDF
import json
import random
import yaml

# ============================
# CONFIG
# ============================

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "dataset"
PDF_DIR = ROOT / "pdfs"

SPLITS = ["train", "val", "test"]

CLASSES = {
    0: "question_block",
    1: "statement_text",
    2: "statement_image",
    3: "alternative_text",
    4: "alternative_image",
}

CLASS_COLORS = {
    0: "#ff0000",
    1: "#00ff00",
    2: "#0000ff",
    3: "#ffff00",
    4: "#ff00ff",
}

IMG_SIZE_DPI = 200
STATE_FILE = DATASET / "labeling_state.json"

# ============================
# INIT DIRS
# ============================

for s in SPLITS:
    (DATASET / "images" / s).mkdir(parents=True, exist_ok=True)
    (DATASET / "labels" / s).mkdir(parents=True, exist_ok=True)

PDF_DIR.mkdir(exist_ok=True)

# ============================
# UTILS
# ============================

def pdf_to_images():
    pages = []
    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        doc = fitz.open(pdf)
        for i, page in enumerate(doc):
            name = f"{pdf.stem}_p{i}.png"
            out = DATASET / "images" / "train" / name
            if out.exists():
                pages.append(name)
                continue
            pix = page.get_pixmap(dpi=IMG_SIZE_DPI)
            pix.save(out)
            pages.append(name)
    return pages


def split_dataset():
    imgs = sorted((DATASET / "images" / "train").glob("*.png"))
    random.shuffle(imgs)
    n = len(imgs)
    train_end = int(n * 0.8)
    val_end = int(n * 0.9)

    splits = {
        "train": imgs[:train_end],
        "val": imgs[train_end:val_end],
        "test": imgs[val_end:],
    }

    for split, files in splits.items():
        for img in files:
            target = DATASET / "images" / split / img.name
            if not target.exists():
                img.rename(target)


def to_yolo(box, img_w, img_h):
    x, y, w, h = box["left"], box["top"], box["width"], box["height"]
    cx = (x + w / 2) / img_w
    cy = (y + h / 2) / img_h
    return round(cx, 6), round(cy, 6), round(w / img_w, 6), round(h / img_h, 6)


def save_labels(img_path, objects):
    split = img_path.parts[-2]
    lbl = DATASET / "labels" / split / img_path.with_suffix(".txt").name
    with open(lbl, "w") as f:
        for o in objects:
            yolo = to_yolo(o, o["img_w"], o["img_h"])
            f.write(f"{o['class_id']} {' '.join(map(str, yolo))}\n")


def save_state(idx):
    with open(STATE_FILE, "w") as f:
        json.dump({"idx": idx}, f)


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text()).get("idx", 0)
    return 0


def write_data_yaml():
    data = {
        "path": str(DATASET),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": CLASSES,
    }
    with open(DATASET / "data.yaml", "w") as f:
        yaml.dump(data, f)

# ============================
# PREPARE DATA (RUN ONCE)
# ============================

if not any((DATASET / "images" / "train").glob("*.png")):
    pdf_to_images()
    split_dataset()
    write_data_yaml()

# ============================
# STREAMLIT STATE (SAFE INIT)
# ============================

if "idx" not in st.session_state:
    st.session_state.idx = load_state()

# ============================
# UI
# ============================

st.set_page_config(layout="wide")
st.title("📄 ENEM PDF → YOLO Labeling")

images = sorted((DATASET / "images" / "train").glob("*.png"))

if not images:
    st.error("Nenhuma imagem encontrada")
    st.stop()

if st.session_state.idx >= len(images):
    st.session_state.idx = 0
    save_state(0)

img_path = images[st.session_state.idx]
image = Image.open(img_path)
img_w, img_h = image.size

# Sidebar
st.sidebar.header("Classe")
class_name = st.sidebar.radio("Selecione", list(CLASSES.values()))
class_id = [k for k, v in CLASSES.items() if v == class_name][0]

st.sidebar.markdown(f"**Imagem:** {img_path.name}")
st.sidebar.markdown(f"**Progresso:** {st.session_state.idx + 1}/{len(images)}")

if st.sidebar.button("⬅️ Anterior") and st.session_state.idx > 0:
    st.session_state.idx -= 1
    save_state(st.session_state.idx)
    st.experimental_rerun()

if st.sidebar.button("➡️ Próxima") and st.session_state.idx < len(images) - 1:
    st.session_state.idx += 1
    save_state(st.session_state.idx)
    st.experimental_rerun()

# Canvas
canvas = st_canvas(
    fill_color=f"{CLASS_COLORS[class_id]}33",
    stroke_color=CLASS_COLORS[class_id],
    stroke_width=2,
    background_image=image,
    height=img_h,
    width=img_w,
    drawing_mode="rect",
    key=f"canvas_{img_path.name}",
)

# Save
if st.button("💾 Salvar"):
    if canvas.json_data and "objects" in canvas.json_data:
        objs = []
        for o in canvas.json_data["objects"]:
            o["class_id"] = class_id
            o["img_w"] = img_w
            o["img_h"] = img_h
            objs.append(o)

        save_labels(img_path, objs)
        save_state(st.session_state.idx)
        st.success("Labels salvos ✔")
    else:
        st.warning("Nenhuma bbox desenhada")
