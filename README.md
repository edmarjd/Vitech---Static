# Projeto ANS — compressão de planos de bits com rANS e tANS

Compressão **sem perdas** de imagens em tons de cinza, feita plano de bit por plano de bit, usando
**ANS (Asymmetric Numeral Systems)**. O projeto tem duas partes que se complementam:

| Parte | Linguagem | Função |
|---|---|---|
| **rANS** (streaming, estado contínuo) | Python | Implementação de referência. Também é quem **gera as tabelas** do tANS. |
| **tANS** (baseado em tabelas) | C | Encoder e decoder rápidos, que apenas consultam tabelas pré-computadas. |

---

## Como funciona

1. **Planos de bits.** Cada pixel (8 bits) é separado em 8 planos binários, do bit 0 ao bit 7. Cada plano
   vira uma sequência de símbolos `0` e `1`, gravada em `plano_bit_N.txt`.
   Os planos altos (6 e 7) são suaves e previsíveis. Os baixos (0 a 3) são quase ruído.
2. **Contexto 1D (lookahead).** A probabilidade de um símbolo depende do **próximo** símbolo do plano.
   O decoder trabalha de trás para frente (o ANS é LIFO), então o próximo símbolo já foi decodificado
   e o contexto fica disponível sem ser transmitido.
3. **Blocos independentes.** O plano é dividido em blocos (`BLOCK_SIZE`). Cada bloco é codificado sozinho,
   com o estado do ANS reiniciado.
4. **Modelo semi-estático.** Antes de codificar um bloco, o encoder conta os 0s e 1s dele (por contexto) e
   escolhe a tabela mais próxima da proporção medida. A escolha vai no cabeçalho do bloco e o decoder só a lê.
   A probabilidade **nunca se adapta durante a codificação**; ela só muda de um bloco para o seguinte.
5. **Tabelas geradas pelo rANS.** O `tans_tables.h` não é escrito à mão. O `ANS-Streaming Encoder.py` aplica
   o encoder rANS (`_encode_symbol`) a cada estado `x` em `[L, 2L-1]` e a cada símbolo, e grava o resultado.
   O C só lê essas tabelas.
6. **Modo RAW.** Se o tANS não deixa o plano menor que o original, o plano é gravado sem compressão
   (apenas 10 bytes de cabeçalho a mais).

---

## Requisitos

- Python 3.9 ou superior, com `numpy`, `opencv-python` e `matplotlib`
- `gcc` (ou outro compilador C99) e a biblioteca matemática (`-lm`)

```bash
pip install numpy opencv-python matplotlib
```

---

## Como rodar

Execute tudo de **dentro da pasta do projeto**. Atenção ao `-O2`, que é a letra **O**, não o número zero.

### Comando completo (gera as tabelas, compila e testa uma imagem)

```bash
python3 "ANS-Streaming Encoder.py" --gerar-tabelas && gcc -O2 Encoder_Ans.c -o encoder -lm && gcc -O2 Decoder.c -o decoder && python3 Bit_Planes.py Kodak/kodim19.png
```

O nome do primeiro arquivo tem **espaço**, por isso as aspas. A primeira linha da saída deve ser
`tans_tables.h gerado: RANGE=10, cfgs (f0) = [9, 1]`.

### Passo a passo

```bash
# 1. Gerar as tabelas do tANS a partir do rANS
python3 "ANS-Streaming Encoder.py" --gerar-tabelas

# 2. Compilar
gcc -O2 Encoder_Ans.c -o encoder -lm
gcc -O2 Decoder.c -o decoder

# 3. Rodar numa imagem (outro caminho funciona do mesmo jeito)
python3 Bit_Planes.py Kodak/kodim19.png
python3 Bit_Planes.py DIV2K/0063.png

# Opcional: mostra o log completo do encoder e do decoder para cada plano
python3 Bit_Planes.py Kodak/kodim19.png --detalhe
```

O `Bit_Planes.py` separa a imagem em planos, comprime e decodifica cada um, confere se o resultado é
idêntico ao original e imprime uma tabela com uma coluna por plano e uma coluna `TOTAL`.
Ele também cria `plano_bit_N.txt`, `plano_bit_N_encoded.bin`, `saida_N.txt` e `resultado_planos_bits.png`.

### Rodar o encoder e o decoder em C diretamente

```bash
./encoder plano_bit_7.txt                              # gera plano_bit_7_encoded.bin
./decoder plano_bit_7_encoded.bin saida_7.txt          # reconstrói a sequência
```

### Versão Python (rANS de referência)

```bash
# Codificar e decodificar um arquivo de símbolos
python3 "ANS-Streaming Encoder.py" --input input.txt --output comprimido.bin --recalc-window 1000
python3 ANS-Streaming-Decoder.py --encoded comprimido.bin --output saida.txt --verify input.txt

# Rodar todos os arquivos de inputs/ e de Plano_de_Bits/ e imprimir uma tabela comparativa
python3 run_all.py --recalc-window 1000
```

---

## Estrutura de arquivos

```text
Projeto-ANS-main/
├── ANS-Streaming Encoder.py   Encoder rANS (Python) e gerador do tans_tables.h
├── ANS-Streaming-Decoder.py   Decoder rANS (Python)
├── context_model.py           Modelo de contexto: frequências por bloco e cabeçalhos
├── run_all.py                 Roda o pipeline rANS em inputs/ e Plano_de_Bits/
├── Bit_Planes.py              Separa a imagem em planos, roda o tANS em C e imprime o relatório
├── Encoder_Ans.c              Encoder tANS (C)
├── Decoder.c                  Decoder tANS (C)
├── tans_tables.h              Tabelas do tANS (GERADO: não editar à mão)
├── Kodak/                     Imagens de teste (kodim01 a kodim24)
├── DIV2K/                     Imagens de teste maiores
├── inputs/                    Sequências de 0s e 1s (input_1.txt a input_8.txt)
└── Plano_de_Bits/             Planos de bits já extraídos (plano_bit_0.txt a plano_bit_7.txt)
```

