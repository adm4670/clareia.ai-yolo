# Pipeline de Criação de Dataset YOLO para Questões do ENEM

Esta documentação descreve o **processo completo, reproduzível e escalável** para criar um dataset de visão computacional (YOLO) voltado à identificação estrutural de questões do ENEM.

O objetivo do dataset é permitir a detecção automática de:

* Blocos de questões
* Enunciados (texto e imagem)
* Alternativas (texto e imagem)

Esse dataset serve como base para pipelines que combinam **YOLO + OCR + LLM**, com saída final em **Markdown estruturado**.

---

## 1. Visão Geral do Pipeline

```text
PDFs do ENEM
  ↓
Normalização dos PDFs
  ↓
Renderização página → imagem
  ↓
Pré-processamento visual leve
  ↓
Amostragem inteligente
  ↓
Anotação humana
  ↓
Validação automática
  ↓
Export YOLOv8
  ↓
Versionamento do dataset
```

---

## 2. Organização de Diretórios

Estrutura recomendada do repositório:

```text
project_root/
 ├── raw_pdfs/
 │    ├── enem_2012/
 │    ├── enem_2015_ppl/
 │    ├── enem_2019/
 │    └── enem_2022/
 │
 ├── normalized_pdfs/
 ├── pages/
 ├── annotations/
 ├── dataset/
 │    ├── images/
 │    │    ├── train/
 │    │    ├── val/
 │    │    └── test/
 │    ├── labels/
 │    │    ├── train/
 │    │    ├── val/
 │    │    └── test/
 │    └── data.yaml
 │
 └── scripts/
```

**Regra de ouro:** nunca sobrescrever dados brutos ou versões anteriores do dataset.

---

## 3. Coleta dos PDFs

### Fontes

* Provas oficiais do ENEM (INEP)
* Tipos recomendados:

  * Aplicação regular
  * PPL
  * Reaplicação

### Cobertura temporal

* Ideal: anos entre **2010 e 2023**
* Quanto maior a variação visual, melhor a generalização do modelo

---

## 4. Normalização dos PDFs

Antes da conversão para imagem, todos os PDFs devem ser normalizados.

### Ações obrigatórias

* Corrigir rotação de páginas
* Padronizar DPI (recomendado: **300 DPI**)
* Converter para espaço de cor RGB

### Ferramentas sugeridas

* Ghostscript
* ImageMagick
* PyMuPDF

Saída:

```text
normalized_pdfs/
```

---

## 5. Renderização Página → Imagem

Cada página do PDF deve ser renderizada como uma imagem independente.

### Parâmetros

* Formato: PNG
* DPI: 300
* Uma página = uma imagem

### Convenção de nomes

```text
enem_2022_pagina_034.png
```

Saída:

```text
pages/
```

---

## 6. Pré-processamento Visual

O pré-processamento deve ser **mínimo**, mantendo a aparência real das provas.

### Permitido

* Ajuste leve de contraste
* Remoção de fundo amarelado
* Sharpen suave

### Proibido

* Binarização agressiva
* Recorte de margens
* Remoção pesada de ruído

Objetivo: melhorar legibilidade sem distorcer o layout original.

---

## 7. Amostragem Inteligente

Não é necessário anotar todas as páginas.

### Critérios de seleção

* Questões com imagens no enunciado
* Questões com alternativas que possuem imagens
* Gráficos grandes, tabelas ou esquemas

### Proporção recomendada

| Tipo de questão        | Percentual |
| ---------------------- | ---------- |
| Apenas texto           | 40%        |
| Enunciado com imagem   | 40%        |
| Alternativa com imagem | 20%        |

---

## 8. Schema de Labels YOLO

### Labels finais

```text
question_block
statement_text
statement_image
alternative_text
alternative_image
```

### Definições

* **question_block**: área total de uma questão (do número até a alternativa E)
* **statement_text**: texto do enunciado
* **statement_image**: imagens associadas ao enunciado
* **alternative_text**: texto completo de cada alternativa (A–E)
* **alternative_image**: imagens associadas diretamente a uma alternativa

---

## 9. Anotação Humana

### Ferramentas recomendadas

* Label Studio (preferencial)
* CVAT
* Roboflow

### Regras de anotação

* Nunca misturar texto e imagem no mesmo bounding box
* Uma alternativa inteira = um único bounding box
* Imagens pequenas também devem ser anotadas
* Usar padding leve ao redor das caixas

**Consistência é mais importante que precisão pixel-perfect.**

---

## 10. Validação Automática

Antes do export, executar validações automáticas.

### Regras sugeridas

* Todo `question_block` deve conter ao menos uma `alternative_text`
* Máximo de 5 `alternative_text` por questão
* Toda `alternative_image` deve estar abaixo de uma `alternative_text`
* Nenhuma label fora de um `question_block`

