import streamlit as st
from pathlib import Path
from PIL import Image
from streamlit_drawable_canvas import st_canvas

# ============================
# CONFIG
# ============================

ROOT = Path(__file__).resolve().parent
IMG_DIR = ROOT / "dataset" / "images" / "train"
LBL_DIR = ROOT / "dataset" / "labels" / "train"

LBL_DIR.mkdir(parents=True, exist_ok=True)

CLASSES = {
    0: "question_block",
    1: "statement_text",
    2: "statement_image",
    3: "alternative_text",
    4: "alternative_image",
}

# ============================
# STATE
# ============================

if "img_idx" not in st.session_state:
    st.session_state.img_idx = 0

# ============================
# UTILS
# ============================

def to_yolo(box, img_w, img_h):
    x = box["left"]
    y = box["top"]
    w = box["width"]
    h = box["height"]

    cx = (x + w / 2) / img_w
    cy = (y + h / 2) / img_h
    bw = w / img_w
    bh = h / img_h

    return round(cx, 6), round(cy, 6), round(bw, 6), round(bh, 6)


def save_labels(img_name, objects, img_w, img_h):
    label_path = LBL_DIR / img_name.replace(".png", ".txt")

    with open(label_path, "w") as f:
        for obj in objects:
            cls = int(obj["class_id"])
            bbox = to_yolo(obj, img_w, img_h)
            f.write(f"{cls} {' '.join(map(str, bbox))}\n")


# ============================
# UI
# ============================

st.set_page_config(layout="wide")
st.title("🖊️ ENEM – YOLO Labeling Tool")

images = sorted(IMG_DIR.glob("*.png"))

if not images:
    st.error("Nenhuma imagem encontrada em dataset/images/train")
    st.stop()

img_path = images[st.session_state.img_idx]
image = Image.open(img_path)
img_w, img_h = image.size

# ----------------------------
# SIDEBAR
# ----------------------------

st.sidebar.header("Configurações")

class_name = st.sidebar.selectbox(
    "Classe atual",
    list(CLASSES.values())
)

class_id = [k for k, v in CLASSES.items() if v == class_name][0]

if st.sidebar.button("⬅️ Anterior") and st.session_state.img_idx > 0:
    st.session_state.img_idx -= 1
    st.experimental_rerun()

if st.sidebar.button("➡️ Próxima") and st.session_state.img_idx < len(images) - 1:
    st.session_state.img_idx += 1
    st.experimental_rerun()

st.sidebar.markdown(f"""
**Imagem:** {img_path.name}  
**Progresso:** {st.session_state.img_idx + 1} / {len(images)}
""")

# ----------------------------
# CANVAS
# ----------------------------

canvas = st_canvas(
    fill_color="rgba(255, 0, 0, 0.3)",
    stroke_width=2,
    stroke_color="#ff0000",
    background_image=image,
    update_streamlit=True,
    height=img_h,
    width=img_w,
    drawing_mode="rect",
    key="canvas",
)

# ----------------------------
# SAVE
# ----------------------------

if st.button("💾 Salvar labels"):
    if canvas.json_data and "objects" in canvas.json_data:
        objects = canvas.json_data["objects"]

        for obj in objects:
            obj["class_id"] = class_id

        save_labels(img_path.name, objects, img_w, img_h)
        st.success("Labels salvos com sucesso!")

    else:
        st.warning("Nenhuma bounding box desenhada.")