---

## Formato do arquivo comprimido (C)

Cabeçalho global, **10 bytes**:

| Campo | Tamanho |
|---|---|
| Número de símbolos | 4 bytes |
| `RANGE` (L) | 1 byte |
| Modo (`1` = tANS, `0` = RAW) | 1 byte |
| Número de blocos | 4 bytes |

No **modo tANS**, cada bloco vem em seguida:

| Campo | Tamanho |
|---|---|
| `cfg0`: tabela do contexto "próximo símbolo = 0" | 1 byte |
| `cfg1`: tabela do contexto "próximo símbolo = 1" | 1 byte |
| Tamanho do bloco em bytes | 4 bytes |
| Bits do bloco: símbolos, estado final (`FLUSH_BITS` bits) e *stop bit* | variável |

No **modo RAW**, o cabeçalho é seguido de 1 bit por símbolo.

---

## Métricas do relatório

| Linha | Significado |
|---|---|
| TAMANHO ORIGINAL | Símbolos do plano (1 bit cada) |
| TABELA (RANGE) | `L=10` quando usa tANS, `RAW` quando não comprime |
| TAMANHO TOTAL DE BLOCOS | Número de blocos tANS (0 em RAW) |
| OVERHEAD | Cabeçalhos: (10 + 6 × blocos) × 8 bits |
| BITS DE PREENCHIMENTO | Bits que completam o último byte de cada bloco |
| ESTADO | Estado final de cada bloco: (`FLUSH_BITS` + 1) bits, incluindo o *stop bit* |
| BITSTREAM | Bits produzidos pela codificação dos símbolos |
| COMPRIMIDO GLOBAL | Overhead + preenchimento + estado + bitstream |
| GANHO TOTAL | Original − comprimido (negativo se o arquivo cresceu) |
| TAXA DE COMPRESSAO | (1 − comprimido / original) × 100 |
| TEMPO ENCODER / DECODER | Tempo de relógio de uma execução, incluindo leitura e escrita de arquivo |
| VERIFICACAO LOSSLESS | `OK` quando o plano decodificado é idêntico ao original |

---

## Parâmetros que podem ser alterados

| O quê | Onde | Observação |
|---|---|---|
| Tamanho do bloco | `BLOCK_SIZE` em `Encoder_Ans.c` e `Decoder.c` | **Precisa ser o mesmo valor nos dois arquivos**. Padrão: 10000 |
| Limite de símbolos por plano | `MAX_SYMBOLS` (encoder) e `MAX_DECODED_SYMBOLS` (decoder) | Padrão: 12 milhões, o suficiente para as imagens do DIV2K |
| Tamanho das tabelas (L) | `--range` ao gerar as tabelas | Padrão: 10. O estado precisa caber em 8 bits, então L ≤ 128 |
| Probabilidades das tabelas | `--freqs` ao gerar as tabelas | Padrão: `9,1` (P(0) = 90% e 10%) |

Depois de mudar qualquer valor, gere as tabelas e recompile os dois programas em C.

Exemplo com outras probabilidades (testado, P(0) = 80% e 20%): `python3 "ANS-Streaming Encoder.py" --gerar-tabelas --range 10 --freqs 8,2`.

> **Limite atual:** o `Encoder_Ans.c` e o `Decoder.c` só têm código para RANGE 4, 6, 8, 9 e 10, e o
> `select_cfg` do RANGE 10 usa exatamente duas tabelas (`--freqs` com dois valores). Outro `--range`, ou outra
> quantidade de tabelas, exige adaptar o encoder e o decoder.

---

## Problemas comuns

| Mensagem ou sintoma | Causa e solução |
|---|---|
| `Ficheiro ou pasta inexistente` / `No such file` | O terminal está na pasta errada. Use `cd` para a pasta do projeto. |
| `unrecognized command-line option '-02'` | Foi digitado zero em vez da letra O. Use `-O2`. |
| `can't open file ... ANS-Streaming_Encoder.py` | O nome real tem espaço: `"ANS-Streaming Encoder.py"`, entre aspas. |
| `ERRO: muitos simbolos` | O plano passa de `MAX_SYMBOLS`. Aumente o valor no encoder e no decoder. |
| `ERRO` na linha VERIFICACAO LOSSLESS | `BLOCK_SIZE` diferente entre encoder e decoder, ou `tans_tables.h` de outra versão. Gere as tabelas de novo e recompile os dois. |
| `RANGE` diferente entre arquivo e decoder | O `.bin` foi gerado com outras tabelas. Recompile o decoder ou gere o `.bin` de novo. |

---

## Observações

- O projeto é **estático por blocos**: as probabilidades são medidas antes, por bloco, e vão no cabeçalho.
  Não há modelo adaptativo, que atualizaria a probabilidade a cada símbolo ou lote.
- A versão em C reinicia o estado a cada bloco. A versão Python (`run_all.py`) mantém um estado contínuo,
  o que reduz o custo por bloco, mas usa 5 bits de precisão por contexto em vez de tabelas tANS.
- Os tempos do relatório vêm de uma única execução e incluem a leitura e a escrita de arquivos. Servem de
  referência, não de medida precisa do desempenho do tANS.