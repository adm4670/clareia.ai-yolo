from dotenv import load_dotenv
load_dotenv(".env")

from utils import ler_labels_yolo, processar_pdf

arquivos = ler_labels_yolo()

for item in arquivos[:1]:
    resultado = processar_pdf(
        ano=item["ano"],
        arquivo=item["arquivo"],
        page=item["page"],
        labels_yolo=item["labels_yolo"]
    )

    print("Markdown gerado")
