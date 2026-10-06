# transcript-normalizer: guia

Este guia serve a três leitores ao mesmo tempo: quem só quer transcrições mais limpas; quem estuda outra área e quer ensinar o próprio vocabulário à ferramenta (o exemplo que acompanha o texto é biomedicina); e quem desenvolve. Cada seção é curta. Números como (D-020) remetem a [DECISIONS.md](DECISIONS.md), onde estão os motivos e as medições. A versão em inglês está em [GUIDE.md](GUIDE.md).

**Comece por aqui** (os detalhes estão na seção 2):
- *Só quero usar:* baixe o programa do seu sistema em [Releases](https://github.com/Tatiwel/transcript-normalizer/releases) e dê dois cliques.
- *Uso Python:* `pip install "transcript-normalizer[ingest] @ git+https://github.com/Tatiwel/transcript-normalizer@v0.4.2"`.
- *Quero contribuir:* `git clone https://github.com/Tatiwel/transcript-normalizer` e depois [CONTRIBUTING.md](../CONTRIBUTING.md).

## 1. O que faz, e o que não faz

Legenda automática e reconhecimento de fala erram justamente o vocabulário de cada área. Num vídeo de finanças, CEMIG vira `SEMIG` e EBITDA vira `evitida`; numa aula de farmacologia, metformina vira `metiformina`. A ferramenta conhece os termos que você entrega a ela, num **pacote** (o arquivo de termos), e aponta os lugares em que a transcrição errou um deles. Trecho que não se parece com nada do pacote nunca é tocado: um pacote de finanças não estraga uma aula de biologia (D-001).

Ela nunca muda o que o falante disse; corrige o que o reconhecedor ouviu. Daí a diferença entre **correção** (a legenda estropiou o termo: `SEMIG` vira `CEMIG`) e **alias** (o falante disse mesmo de outro jeito, como o ticker `CMIG4` ou um plural: o termo é reconhecido e o texto fica como foi dito, D-020). A legenda original e seus timestamps nunca são alterados; cada mudança é um registro à parte que aponta para o texto (D-004). Não é corretor ortográfico, não resume nada e não pede a uma IA que reescreva o texto.

## 2. Instalação

**Só quero usar.** Baixe o programa do seu sistema em [Releases](https://github.com/Tatiwel/transcript-normalizer/releases). O `lite` (uns 40 MB) pega a legenda da plataforma; o `full` (algumas centenas de MB) também transcreve áudio no seu computador; na primeira vez, baixa um modelo de fala de 1,5 GB. A página da Release tem uma tabela dizendo qual arquivo é qual. Windows: dois cliques no `.exe`; o arquivo não é assinado, então, se o Windows disser que protegeu o computador, escolha *Mais informações* e depois *Executar assim mesmo*. macOS (Apple Silicon): descompacte e, na primeira vez, clique com o botão direito e escolha *Abrir*. Linux: extraia e rode pelo terminal. O programa abre o menu (seção 3). Seus arquivos vão para `Documentos/transcript-normalizer/` (`runs/` e `packs/`), e a primeira linha do menu diz onde (D-052).

**Uso Python.**

```
pip install "transcript-normalizer[ingest] @ git+https://github.com/Tatiwel/transcript-normalizer@v0.4.2"
```

Sem extra, vem só o normalizador (poucos MB): para chamar do seu próprio programa, ou normalizar legendas que você já tem. `[captions]` acrescenta o `fetch` com legendas das plataformas (yt-dlp); `[ingest]` acrescenta também o reconhecimento de fala local (faster-whisper). Os arquivos ficam no diretório atual. O pacote ainda não está no PyPI; o wheel também vai anexado a cada Release.

**Quero contribuir.**

```
git clone https://github.com/Tatiwel/transcript-normalizer
cd transcript-normalizer
uv sync
uv run pytest -q
```

O `uv sync` instala todos os extras, pelo grupo `dev`. Depois, leia [CONTRIBUTING.md](../CONTRIBUTING.md).

Em qualquer caso: não é preciso ffmpeg (o faster-whisper decodifica o áudio sozinho). Para ler o YouTube, as versões recentes do yt-dlp exigem um runtime de JavaScript, como o Deno; se o download do YouTube falhar com uma mensagem sobre JavaScript, instale um.

## 3. Primeiro uso, de dois jeitos

**O menu.** Dê dois cliques no programa, ou digite `transcript-normalizer`, sem mais nada, num terminal. Com o extra `[menu]` (todo executável tem) você navega pelas setas. O menu está em inglês:

```
transcript-normalizer 0.4.2
Your files: /home/ana/Documentos/transcript-normalizer
Typical flow: 1 fetch → 2 normalize → 3 review
Keyboard: ↑↓ move · enter confirm · esc back · ? explain
? What would you like to do?
 » Fetch a video or file   download a caption, or transcribe audio locally
   Normalize a run         fix domain terms in a fetched caption
   Review pending          answer what the tool was unsure about
   Show a run's outputs    where the files are, first lines of the result
   List runs               everything under runs/
   Help                    what each action does and its command
   Quit
```

Cada passo oferece o seguinte: depois de baixar, "Next: normalize this run now?"; em seguida "What is this video about?" (sobre o que é o vídeo), com a lista dos seus pacotes e "none / another area" (seção 6); depois de normalizar, três contadores e "Next: review the 6 uncertain one(s) now?". O resultado já serve sem a revisão; revisar melhora o próximo vídeo. Depois de uma revisão, o menu oferece contribuir com o que você ensinou à ferramenta (seção 6), e no fim "Open the folder?" abre a pasta da run no gerenciador de arquivos. "Normalize a run" também aceita um arquivo que você já tem: escolha "A file…" e digite o caminho, um `legenda.txt` ou uma legenda `.srt` ou `.vtt`. Esc ou entrada vazia em qualquer pergunta volta, e `?` explica as opções. Sem o extra, ou fora de um terminal, as mesmas perguntas aparecem como linhas numeradas. Cada item do menu executa um dos comandos abaixo; o que você faz no menu vale num script (D-051, D-053). O que a normalização mostra no menu, para o vídeo abaixo:

```
corrected 24  (semiga → CEMIG, Semig → CEMIG)
recognized 65  (terms already spelled right, left as they are)
to confirm 6  (the tool was unsure; your answer is remembered)
result: runs/4wCtn8BWR4o/normalized.txt
```

`transcript-normalizer help` (ou `--help`, ou o item 6 do menu) imprime a referência inteira, em seções: USAGE, COMMANDS, MENU, WHAT HAPPENS, THE REVIEW LOOP, EXAMPLES, LEARN MORE.

**Os três comandos.**

```
transcript-normalizer fetch https://youtu.be/4wCtn8BWR4o
transcript-normalizer runs/4wCtn8BWR4o/legenda.txt
transcript-normalizer runs/4wCtn8BWR4o/legenda.txt --review
```

O `fetch` pega a legenda da plataforma (a faixa no idioma original, nunca uma tradução automática, D-045) e, se não houver, transcreve o áudio localmente (D-036). Também aceita um arquivo de áudio ou vídeo: `transcript-normalizer fetch aula.mp4`. O `.vtt` ou `.srt` baixado é apagado depois de convertido em `legenda.txt`; `--keep-raw` o mantém. O segundo comando normaliza, e aceita também um `.srt` ou `.vtt`, que antes converte em `runs/<nome-do-arquivo>/legenda.txt`; o terceiro faz o mesmo e depois pergunta o que ficou em dúvida. `transcript-normalizer list` mostra o que você já tem. Parte do que o segundo imprime para o vídeo acima:

```
runs/4wCtn8BWR4o/legenda.txt: 239 caption lines, pack 0.3.4
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
 "score": 100, "applied": true, "pack_version": "0.3.4"}
```

`kind` é `correction` ou `alias`. `band` é o grau de certeza: **high** (uma forma já listada: aplicada), **medium** (um palpite próximo: aplicado e listado em `pending.txt` para você confirmar), **low** (uma semelhança fraca: só registrada, nunca aplicada) (D-011).

## 5. Revisando o que ficou em dúvida

O item 3 do menu, ou `--review`, mostra uma tela por termo: as formas que a ferramenta achou que são aquele termo, cada uma com quantas vezes aparece e uma linha onde aparece. Marque as que são de fato o reconhecedor errando o termo (barra de espaço, depois Enter); as que ficarem desmarcadas são rejeitadas e não voltam. Aqui, `a DAPTA Valdre` é a ferramenta do canal, `Adapta Valuer`:

```
Which of these are the recognizer mishearing "Adapta Valuer"?
  pick the ones that should read Adapta Valuer; the others are rejected
  a. [ ] AdaptaValor      1 occurrence · 18:16  …uma nova aba também aqui da «AdaptaValor», análise
  b. [ ] Adaptavalda      1 occurrence · 1:04  …aba mais recente aqui da «Adaptavalda», entramos aqui
  c. [ ] a DAPTA Valdre   1 occurrence · 5:03  …É o que eu sempre te falo, «a DAPTA Valdre»
  d. [ ] adaptavala       1 occurrence · 18:42  de R, tudo isso na «adaptavala».
```

Se você marcou alguma, uma segunda tela pergunta quais delas o falante disse assim mesmo (um ticker, um plural, um apelido): essas ficam como foram ditas e só são reconhecidas (D-020). **Se precisar pensar mais de dois segundos num termo, aperte Esc:** ele fica pendente e volta na próxima vez; resposta errada fica gravada. As respostas são salvas a cada termo (D-037), em `packs/<nome-do-pacote>.learned.yaml`, a sua camada pessoal, nunca no pacote (D-013).

O `--confirm` pergunta a mesma coisa uma forma por vez, com `y` (é o termo), `n` (não é), `l` (é, dito assim), `s` (pular), `a` ou `r` (sim ou não para as formas que faltam do termo):

```
  Osvaldo Cruz  (1 occurrence)
    0:20  a metformina ainda é a primeira escolha, segundo o Osvaldo Cruz
    Osvaldo Cruz -> Oswaldo Cruz? [y]es / [n]o / [s]kip / a[l]ias / [a]ll-yes / [r]est-no:
```

## 6. Pacotes

**Qual pacote, e se ele serve.** Um pacote é de uma área. Aplicado a um vídeo de outra área, só pode fazer estrago: acha uma palavra curta qualquer que lembra um dos termos, e toda mudança que faz ali está errada (D-035). Por isso, antes de aplicar qualquer coisa, a ferramenta conta quantos termos do pacote achou com confiança. Menos de três, e ela não muda nada (D-054):

```
pack financas-ptbr does not seem to fit this transcript (1 terms found); nothing applied. Use --force to apply anyway.
```

O `normalized.txt` fica então igual à transcrição. `--force` aplica o pacote mesmo assim, para um trecho curto que é mesmo da área. No menu, "What is this video about?" pergunta antes: escolha o pacote, ou "none / another area", que não normaliza nada.

**Instalando pacotes.** Os pacotes ficam num repositório próprio, [transcript-normalizer-packs](https://github.com/Tatiwel/transcript-normalizer-packs), um diretório por pacote, cada um com as pessoas que o mantêm (D-055). O pacote de finanças também vem dentro da ferramenta, para funcionar sem internet.

```
transcript-normalizer pack list
transcript-normalizer pack install financas-ptbr
transcript-normalizer pack update
```

O `pack install` põe o pacote no seu `packs/` depois de conferi-lo contra o checksum que o repositório publica; dali em diante é ele que a ferramenta usa, e o menu o lista. O `pack update` instala versões novas e não mexe num pacote que você editou.

**A sua área.** Um pacote é um arquivo YAML. Eis um primeiro pacote de biomedicina, com seis termos, um de cada tipo que você deve precisar:

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

As suas respostas na revisão vão crescendo `packs/biomed-ptbr.learned.yaml`. Quando uma entrada aprendida se provar, passe-a à mão para o pacote e suba a versão; a seção 2 de [CONTRIBUTING.md](../CONTRIBUTING.md) tem as regras de curadoria e mostra como medir um pacote. Para compartilhar um pacote, proponha-o ao repositório de pacotes; o README dele diz como.

**Devolvendo.** O que você ensina à ferramenta numa revisão fica na sua camada aprendida. Para oferecê-lo a todo mundo que usa o pacote:

```
transcript-normalizer pack propose --pack financas-ptbr
```

```
What would be contributed to financas-ptbr 0.3.4 (3), from packs/financas-ptbr.learned.yaml:
  + variant   esse mig -> CEMIG
  + alias     Klabinha -> Klabin
  - rejected  saber se  (not Sabesp)
Only these lines are sent: the term, the form and your decision, never the transcript.
Contribute these? [y/N]
```

Com um sim, grava `contributions/financas-ptbr-<data>.yaml` e abre no navegador uma issue já preenchida no repositório de pacotes (ou imprime o link); você a envia por lá, e quem mantém o pacote decide o que entra (D-056). O menu oferece isso depois de uma revisão.

## 7. Outro idioma

O pacote declara o idioma (`language: pt-BR`), e um módulo de idioma fornece o que o núcleo não deve adivinhar: como dobrar o texto (caixa, acentos), como é um plural, os padrões de unidade, onde termina uma frase e o esqueleto fonético. Por enquanto só existe português do Brasil. Acrescentar um idioma é um arquivo Python; a seção 1 de [CONTRIBUTING.md](../CONTRIBUTING.md) mostra o caminho.

## 8. Quão bom é

Quatro vídeos têm um gabarito conferido à mão (o arquivo **gold**) e são medidos de novo a cada mudança (`uv run python scripts/measure.py`). Com o pacote que vem junto (0.3.4):

| vídeo | linhas a acertar | acertos | faltas | mudanças erradas |
|---|---|---|---|---|
| R2Qgz8tFWVI | 167 | 142 | 25 | 16 |
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
- **encaixe do pacote** (pack fit): se o pacote é da transcrição: pelo menos três termos achados com confiança, ou nada é aplicado.
- **variante** (variant): uma forma que o reconhecedor produziu no lugar do termo; é corrigida.
- **alias**: outro nome correto do termo (ticker, marca, plural); reconhecido, nunca alterado.
- **faixa** (band): o grau de certeza de um casamento: alta (aplicada), média (aplicada e perguntada), baixa (só registrada).
- **run**: o diretório `runs/<id-do-vídeo>/`, com a transcrição de um vídeo e tudo o que saiu dela.
- **fixture**: um vídeo guardado no repositório com a transcrição, um pacote congelado e um gabarito, para medir.
- **gold** (gabarito): a resposta conferida à mão de uma fixture: cada lugar que deve mudar e cada lugar que não pode.
- **camada aprendida** (learned layer): as suas respostas da revisão (`--review` ou `--confirm`), em `packs/<pacote>.learned.yaml`; pessoal, nunca distribuída.
- **stand-off**: guardar as mudanças como registros à parte que apontam para o texto original, em vez de editá-lo.
