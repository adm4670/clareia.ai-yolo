"""
Pipeline para criação de dataset YOLOv8 a partir de PDFs do ENEM.

O pipeline:
- Lê PDFs da pasta ./pdf
- Renderiza páginas em PNG (300 DPI)
- Aplica heurísticas de layout (weak labeling)
- Gera labels no formato YOLO
- Cria automaticamente o arquivo data.yaml

IMPORTANTE:
Este pipeline gera *weak labels*.
Ele NÃO substitui anotação humana — apenas acelera o bootstrap.

Dependências:
- pymupdf
- opencv-python
- pillow
- pytesseract (opcional)
"""

import re
import fitz  # PyMuPDF
import cv2
from pathlib import Path

# ============================
# CONFIGURAÇÕES
# ============================

ROOT = Path(__file__).resolve().parent

PDF_DIR = ROOT / "pdf"
DATASET_DIR = ROOT / "dataset"

IMG_DIR = DATASET_DIR / "images" / "train"
LBL_DIR = DATASET_DIR / "labels" / "train"

DPI = 300

CLASSES = {
    "question_block": 0,
    "statement_text": 1,
    "statement_image": 2,
    "alternative_text": 3,
    "alternative_image": 4,
}

# ============================
# SETUP DE DIRETÓRIOS
# ============================

IMG_DIR.mkdir(parents=True, exist_ok=True)
LBL_DIR.mkdir(parents=True, exist_ok=True)

# ============================
# UTILITÁRIOS
# ============================

def normalize_bbox(bbox, img_w, img_h):
    """
    Converte bbox (x0,y0,x1,y1) → YOLO (cx,cy,w,h) normalizado
    """
    x0, y0, x1, y1 = bbox
    cx = ((x0 + x1) / 2) / img_w
    cy = ((y0 + y1) / 2) / img_h
    bw = (x1 - x0) / img_w
    bh = (y1 - y0) / img_h
    return round(cx, 6), round(cy, 6), round(bw, 6), round(bh, 6)


def save_labels(path, labels):
    with open(path, "w", encoding="utf-8") as f:
        for l in labels:
            f.write(" ".join(map(str, l)) + "\n")


# ============================
# HEURÍSTICAS
# ============================

def is_question_header(text: str) -> bool:
    return bool(re.search(r"QUEST[AÃ]O\s+\d+", text.upper()))


def is_alternative(text: str) -> bool:
    return bool(re.match(r"^[A-E]\)", text.strip()))


# ============================
# PROCESSAMENTO DO PDF
# ============================

def process_pdf(pdf_path: Path):
    doc = fitz.open(pdf_path)

    for page_idx, page in enumerate(doc):
        pix = page.get_pixmap(dpi=DPI)

        img_name = f"{pdf_path.stem}_p{page_idx:03}.png"
        img_path = IMG_DIR / img_name
        pix.save(img_path)

        image = cv2.imread(str(img_path))
        img_h, img_w = image.shape[:2]

        labels = []
        blocks = page.get_text("blocks")

        # ----------------------------
        # QUESTION BLOCK
        # ----------------------------
        question_boxes = []

        for b in blocks:
            x0, y0, x1, y1, text, *_ = b
            if is_question_header(text):
                question_boxes.append((x0, y0, x1, y1))

        if not question_boxes:
            question_boxes = [(0, 0, img_w, img_h)]

        for qb in question_boxes:
            cx, cy, bw, bh = normalize_bbox(qb, img_w, img_h)
            labels.append([CLASSES["question_block"], cx, cy, bw, bh])

        # ----------------------------
        # TEXTOS / ALTERNATIVAS
        # ----------------------------
        for b in blocks:
            x0, y0, x1, y1, text, *_ = b

            if len(text.strip()) < 5:
                continue

            if is_alternative(text):
                cls = "alternative_text"
            else:
                cls = "statement_text"

            cx, cy, bw, bh = normalize_bbox((x0, y0, x1, y1), img_w, img_h)
            labels.append([CLASSES[cls], cx, cy, bw, bh])

        # ----------------------------
        # IMAGENS
        # ----------------------------
        for img in page.get_images(full=True):
            bbox = page.get_image_bbox(img)
            if not bbox:
                continue

            cx, cy, bw, bh = normalize_bbox(bbox, img_w, img_h)
            labels.append([CLASSES["statement_image"], cx, cy, bw, bh])

        # ----------------------------
        # SALVAR LABEL
        # ----------------------------
        label_path = LBL_DIR / img_name.replace(".png", ".txt")
        save_labels(label_path, labels)


# ============================
# DATA.YAML
# ============================

def write_data_yaml():
    yaml_path = DATASET_DIR / "data.yaml"

    content = f"""path: {DATASET_DIR.as_posix()}
train: images/train
val: images/train

nc: {len(CLASSES)}
names:
"""

    for name, idx in CLASSES.items():
        content += f"  {idx}: {name}\n"

    yaml_path.write_text(content, encoding="utf-8")
    print(f"✔ data.yaml criado em {yaml_path}")


# ============================
# MAIN
# ============================

if __name__ == "__main__":
    pdfs = list(PDF_DIR.glob("*.pdf"))

    print(f"Encontrados {len(pdfs)} PDFs")

    for pdf in pdfs:
        print(f"→ Processando {pdf.name}")
        process_pdf(pdf)

    write_data_yaml()

    print("\nDataset YOLO inicial gerado com sucesso.")
