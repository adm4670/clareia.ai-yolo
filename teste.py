import fitz  # PyMuPDF
import os
import re

# =====================================
# CONFIGURAÇÃO
# =====================================
YOLO_IMAGE_CLASSES = {2, 4}  # statement_image, alternative_image

# =====================================
# FUNÇÕES AUXILIARES
# =====================================
def load_yolo_labels(label_path):
    boxes = []
    with open(label_path, "r", encoding="utf-8") as f:
        for line in f:
            cls, x, y, w, h = map(float, line.strip().split())
            boxes.append({"class": int(cls), "x": x, "y": y, "w": w, "h": h})
    return boxes

def yolo_to_rect(box, page_width, page_height):
    x = box["x"] * page_width
    y = box["y"] * page_height
    w = box["w"] * page_width
    h = box["h"] * page_height
    return fitz.Rect(x - w/2, y - h/2, x + w/2, y + h/2)

def renderizar_recorte_bbox(page, bbox_pdf, output_dir, nome_imagem, dpi=300):
    pix = page.get_pixmap(clip=bbox_pdf, dpi=dpi)
    caminho_imagem = os.path.join(output_dir, nome_imagem)
    pix.save(caminho_imagem)
    return caminho_imagem

# =====================================
# EXTRAÇÃO DE QUESTÕES - PÁGINA 2
# =====================================
def extrair_questoes_pagina_2(pdf_path, yolo_path, output_dir="output"):
    os.makedirs(output_dir, exist_ok=True)
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    page = doc[1]  # Página 2

    page_width, page_height = page.rect.width, page.rect.height
    yolo_boxes = load_yolo_labels(yolo_path)

    # Regex para Questão X e alternativas
    question_regex = re.compile(r"(?i)Questão\s+([1-9][0-9]{0,2}|1000)")
    alternativa_regex = re.compile(r"^\(?[A-Ea-e]\)")

    # Extrair blocos de texto da página
    blocks = page.get_text("blocks")
    text_blocks = [b for b in blocks if b[6] == 0]  # tipo 0 = texto

    # Ordena pelo eixo Y
    text_blocks.sort(key=lambda b: (b[1], b[0]))

    questoes = []
    questao_atual = None
    img_counter = 0

    for b in text_blocks:
        texto = b[4].strip().replace("\n", " ")
        if not texto:
            continue

        # Nova questão
        if question_regex.search(texto):
            if questao_atual:
                questoes.append(questao_atual)
            questao_atual = {
                "titulo": texto,
                "enunciado": "",
                "alternativas": [],
                "imagens": []
            }
            continue

        if not questao_atual:
            continue

        # Alternativa ou enunciado
        if alternativa_regex.match(texto):
            questao_atual["alternativas"].append(texto)
        else:
            questao_atual["enunciado"] += texto + " "

    # Última questão
    if questao_atual:
        questoes.append(questao_atual)

    # Renderizar imagens YOLO para todas as questões
    for box in yolo_boxes:
        if box["class"] not in YOLO_IMAGE_CLASSES:
            continue
        rect = yolo_to_rect(box, page_width, page_height)
        img_counter += 1
        nome_img = f"img_p2_{img_counter}.png"
        caminho_img = renderizar_recorte_bbox(page, rect, images_dir, nome_img)
        # Associar à questão mais próxima verticalmente
        min_dist = float("inf")
        quest_proxima = None
        centro_y = (rect.y0 + rect.y1)/2
        for q in questoes:
            # usar posição do enunciado como referência
            q_y = page.search_for(q["titulo"])[0].y0
            dist = abs(q_y - centro_y)
            if dist < min_dist:
                min_dist = dist
                quest_proxima = q
        if quest_proxima:
            quest_proxima["imagens"].append(caminho_img)

    return questoes

# =====================================
# GERAR MARKDOWN
# =====================================
def gerar_markdown(questoes):
    md = ""
    for q in questoes:
        md += "\n---\n\n"
        md += f"### {q['titulo']}\n\n"
        md += f"{q['enunciado'].strip()}\n\n"
        for i, img in enumerate(q["imagens"]):
            md += f"![Imagem {i+1}]({img})\n\n"
        for alt in q["alternativas"]:
            md += f"- {alt}\n"
    return md

# =====================================
# EXECUÇÃO
# =====================================
def main(pdf_path, yolo_path, output_md="pagina_2.md"):
    questoes = extrair_questoes_pagina_2(pdf_path, yolo_path)
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(gerar_markdown(questoes))
    print(f"✔ Questões da página 2 extraídas e salvas em {output_md}")

# =====================================
# USO
# =====================================
if __name__ == "__main__":
    pdf_path = "./provas/2013/Caderno1_Azul_Sab.pdf"
    yolo_path = "./dataset_full/labels/2013_Caderno1_Azul_Sab_page_002.txt"
    main(pdf_path, yolo_path)
