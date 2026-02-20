"""
Builder de dataset YOLOv8 (IMAGENS APENAS) a partir de PDFs do ENEM.

O pipeline:
- Lê PDFs da pasta ./pdf
- IGNORA a página 1 (page_idx == 0)
- Renderiza páginas restantes em PNG (300 DPI)
- NÃO gera labels (anotação será manual)
- Cria automaticamente o arquivo data.yaml

Uso:
- Este script prepara SOMENTE as imagens
- O labeling deve ser feito manualmente depois
"""

import fitz  # PyMuPDF
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
LBL_DIR.mkdir(parents=True, exist_ok=True)  # vazio por enquanto

# ============================
# PROCESSAMENTO DO PDF
# ============================

def process_pdf(pdf_path: Path):
    doc = fitz.open(pdf_path)

    for page_idx, page in enumerate(doc):

        # ❌ IGNORAR PRIMEIRA PÁGINA
        if page_idx == 0:
            continue

        pix = page.get_pixmap(dpi=DPI)

        img_name = f"{pdf_path.stem}_p{page_idx:03}.png"
        img_path = IMG_DIR / img_name

        pix.save(img_path)
        print(f"  ✔ imagem salva: {img_name}")


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
    print(f"\n✔ data.yaml criado em {yaml_path}")


# ============================
# MAIN
# ============================

if __name__ == "__main__":
    pdfs = list(PDF_DIR.glob("*.pdf"))

    print(f"Encontrados {len(pdfs)} PDFs\n")

    for pdf in pdfs:
        print(f"→ Processando {pdf.name}")
        process_pdf(pdf)

    write_data_yaml()

    print("\nDataset de imagens gerado com sucesso (pronto para anotação manual).")