Essas validações eliminam a maioria dos erros humanos.

---

## 11. Export para YOLOv8

### Estrutura final

```text
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
```

### Exemplo de `data.yaml`

```yaml
path: dataset
train: images/train
val: images/val

names:
  0: question_block
  1: statement_text
  2: statement_image
  3: alternative_text
  4: alternative_image
```

Split recomendado:

* 70% treino
* 20% validação
* 10% teste (anos nunca vistos)

---

## 12. Versionamento do Dataset

Nunca sobrescrever versões antigas.

### Estratégia

* Git para scripts e metadados
* DVC ou Git-LFS para imagens

### Exemplo

```text
dataset_v1.0
dataset_v1.1  # correções de anotação
dataset_v2.0  # inclusão de novos anos
```

---

## 13. Métricas Prioritárias

Além do mAP geral, acompanhar:

* Recall de `alternative_image`
* Precision de `statement_image`
* Falsos positivos de `question_block`

Essas métricas impactam diretamente a qualidade do Markdown final.

---

## 14. Observação Final

Este pipeline foi desenhado para **uso em produção**, com foco em qualidade estrutural e escalabilidade, sendo especialmente adequado para plataformas educacionais baseadas em ENEM, como pipelines de extração, organização e geração de conteúdo pedagógico estruturado.




# 🎯 PRIORIDADE ÚNICA DO DIA  
**Data:** 17/02/2026

## ❓ Pergunta-âncora
### **Qual é a ÚNICA coisa que faz a clareia.ai avançar hoje?**

---

## ✅ PRIORIDADE DEFINIDA

> **Implementar o pipeline de extração e formatação de PDF → Markdown utilizando rotulagens já existentes do YOLO (sem treinamento), validando se a estrutura final reproduz o layout original com precisão próxima de 100%.**

---

## 🧠 CONTEXTO (POR QUE ISSO IMPORTA)

- Elimina um risco técnico central do produto  
- Valida a hipótese de preservação de **layout + semântica**  
- Destrava a automação real da base de questões  
- Evita distrações com treino prematuro de modelo  

---

## ⚙️ ESCOPO EXATO DA AÇÃO

### ✅ Fazer
- Utilizar **rotulagens já realizadas no YOLO**
- Não realizar treinamento de modelo
- Implementar o pipeline de:
  1. Leitura do PDF  
  2. Associação bloco → rótulo  
  3. Ordenação espacial (layout-aware)  
  4. Geração de Markdown estruturado  

### ❌ Não fazer
- Treinar YOLO  
- Ajustar dataset  
- Melhorar acurácia do detector  
- Refinar estética além do essencial  

---

## 📦 OUTPUT ESPERADO (CRITÉRIO BINÁRIO)

- [ ] Markdown gerado automaticamente  
- [ ] Estrutura fiel ao PDF original  
- [ ] Ordem correta dos elementos  
- [ ] Referências corretas de imagens  
- [ ] Precisão visual/estrutural ≈ **100%**

> Se o Markdown representa o PDF de forma confiável → **o dia venceu**.

---

## 🚨 REGRA DE DECISÃO

- Se funcionar **sem treinamento**, o caminho está validado  
- Se não funcionar, o problema é **arquitetura**, não modelo  

---

# 🎯 PRIORIDADE ÚNICA DO DIA  
**Data:** 19/02/2026

## ❓ Pergunta-âncora
### **Qual é a ÚNICA coisa que faz a clareia.ai avançar hoje?**

---

## ✅ PRIORIDADE DEFINIDA

> **Testar o pipeline de PDF → Markdown usando apenas rotulagens YOLO existentes, garantindo que o layout e a ordem dos elementos sejam preservados.**

---

## ⚙️ ESCOPO SIMPLIFICADO

### ✅ Fazer
- Usar **rotulagens YOLO já existentes**  
- Implementar pipeline básico:
  1. Ler PDF  
  2. Mapear blocos com rótulos  
  3. Ordenar elementos pelo layout  
  4. Gerar Markdown fiel ao PDF  

### ❌ Não fazer
- Treinar YOLO  
- Ajustar dataset  
- Melhorar detector ou estética  
- Qualquer refinamento não essencial  

---

## 📦 OUTPUT ESPERADO

- [ ] Markdown gerado automaticamente  
- [ ] Estrutura fiel ao PDF  
- [ ] Ordem correta dos elementos  
- [ ] Referências de imagens corretas  
- [ ] Precisão visual ≈ **100%**

> Markdown confiável = dia **vencido** ✅

---

## 🚨 DECISÃO RÁPIDA

- Pipeline funciona sem treinamento → validação concluída  
- Pipeline falha → foco em **arquitetura**, não modelo  

> **Feito gera clareza. Clareza gera dinheiro.**





uvicorn backend:app --reload
