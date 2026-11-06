# Projeto ANS (Asymmetric Numeral Systems) - Streaming Contextual e C Estático

Este projeto foca na implementação e experimentação com técnicas de compressão baseadas em **Asymmetric Numeral Systems (ANS)**, abrangendo tanto implementações em C baseadas em tabelas (tANS estático) quanto pipelines modernos em Python baseados em streaming rANS com estado contínuo e modelo de contexto 1D (lookahead).

O ANS é uma técnica moderna de codificação entrópica que substitui o clássico Huffman em algoritmos de alta performance como Zstandard, JPEG XL e compressores de jogos, por possuir a velocidade de Huffman aliada à eficiência teórica da Codificação Aritmética.

---

## Pré-requisitos e Configuração

Para executar os scripts em Python, você precisará ter o Python 3 instalado com as seguintes bibliotecas:

- `numpy`
- `opencv-python` (cv2)
- `matplotlib` (apenas para exibição dos bitplanes)

Se você estiver usando o ambiente virtual já criado (`venv`), pode executar os scripts com:

```bash
venv/bin/python <nome_do_script.py>
```

Ou ativar o ambiente e instalar dependências, se necessário:

```bash
source venv/bin/activate
pip install numpy opencv-python matplotlib
```

Para a versão C, você precisará do `gcc` ou qualquer compilador C padrão.

---

## Como Rodar o Projeto

O projeto é dividido em diferentes frentes de compressão. Abaixo mostramos como rodar cada parte:

### 1. Extração e Análise de Planos de Bits (Bit Plane Slicing)

A estratégia inicial do projeto para comprimir imagens passava por quebrar as imagens em seus 8 planos de bits para estudá-los de modo avulso.

**Gerar planos de bits de uma imagem:**
Edite o arquivo `Bit_Planes.py` para apontar para a imagem desejada na linha 45 e então rode:

```bash
python3 Bit_Planes.py
```

Esse script vai processar a imagem, salvar um gráfico combinando os bits (`resultado_planos_bits.png`) e gerar 8 arquivos `.txt` (como `plano_bit_7.txt`) contendo a matriz de cada plano.

### 2. Codificando Arquivos Manuais (Python CLI)

Se você quer executar o streaming contextual em um arquivo `txt` individual.

> **Atenção:** execute os comandos de dentro da pasta do projeto:
>
> ```bash
> cd ~/Documentos/Vitech/Projeto-ANS-main
> ```

**Codificar (Contexto 1D Padrão):**

```bash
python3 "ANS-Streaming Encoder.py" --input input.txt --output comprimido.bin --mode static --recalc-window 1000
```

**Decodificar (Contexto 1D):**

```bash
python3 ANS-Streaming-Decoder.py --encoded comprimido.bin --output saida.txt --verify input.txt
```

### 3. tANS Estático (Implementação C)

A implementação em C funciona como um _Table-based ANS (tANS)_ clássico para alfabetos binários fixos (`RANGE = 8`, `CONFIG = 6`), escrevendo e lendo bitstreams byte a byte usando operações reversas.

**Para compilar e rodar:**

```bash
# Compilar Encoder
gcc Encoder_Ans.c -o encoder
# Compilar Decoder
gcc Decoder.c -o decoder

# A implementação C lê o arquivo "input.txt". Antes de testar copie seu input de teste:
cp inputs/input_1.txt input.txt

# Executar
./encoder
./decoder
```

Esses executáveis gerarão `input_encoded.bin` e a respectiva saída, mantendo log no console.

---

## Estrutura de Arquivos

```text
Projeto-ANS-main/
│
├── ANS-Streaming Encoder.py  # Codificador principal Python (rANS + Estado Contínuo + Contexto 1D)
├── ANS-Streaming-Decoder.py  # Decodificador Python (reverso simétrico exato)
├── context_model.py          # Implementação de modelagem de contexto e estado de lookahead
├── Bit_Planes.py             # Script de análise e recorte de planos de bit de imagens
├── Encoder_Ans.c             # tANS table-based Encoder estático legado (C)
├── Decoder.c                 # tANS table-based Decoder estático legado (C)
├── inputs/                   # Textos baseados em bits de 1 a 8 para benchmarking rápido
└── foto.jpg                  # Imagem base de teste padrão
```

## Entendendo a Inovação da Versão Python (v2 Contextual)

Diferente da versão primária em C ou das primitivas anteriores, os scripts Python (`ANS-Streaming Encoder.py` e `Decoder.py`) aplicam o estado da arte com:

- **Estado Contínuo**: Em vez de fazer reflush de estado por blocos curtos e gastar performance gravando padding, o ANS carrega um macro-estado continuamente e despacha bits excedentes instantaneamente, gerando Overhead próximo de zero;
- **Contexto _Lookahead_**: Foi introduzida predição contextual via cadeias de Markov onde a probabilidade de um bit é modulada com base no próximo símbolo (lookahead-1). No decoder (por ser operado em passo reverso - LIFO), o próximo símbolo já está perfeitamente acessível, tornando-o ultraeficiente e eliminando cabeçalhos de predição embutidos.

cd ~/Documentos/Vitech/Projeto-ANS-main
python3 run_all.py
