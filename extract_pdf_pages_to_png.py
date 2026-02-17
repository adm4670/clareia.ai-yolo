import fitz  # PyMuPDF
from pathlib import Path

# Diretório raiz do projeto (onde o script está)
ROOT_DIR = Path(__file__).resolve().parent

PROVAS_DIR = ROOT_DIR / "provas"
CAPTURA_DIR = ROOT_DIR / "captura"

def sanitize_filename(name: str) -> str:
    """
    Remove caracteres problemáticos para nomes de arquivo
    """
    return (
        name.replace(" ", "_")
            .replace("/", "_")
            .replace("\\", "_")
            .replace("(", "")
            .replace(")", "")
    )

def pdf_to_images(pdf_path: Path):
    ano = pdf_path.parent.name
    caderno = sanitize_filename(pdf_path.stem)

    CAPTURA_DIR.mkdir(exist_ok=True)

    doc = fitz.open(pdf_path)

    for page_index in range(len(doc)):
        page = doc[page_index]

        zoom = 2  # ~300 DPI
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        image_name = f"{ano}_{caderno}_page_{page_index + 1:03}.png"
        image_path = CAPTURA_DIR / image_name

        pix.save(image_path)
        print(f"✅ {image_name}")

    doc.close()

def process_all_pdfs():
    for pdf_path in PROVAS_DIR.rglob("*.pdf"):
        print(f"\n📄 Processando: {pdf_path}")
        pdf_to_images(pdf_path)

if __name__ == "__main__":
    process_all_pdfs()
