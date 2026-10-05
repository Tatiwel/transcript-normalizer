# transcript-normalizer: guia

Este guia serve a três leitores ao mesmo tempo: quem só quer transcrições mais limpas; quem estuda outra área e quer ensinar o próprio vocabulário à ferramenta (o exemplo que acompanha o texto é biomedicina); e quem desenvolve. Cada seção é curta. Números como (D-020) remetem a [DECISIONS.md](DECISIONS.md), onde estão os motivos e as medições. A versão em inglês está em [GUIDE.md](GUIDE.md).

## 1. O que faz, e o que não faz

Legenda automática e reconhecimento de fala erram justamente o vocabulário de cada área. Num vídeo de finanças, CEMIG vira `SEMIG` e EBITDA vira `evitida`; numa aula de farmacologia, metformina vira `metiformina`. A ferramenta conhece os termos que você entrega a ela, num **pacote** (o arquivo de termos), e aponta os lugares em que a transcrição errou um deles. Trecho que não se parece com nada do pacote nunca é tocado: um pacote de finanças não estraga uma aula de biologia (D-001).

Ela nunca muda o que o falante disse; corrige o que o reconhecedor ouviu. Daí a diferença entre **correção** (a legenda estropiou o termo: `SEMIG` vira `CEMIG`) e **alias** (o falante disse mesmo de outro jeito, como o ticker `CMIG4` ou um plural: o termo é reconhecido e o texto fica como foi dito, D-020). A legenda original e seus timestamps nunca são alterados; cada mudança é um registro à parte que aponta para o texto (D-004). Não é corretor ortográfico, não resume nada e não pede a uma IA que reescreva o texto.

## 2. Instalação

```
pip install "transcript-normalizer[ingest] @ git+https://github.com/Tatiwel/transcript-normalizer@v0.3.0"
```

`v0.3.0` é a tag mais recente. O menu interativo e a comparação fonética descritos aqui vieram depois dela; até a próxima tag, instale de `@main`.

- **O extra `[ingest]`** traz o que o `fetch` usa para obter a transcrição: yt-dlp (legendas das plataformas), faster-whisper (reconhecimento de fala no seu próprio computador) e rich (barras de progresso). Sem ele, você ainda normaliza uma legenda que já tem.
- **ffmpeg** só é necessário quando há transcrição de áudio (arquivo local, ou `--whisper`). Legenda baixada da plataforma dispensa.
- **Um runtime de JavaScript** (o Deno, por exemplo) é exigido pelas versões recentes do yt-dlp para ler o YouTube. Se o download do YouTube falhar com uma mensagem sobre JavaScript, instale um.

## 3. Primeiro uso, de dois jeitos

**O menu.** Digite `transcript-normalizer`, sem mais nada, num terminal:

```
╭────────────────────────── transcript-normalizer ───────────────────────────╮
│ 1. Fetch a video or file   download a caption, or transcribe audio locally │
│ 2. Normalize a run         fix domain terms in a fetched caption           │
│ 3. Review pending          answer what the tool was unsure about           │
│ 4. Show a run's outputs    where the files are, first lines of the result  │
│ 5. List runs               everything under runs/                          │
│ 6. Help                    what each action does and its command           │
│ q. Quit                                                                    │
╰────────────────────────────────────────────────────────────────────────────╯
```

Baixe um vídeo (1), normalize (2) e responda o que ficou em dúvida (3). Cada item do menu executa um dos comandos abaixo; o que você aprende no menu vale num script (D-051). O menu e a ajuda estão em inglês. `?2` mostra o que o item 2 faz e o comando equivalente:

```
  2. Normalize a run  pick a run by number; shows the report, then offers the
                      review if anything is pending
                      `transcript-normalizer runs/<id>/legenda.txt`
```

`transcript-normalizer help` (ou `--help`, ou o item 6 do menu) imprime a referência inteira, em seções: USAGE, COMMANDS, MENU, WHAT HAPPENS, THE REVIEW LOOP, EXAMPLES, LEARN MORE. Uma delas:

```
THE REVIEW LOOP
  y  the recognizer garbled the term: correct it from now on
  n  not this term: never propose it again
  l  this term, said that way: recognize it, never change it
  s  not sure: asked again next time; two seconds of doubt is a skip
  a  yes to this form and the remaining forms of the same term
  r  no to this form and the remaining forms of the same term
```

**Os três comandos.**

```
transcript-normalizer fetch https://youtu.be/4wCtn8BWR4o
transcript-normalizer runs/4wCtn8BWR4o/legenda.txt
transcript-normalizer runs/4wCtn8BWR4o/legenda.txt --confirm
```

O `fetch` pega a legenda da plataforma (a faixa no idioma original, nunca uma tradução automática, D-045) e, se não houver, transcreve o áudio localmente (D-036). Também aceita um arquivo de áudio ou vídeo: `transcript-normalizer fetch aula.mp4`. O segundo comando normaliza; o terceiro faz o mesmo e depois pergunta o que ficou em dúvida. `transcript-normalizer list` mostra o que você já tem. Parte do que o segundo imprime para o vídeo acima:

