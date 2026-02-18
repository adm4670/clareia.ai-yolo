import os
import re
import fitz  # PyMuPDF
import base64
from pathlib import Path
from openai import OpenAI

from pathlib import Path
import re

def ler_labels_yolo(path="dataset_full/labels"):
    resultados = []

    padrao_nome = re.compile(
        r'(?P<ano>\d{4})_(?P<arquivo>.+?)_page_(?P<page>\d+)\.txt$'
    )

    path = Path(path)

    for arquivo_label in path.iterdir():
        if arquivo_label.suffix != ".txt":
            continue

        match = padrao_nome.match(arquivo_label.name)
        if not match:
            continue

        objetos = []

        with arquivo_label.open(encoding="utf-8") as f:
            for linha in f:
                partes = linha.strip().split()
                if len(partes) != 5:
                    continue

                class_id, x, y, w, h = partes

                objetos.append({
                    "class_id": int(class_id),
                    "x_center": float(x),
                    "y_center": float(y),
                    "width": float(w),
                    "height": float(h),
                })

        resultados.append({
            "ano": int(match.group("ano")),
            "arquivo": match.group("arquivo"),
            "page": int(match.group("page")),
            "labels_yolo": objetos,
        })

    return resultados



# =========================================================
# CONFIGURAÇÕES
# =========================================================

CLASSES = {
    0: "question_block",
    1: "statement_text",
    2: "statement_image",
    3: "alternative_text",
    4: "alternative_image",
}

QUESTAO_REGEX = re.compile(r"(?i)^quest[aã]o\s*(n[ºo]?)?\s*\d+")

client = OpenAI()

# =========================================================
# UTILIDADES
# =========================================================

def yolo_to_pdf_bbox(label, page_width, page_height):
    x_c, y_c, w, h = (
        label["x_center"],
        label["y_center"],
        label["width"],
        label["height"],
    )

    return fitz.Rect(
        (x_c - w / 2) * page_width,
        (y_c - h / 2) * page_height,
        (x_c + w / 2) * page_width,
        (y_c + h / 2) * page_height,
    )


def imagem_para_base64(caminho: Path) -> str:
    with open(caminho, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# =========================================================
# AGENTE MULTIMODAL
# =========================================================

def agente_formatador_markdown_multimodal(
    numero_questao: int,
    texto_bruto: str,
    imagens_paths: list[Path],
):
    content = [
        {
            "type": "input_text",
            "text": f"""
Você é um especialista em provas do ENEM.

Reconstrua a questão em Markdown estruturado.

REGRAS:
- Não invente texto
- Extraia:
  • Enunciado
  • Alternativas A–E
- Ignore créditos editoriais
- As imagens aparecem no local indicado no texto

FORMATO FINAL:

# Questão {numero_questao}

(enunciado)

(imagens se existirem)

---

A) ...
B) ...
C) ...
D) ...
E) ...

TEXTO BRUTO:
{texto_bruto}
"""
        }
    ]
    
    for img in imagens_paths:
        content.append({
            "type": "input_image",
            "image_url": f"data:image/png;base64,{imagem_para_base64(img)}"
        })

    print(texto_bruto)
    response = client.responses.create(
        model="gpt-5-nano",
        input=[{"role": "user", "content": content}],
        max_output_tokens=1200,
    )


    return response.output_text.strip()


# =========================================================
# PROCESSAMENTO DO PDF
# =========================================================

def processar_pdf(
    ano: int,
    arquivo: str,
    page: int,
    labels_yolo: list,
    output_base="output",
):
    pdf_path = Path(f"provas/{ano}/{arquivo}.pdf")
    output_base = Path(output_base)

    img_dir = output_base / "imagens"
    md_dir = output_base / "markdown"
    img_dir.mkdir(parents=True, exist_ok=True)
    md_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    pagina = doc[page - 1]

    page_width = pagina.rect.width
    page_height = pagina.rect.height

    blocos = []

    # 🔹 TEXTO
    for block in pagina.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue

        texto = " ".join(
            span["text"]
            for line in block["lines"]
            for span in line["spans"]
        ).strip()

        if texto:
            x0, y0, *_ = block["bbox"]
            blocos.append({
                "tipo": "texto",
                "conteudo": texto,
                "y": y0,
                "x": x0,
            })

    # 🔹 IMAGENS (YOLO)
    img_count = 0

    for label in labels_yolo:
        class_name = CLASSES.get(label["class_id"])
        if class_name not in {"statement_image", "alternative_image"}:
            continue

        bbox = yolo_to_pdf_bbox(label, page_width, page_height)
        pix = pagina.get_pixmap(clip=bbox, dpi=300)

        img_count += 1
        nome = f"{ano}_{arquivo}_p{page}_img_{img_count}.png"
        caminho = img_dir / nome
        pix.save(caminho)

        blocos.append({
            "tipo": "imagem",
            "conteudo": caminho,
            "y": bbox.y0,
            "x": bbox.x0,
        })

    # 🔥 ORDENAR POR LAYOUT REAL
    blocos.sort(key=lambda b: (b["y"], b["x"]))

    # =====================================================
    # AGRUPAR QUESTÕES
    # =====================================================

    questoes = []
    atual = None
    num = 0

    for bloco in blocos:
        if bloco["tipo"] == "texto" and QUESTAO_REGEX.match(bloco["conteudo"]):
            if atual:
                questoes.append(atual)
            num += 1
            atual = {"numero": num, "texto": "", "imagens": []}
            continue

        if not atual:
            continue

        if bloco["tipo"] == "texto":
            atual["texto"] += bloco["conteudo"] + "\n"

        else:
            atual["texto"] += "\n[IMAGEM]\n"
            atual["imagens"].append(bloco["conteudo"])

    if atual:
        questoes.append(atual)

    # =====================================================
    # LLM
    # =====================================================

    markdown_final = []

    for q in questoes:
        md = agente_formatador_markdown_multimodal(
            q["numero"],
            q["texto"],
            q["imagens"],
        )
        print(md)
        markdown_final.append(md)

    md_path = md_dir / f"{ano}_{arquivo}_page_{page}.md"
    md_path.write_text("\n\n".join(markdown_final), encoding="utf-8")

    return {
        "questoes": len(questoes),
        "markdown": md_path,
        "imagens": img_dir,
    }