```
runs/4wCtn8BWR4o/legenda.txt: 239 caption lines, pack 0.3.3
terms:
  Semig, semiga, SEMIG, Semiga (21 occurrences) -> CEMIG
  evitida (1 occurrence) -> EBITDA
  dívida alíquida (1 occurrence) -> dívida líquida

recognized (not changed):
  CEMIG (14 occurrences) -> CEMIG
  bilhões, Bilhões (8 occurrences) -> bilhão

to confirm:
  Adaptavalda, a DAPTA Valdre, AdaptaValor, adaptavala (4 occurrences) -> Adapta Valuer
  dividido (2 occurrences) -> dividendo
```

## 4. Lendo as saídas

Tudo vai para `runs/<id-do-vídeo>/`, no diretório em que você está; nada é escrito ao lado do arquivo de entrada (D-015, D-022).

| arquivo | o que é |
|---|---|
| `legenda.txt` | a transcrição como chegou, com um cabeçalho dizendo de onde veio |
| `meta.yaml` | título, canal, data e qual etapa do `fetch` produziu o texto |
| `normalized.txt` | a transcrição com as correções aplicadas, mesmas linhas, mesmos timestamps |
| `annotations.json` | cada correção e cada reconhecimento, como dados |
| `report.txt` | o que o comando imprimiu |
| `needs-review/pending.txt` | o que ainda espera a sua resposta |
| `needs-review/corrections.csv` | com `--corrections`: as mudanças numa tabela para conferir à mão |

`needs-review/` guarda o que precisa de uma pessoa. Vazio ou ausente, não há nada esperando por você.

O `normalized.txt` se lê como o original. A linha 9:36 do vídeo acima, antes e depois:

```
9:36 lógico indicador de alavancagem, dívida alíquida sobre evitida, cresceu uma vez,
9:36  lógico indicador de alavancagem, dívida líquida sobre EBITDA, cresceu uma vez,
```

O `annotations.json` tem um registro por mudança, apontando posições de caractere no original:

```json
{"start": 9141, "end": 9156, "original": "dívida alíquida", "replacement": "dívida líquida",
 "term": "dívida líquida", "rule": "term:variant", "kind": "correction", "band": "high",
 "score": 100, "applied": true, "pack_version": "0.3.3"}
```

`kind` é `correction` ou `alias`. `band` é o grau de certeza: **high** (uma forma já listada: aplicada), **medium** (um palpite próximo: aplicado e listado em `pending.txt` para você confirmar), **low** (uma semelhança fraca: só registrada, nunca aplicada) (D-011).

## 5. A rodada de confirmação

`--confirm` (ou o item 3 do menu) pergunta sobre cada palpite da faixa média, uma forma por vez, com as linhas em que ela aparece:

```
Oswaldo Cruz  (1 occurrence)
  Osvaldo Cruz  (1 occurrence)
    0:20  a metformina ainda é a primeira escolha, segundo o Osvaldo Cruz
    Osvaldo Cruz -> Oswaldo Cruz? [y]es / [n]o / [s]kip / a[l]ias / [a]ll-yes / [r]est-no:
```

| resposta | quando usar |
|---|---|
| `y` | o reconhecedor errou o termo; corrigir daqui para a frente |
| `n` | não é esse termo; nunca mais propor |
| `l` | é esse termo, e o falante disse assim mesmo; reconhecer, nunca mudar |
| `s` | você não tem certeza |
| `a` | sim para esta forma e para todas as que faltam do mesmo termo |
| `r` | não para esta forma e para todas as que faltam do mesmo termo |

**Se precisar pensar mais de dois segundos, pule.** Pergunta pulada volta na próxima vez; resposta errada fica gravada. Cada resposta é salva na hora, então um Ctrl+C não perde nada (D-037). Elas vão para `packs/<nome-do-pacote>.learned.yaml`, a sua camada pessoal, nunca para o pacote (D-013).

## 6. A sua área

Um pacote é um arquivo YAML. Eis um primeiro pacote de biomedicina, com seis termos, um de cada tipo que você deve precisar:

```yaml
# Biomedicina, pt-BR. 0.1.0: first terms, from one lecture.
language: pt-BR
version: 0.1.0
terms:
  - term: metformina          # um fármaco
    class: conceito
    aliases: [Glifage]
    variants: [metiformina, met forming]
  - term: PCR                 # uma sigla
    class: sigla
    aliases: [RT-PCR, reação em cadeia da polimerase]
    variants: [pê cê erre]
  - term: miligrama           # uma unidade
    class: unidade
    aliases: [mg, miligramas]
  - term: Oswaldo Cruz        # uma pessoa
    class: pessoa
    variants: [Oswald Cruise]
  - term: Western blot        # um método
    class: conceito
    variants: [western blood, uéstern blot]
  - term: Anvisa              # uma organização
    class: organizacao
    variants: [Anuvisa, Am visa]
```

- `term` é como o termo deve ser escrito. `aliases` são outros nomes corretos (uma marca, um plural, a sigla por extenso). `variants` é o que o reconhecedor produziu no lugar.
- `class` tem de ser uma de oito: `companhia`, `indicador`, `conceito`, `unidade`, `pessoa`, `organizacao`, `ferramenta`, `sigla` (D-021). Elas nasceram para finanças; fármaco e método entram como `conceito`. Nomes (`companhia`, `pessoa`) também passam pela comparação fonética, que pega erros nunca vistos antes (D-050).
- Deixe de fora variantes de uma ou duas letras e variantes que são palavras comuns, mesmo que a legenda as tenha usado (D-005, D-032).

Ponha o arquivo em `packs/`, no diretório em que você trabalha, e aponte para ele:

```
transcript-normalizer aula.txt --pack packs/biomed-ptbr.yaml
```

```
  Anuvisa (1 occurrence) -> Anvisa
  Oswald Cruise (1 occurrence) -> Oswaldo Cruz
  pê cê erre (1 occurrence) -> PCR
  western blood (1 occurrence) -> Western blot
  metiformina (1 occurrence) -> metformina
```

As suas respostas na rodada de confirmação vão crescendo `packs/biomed-ptbr.learned.yaml`. Quando uma entrada aprendida se provar, passe-a à mão para o pacote e suba a versão; a seção 2 de [CONTRIBUTING.md](../CONTRIBUTING.md) tem as regras de curadoria e mostra como medir um pacote.

## 7. Outro idioma

O pacote declara o idioma (`language: pt-BR`), e um módulo de idioma fornece o que o núcleo não deve adivinhar: como dobrar o texto (caixa, acentos), como é um plural, os padrões de unidade, onde termina uma frase e o esqueleto fonético. Por enquanto só existe português do Brasil. Acrescentar um idioma é um arquivo Python; a seção 1 de [CONTRIBUTING.md](../CONTRIBUTING.md) mostra o caminho.

## 8. Quão bom é

Quatro vídeos têm um gabarito conferido à mão (o arquivo **gold**) e são medidos de novo a cada mudança (`uv run python scripts/measure.py`). Com o pacote que vem junto (0.3.3):

| vídeo | linhas a acertar | acertos | faltas | mudanças erradas |
|---|---|---|---|---|
| R2Qgz8tFWVI | 167 | 145 | 22 | 16 |
| wxgFO_fyfXg | 222 | 211 | 11 | 10 |
| 4wCtn8BWR4o | 45 | 44 | 1 | 2 |
| 4tTmY8Buask | 119 | 108 | 11 | 4 |

- **R2Qgz8tFWVI**: um canal de finanças falando de uma elétrica (CEMIG), legenda da plataforma; o primeiro gabarito, de onde vem a maior parte das variantes.
- **wxgFO_fyfXg**: o mesmo canal comparando duas elétricas; muitos aliases (tickers, plurais) que não podem ser alterados.
- **4wCtn8BWR4o**: outro falante sobre a mesma empresa, transcrito localmente com faster-whisper em vez da legenda da plataforma.
- **4tTmY8Buask**: esse segundo falante num setor novo (um banco de investimento), com um nome de empresa que o pacote não conhecia.

Os limites, sem rodeio:

- **Palavras comuns ficam de fora**, mesmo quando o reconhecedor usou uma no lugar do termo (`tira` por TIR, `divide` por dividendo). Separar os casos exige ler as palavras ao redor, coisa que a ferramenta ainda não faz.
- **O mesmo erro pode significar dois termos.** `dividendio` é dividend yield para um falante e dividendo para o outro; o pacote só consegue guardá-lo para um dos dois (D-046).
- **Forma curta só casa exata.** `RO` por ROE, `sel` por Selic: forma com menos de seis letras nunca é adivinhada pela grafia, e a checagem fonética de nomes pede cinco consoantes.
- **Área nova começa do zero.** O quarto vídeo achou 4 de 81 correções antes de o nome da empresa entrar no pacote.

## 9. Glossário

- **pacote** (pack): a lista YAML de termos que a ferramenta pode tocar, para uma área e um idioma.
- **variante** (variant): uma forma que o reconhecedor produziu no lugar do termo; é corrigida.
- **alias**: outro nome correto do termo (ticker, marca, plural); reconhecido, nunca alterado.
- **faixa** (band): o grau de certeza de um casamento: alta (aplicada), média (aplicada e perguntada), baixa (só registrada).
- **run**: o diretório `runs/<id-do-vídeo>/`, com a transcrição de um vídeo e tudo o que saiu dela.
- **fixture**: um vídeo guardado no repositório com a transcrição, um pacote congelado e um gabarito, para medir.
- **gold** (gabarito): a resposta conferida à mão de uma fixture: cada lugar que deve mudar e cada lugar que não pode.
- **camada aprendida** (learned layer): as suas respostas da rodada de confirmação, em `packs/<pacote>.learned.yaml`; pessoal, nunca distribuída.
- **stand-off**: guardar as mudanças como registros à parte que apontam para o texto original, em vez de editá-lo.
