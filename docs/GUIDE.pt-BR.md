# transcript-normalizer: guia

Este guia serve a três leitores ao mesmo tempo: quem só quer transcrições mais limpas; quem estuda outra área e quer ensinar o próprio vocabulário à ferramenta (o exemplo que acompanha o texto é biomedicina); e quem desenvolve. Cada seção é curta. Números como (D-020) remetem a [DECISIONS.md](DECISIONS.md), onde estão os motivos e as medições. A versão em inglês está em [GUIDE.md](GUIDE.md).

**Comece por aqui** (os detalhes estão na seção 2):
- *Só quero usar:* baixe o programa do seu sistema em [Releases](https://github.com/Tatiwel/transcript-normalizer/releases) e dê dois cliques.
- *Uso Python:* `pip install "transcript-normalizer[ingest] @ git+https://github.com/Tatiwel/transcript-normalizer@v0.6.3"`.
- *Quero contribuir:* `git clone https://github.com/Tatiwel/transcript-normalizer` e depois [CONTRIBUTING.md](../CONTRIBUTING.md).

## 1. O que faz, e o que não faz

Legenda automática e reconhecimento de fala erram justamente o vocabulário de cada área. Num vídeo de finanças, CEMIG vira `SEMIG` e EBITDA vira `evitida`; numa aula de farmacologia, metformina vira `metiformina`. A ferramenta conhece os termos que você entrega a ela, num **pacote** (o arquivo de termos), e aponta os lugares em que a transcrição errou um deles. Trecho que não se parece com nada do pacote nunca é tocado: um pacote de finanças não estraga uma aula de biologia (D-001).

Ela nunca muda o que o falante disse; corrige o que o reconhecedor ouviu. Daí a diferença entre **correção** (a legenda estropiou o termo: `SEMIG` vira `CEMIG`) e **alias** (o falante disse mesmo de outro jeito, como o ticker `CMIG4` ou um plural: o termo é reconhecido e o texto fica como foi dito, D-020). A legenda original e seus timestamps nunca são alterados; cada mudança é um registro à parte que aponta para o texto (D-004). Não é corretor ortográfico, não resume nada e não pede a uma IA que reescreva o texto.

## 2. Instalação

**Só quero usar.** Baixe o programa do seu sistema em [Releases](https://github.com/Tatiwel/transcript-normalizer/releases). O `lite` (uns 40 MB) pega a legenda da plataforma; o `full` (algumas centenas de MB) também transcreve áudio no seu computador; na primeira vez, baixa um modelo de fala de 1,5 GB. A página da Release tem uma tabela dizendo qual arquivo é qual. O `lite` é um arquivo só. O `full` do Windows vem como instalador (`-setup.exe`: pergunta onde instalar, só para você ou para todos os usuários, e cria um atalho no menu Iniciar; desinstale em "Adicionar ou remover programas", que remove o programa e mantém os seus arquivos) ou como zip portátil (abaixo). No macOS, o `full` é um zip com uma pasta dentro: descompacte e abra o `transcript-normalizer` dentro da pasta, e mantenha a pasta inteira, porque o programa carrega suas partes dela (D-063, D-070). Windows: dois cliques no `.exe`; o arquivo não é assinado, então, se o Windows disser que protegeu o computador, escolha *Mais informações* e depois *Executar assim mesmo*. macOS (Apple Silicon): descompacte e, na primeira vez, clique com o botão direito e escolha *Abrir*. Linux: extraia e rode pelo terminal. O programa abre o menu (seção 3). Seus arquivos vão para `Documentos/transcript-normalizer/` (`runs/` e `packs/`), e a primeira tela do menu diz onde (D-052). Para guardá-los em outro lugar, escolha Settings no menu e depois "Where to save your files": abre uma janela para escolher a pasta (ou, onde não há janela, você digita o caminho), e a escolha fica em `config.toml`, na pasta de configurações do usuário (D-061).

**Uso Python.**

```
pip install "transcript-normalizer[ingest] @ git+https://github.com/Tatiwel/transcript-normalizer@v0.6.3"
```

Sem extra, vem só o normalizador (poucos MB): para chamar do seu próprio programa, ou normalizar legendas que você já tem. `[captions]` acrescenta o `fetch` com legendas das plataformas (yt-dlp); `[ingest]` acrescenta também o reconhecimento de fala local (faster-whisper). Os arquivos ficam no diretório atual, a não ser que o Settings do menu tenha escolhido uma pasta. O pacote ainda não está no PyPI; o wheel também vai anexado a cada Release.

**Quero contribuir.**

```
git clone https://github.com/Tatiwel/transcript-normalizer
cd transcript-normalizer
uv sync
uv run pytest -q
```

O `uv sync` instala todos os extras, pelo grupo `dev`. Depois, leia [CONTRIBUTING.md](../CONTRIBUTING.md).

Em qualquer caso: não é preciso ffmpeg (o faster-whisper decodifica o áudio sozinho). Para ler o YouTube, as versões recentes do yt-dlp exigem um runtime de JavaScript, como o Deno; se o download do YouTube falhar com uma mensagem sobre JavaScript, instale um.

### Modo portátil

O build full do Windows também vem como zip portátil (`-portable.zip`). Descompacte em qualquer lugar, num pendrive por exemplo, e abra o `transcript-normalizer.exe` dentro da pasta. Ao lado dele está o `portable.txt`: enquanto esse arquivo estiver ali, o programa guarda tudo na pasta `data` ao lado dele: suas runs e pacotes, as configurações, o modelo de fala que ele baixa e o cache do yt-dlp. Nada vai para Documentos, para a pasta de configurações do usuário nem para qualquer outro lugar do computador, então apagar a pasta o remove por completo. Settings diz "portable mode: everything stays in <pasta>" e não oferece outra pasta; para mudar seus arquivos de lugar, mova a pasta inteira. Qualquer build fica portátil do mesmo jeito: ponha um `portable.txt` ao lado do `transcript-normalizer.exe` (o lite também). O `TRANSCRIPT_NORMALIZER_HOME`, para scripts, continua tendo prioridade (D-070).

## 3. Primeiro uso, de dois jeitos

**O menu.** Dê dois cliques no programa, ou digite `transcript-normalizer`, sem mais nada, num terminal. Com o extra `[menu]` (todo executável tem) você navega pelas setas. O menu está em inglês:

```
transcript-normalizer 0.6.3
full build: captions and local transcription
Your files: /home/ana/Documentos/transcript-normalizer
Typical flow: 1 fetch → 2 normalize → 3 review
Keyboard: ↑↓ move · enter confirm · esc back · ? explain
  pick an action; empty input or Esc here quits
◇ What would you like to do? ↑↓ move · enter confirm · esc back · ? explain
 » Fetch a video or file   download a caption, or transcribe audio locally
   Normalize a run         fix domain terms in a fetched caption
   Review pending          answer what the tool was unsure about
   Show a run's outputs    where the files are, first lines of the result
   List runs               everything under runs/
   Packs                   installed, get, create, edit, share
   Settings                where to save your files
   Help                    what each action does and its command
   Quit
```

"Fetch a video or file" pergunta primeiro "Where is it?": um link, ou um arquivo no computador. Um arquivo abre a janela de arquivos do sistema (ou, onde não há janela, você digita o caminho); uma legenda (`.srt`, `.vtt`, `legenda.txt`) vai direto para a normalização, e um arquivo de áudio ou vídeo é transcrito no seu computador. Para um link, o menu lê o vídeo, mostra título, canal e duração, e pergunta "Use the platform's caption, or transcribe the audio on this computer?" (no build lite a segunda opção aparece como "full build only"). A legenda é escolhida pelo nome: primeiro "Portuguese, original audio (automatic)", que o Enter escolhe, depois a do próprio canal ("Portuguese (written by the channel)"), depois "Other languages (automatic translations)…", marcada "(translations are rate-limited more often)", porque o YouTube recusa traduções com HTTP 429 com mais frequência. Sem legenda nenhuma, o build full oferece transcrever e o lite explica por que não pode (D-062). Cada passo oferece o seguinte: depois de baixar, "Next: normalize this run now?"; em seguida "What is this video about?" (sobre o que é o vídeo), com a lista dos seus pacotes e "none / another area" (seção 6); depois de normalizar, três contadores e "Next: review the 6 uncertain one(s) now?". O resultado já serve sem a revisão; revisar melhora o próximo vídeo. Depois de uma revisão, o menu oferece contribuir com o que você ensinou à ferramenta (seção 6), e no fim "Open the folder?" abre a pasta da run no gerenciador de arquivos. "Normalize a run" também aceita um arquivo que você já tem: escolha "A file…" e digite o caminho, um `legenda.txt` ou uma legenda `.srt` ou `.vtt`. Toda lista termina com "← Back", que volta à tela anterior (Esc faz o mesmo, e entrada vazia num campo de texto também), e `?` explica as opções. Abaixo da versão, a primeira tela diz o que esta instalação faz: "full build: captions and local transcription" ou "lite build: platform captions only (no local transcription)" no programa, "captions + local transcription" ou "captions only" numa instalação por pip. Cada bloco começa com uma linha e o nome da etapa (◆ Fetch, ◆ Normalize, ◆ Review, ◆ Settings), e uma linha como "── paste below ──" marca onde digitar. Sem o extra, ou fora de um terminal, as mesmas perguntas aparecem como linhas numeradas, com marcas em ASCII (`* Fetch`, `b. <- Back`). Cada item do menu executa um dos comandos abaixo; o que você faz no menu vale num script (D-051, D-053). O que a normalização mostra no menu, para o vídeo abaixo:

```
corrected 24  (semiga → CEMIG, Semig → CEMIG)
recognized 65  (terms already spelled right, left as they are)
to confirm 6  (the tool was unsure; your answer is remembered)
result: runs/4wCtn8BWR4o/normalized.txt
```

`transcript-normalizer help` (ou `--help`, ou o item 8 do menu) imprime a referência inteira, em seções: USAGE, COMMANDS, MENU, WHAT HAPPENS, THE REVIEW LOOP, EXAMPLES, LEARN MORE.

**Os três comandos.**

```
transcript-normalizer fetch https://youtu.be/4wCtn8BWR4o
transcript-normalizer runs/4wCtn8BWR4o/legenda.txt
transcript-normalizer runs/4wCtn8BWR4o/legenda.txt --review
```

O `fetch` pega a legenda da plataforma (a faixa no idioma original, nunca uma tradução automática, D-045) e, se não houver, transcreve o áudio localmente (D-036). Também aceita um arquivo de áudio ou vídeo: `transcript-normalizer fetch aula.mp4`. O `.vtt` ou `.srt` baixado é apagado depois de convertido em `legenda.txt`; `--keep-raw` o mantém. O segundo comando normaliza, e aceita também um `.srt` ou `.vtt`, que antes converte em `runs/<nome-do-arquivo>/legenda.txt`; o terceiro faz o mesmo e depois pergunta o que ficou em dúvida. `fetch --list <url>` mostra as faixas de legenda de um vídeo, e `fetch --track <código>` escolhe uma exatamente (`pt-orig`, `pt`, `en`), no lugar da escolha do `--lang` (D-062). `transcript-normalizer list` mostra o que você já tem. Parte do que o segundo imprime para o vídeo acima:

```
runs/4wCtn8BWR4o/legenda.txt: 239 caption lines, pack 0.3.7
terms:
  Semig, semiga, SEMIG, Semiga (21 occurrences) -> CEMIG
  evitida (1 occurrence) -> EBITDA
  dividendio (1 occurrence) -> dividend yield
  dívida alíquida (1 occurrence) -> dívida líquida

recognized (not changed):
  CEMIG (14 occurrences) -> CEMIG
  bilhões, Bilhões (8 occurrences) -> bilhão

to confirm:
  Adaptavalda, a DAPTA Valdre, AdaptaValor, adaptavala (4 occurrences) -> Adapta Valuer
  dividido (2 occurrences) -> dividendo
  preço alto (1 occurrence) -> preço alvo
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
 "score": 100, "applied": true, "pack_version": "0.3.7"}
```

`kind` é `correction` ou `alias`. `band` é o grau de certeza: **high** (uma forma já listada: aplicada), **medium** (um palpite próximo: aplicado e listado em `pending.txt` para você confirmar), **ask** (um nome que soa como um nome do pacote: nunca aplicado, só listado em `pending.txt` e perguntado, D-050, D-060), **low** (uma semelhança fraca: só registrada, nunca aplicada) (D-011).

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

O `normalized.txt` fica então igual à transcrição. `--force` aplica o pacote mesmo assim, para um trecho curto que é mesmo da área. No menu, "What is this video about?" pergunta antes: escolha o pacote, ou "none / another area", que não normaliza nada. Quando o pacote não serve, o menu termina a frase com "Pick another pack, or get or create one in Packs." em vez do conselho do `--force`; Packs → "The pack offered first" põe um pacote no topo dessa pergunta.

**O menu Packs.** O item 6 do menu, Packs, é onde se cuida dos pacotes (D-065). Cada entrada executa um comando, então um script faz o mesmo:

| no menu | o comando | o que faz |
|---|---|---|
| Installed packs | `pack list --installed` | uma tabela: nome, versão, idioma, termos, tamanho (KB), origem (`bundled`, `repository` ou `mine`); quando o repositório de pacotes responde em até 3 segundos, uma marca `↑ update` onde ele tem versão mais nova |
| Get a pack | `pack install <nome>` | lista o repositório de pacotes (nome, versão, descrição) e instala no seu `packs/` o que você escolher |
| Create a pack | `pack create --template <área> --name <n> --lang <l>` | um pacote novo a partir de um modelo de área, com as classes da área e nenhum termo; depois o menu oferece pô-lo em primeiro |
| Edit a pack | `pack add-term`, `edit-term`, `remove-term`, `show` | acrescenta, edita, remove e mostra termos; um pacote que vem com o programa ou do repositório é só leitura, e o menu oferece antes uma cópia sua (`pack copy`) |
| Import a pack file | `pack import <arquivo>` | uma janela de arquivos com filtro `.yaml` (ou um caminho digitado); o arquivo é conferido como o `normalize` o leria, e copiado para `packs/` |
| Export a pack file | `pack export <nome> [--to <caminho>]` | grava `<nome>-<versão>.yaml` na pasta que você escolher |
| Remove a pack | `pack remove <nome>` | pergunta duas vezes e mostra o arquivo; um pacote que vem com o programa não pode ser removido |
| Contribute a pack | `pack propose --whole <nome>` | propõe o pacote inteiro ao repositório de pacotes (abaixo) |
| The pack offered first | (configuração do próprio menu) | o pacote no topo de "What is this video about?" |

```
name           version  language  terms  size (KB)  source   update
financas-ptbr  0.3.7    pt-BR        70        8.1  bundled
medicina-ptbr  0.1.0    pt-BR         0        0.5  mine
```

Os pacotes ficam num repositório próprio, [transcript-normalizer-packs](https://github.com/Tatiwel/transcript-normalizer-packs), um diretório por pacote, cada um com as pessoas que o mantêm (D-055). O pacote de finanças também vem dentro da ferramenta, para funcionar sem internet. O `pack list` lista o repositório, o `pack install <nome>` põe um pacote no seu `packs/` depois de conferi-lo contra o checksum que o repositório publica (dali em diante é ele que a ferramenta usa, e o menu o lista), e o `pack update` instala versões novas e não mexe num pacote que você editou. O `pack remove` apaga o arquivo do pacote mas guarda a camada aprendida (`packs/<nome>.learned.yaml`), que tem as suas respostas da revisão.

**A sua área.** Um pacote é um arquivo YAML. Comece de um modelo de área, que dá ao pacote as suas classes:

```
transcript-normalizer pack create --template medicina --name biomed-ptbr --lang pt-BR
```

Os dez modelos são `financas`, `medicina`, `direito`, `tecnologia`, `engenharia`, `educacao-ciencias`, `esportes`, `politica-governo`, `agro` e `geral` (para uma área sem modelo próprio). Depois acrescente os termos. Eis um primeiro pacote de biomedicina, com seis termos, um de cada tipo que você deve precisar:

```yaml
# Biomedicina, pt-BR. 0.1.0: first terms, from one lecture.
name: biomed-ptbr
language: pt-BR
version: 0.1.0
classes: [doenca, farmaco, procedimento, anatomia, exame]
terms:
  - term: metformina          # um fármaco
    class: farmaco
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
    class: procedimento
    variants: [western blood, uéstern blot]
  - term: Anvisa              # uma organização
    class: organizacao
    variants: [Anuvisa, Am visa]
```

- `term` é como o termo deve ser escrito. `aliases` são outros nomes corretos (uma marca, um plural, a sigla por extenso). `variants` é o que o reconhecedor produziu no lugar.
- `class` tem de ser uma das `classes:` do pacote, ou uma das quatro que todo pacote tem: `pessoa`, `organizacao`, `sigla`, `unidade` (D-064). A classe é um rótulo para quem lê o resultado; não muda o que é encontrado, exceto que uma `unidade` nunca é encontrada por semelhança (D-028). Um pacote sem a linha `classes:`, escrito antes da 0.6.0, fica com as oito classes de finanças de D-021. Nomes também passam pela comparação fonética, que acha erros nunca vistos antes e pergunta a você; ela nunca muda o texto sozinha (D-050, D-060). Quais classes são nomes é o `phonetic_classes:` do pacote (por padrão `pessoa` e `organizacao`, e `companhia` onde o pacote a tem; o modelo medicina acrescenta `farmaco` e `doenca`, D-068). Precisa de um idioma com esqueleto fonético: pt-BR tem, inglês ainda não.
- Deixe de fora variantes de uma ou duas letras e variantes que são palavras comuns, mesmo que a legenda as tenha usado (D-005, D-032).

O `pack create` põe o arquivo no seu `packs/`; um pacote que você escreveu em outro lugar vai para lá com `pack import <arquivo>`. Aponte para ele:

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

**Editando um pacote.** Packs → Edit a pack escolhe um pacote e oferece: Add a term (o termo, a classe entre as do pacote, depois outros nomes corretos e as versões do reconhecedor, um por linha, linha vazia para terminar), Edit a term (digite parte dele, escolha, e acrescente ou remova formas, mude a classe ou o nome), Remove a term (pergunta uma vez) e Show terms (página por página, ou busca). Um pacote que vem com o programa ou do repositório é só leitura: o menu oferece antes fazer uma cópia sua, com o mesmo nome, que passa a ser usada. Cada mudança é conferida como o normalize leria o pacote e salva na hora, com a próxima versão de correção (0.1.0 → 0.1.1). Uma variante com menos de 3 letras é recusada (acharia palavras demais, D-005), e uma variante feita de palavras comuns é salva com um aviso (D-032). Pela linha de comando:

```
transcript-normalizer pack copy financas-ptbr
transcript-normalizer pack add-term biomed-ptbr metformina --class farmaco --alias Glifage --variant metiformina
transcript-normalizer pack edit-term biomed-ptbr metformina --add-variant "met forming"
transcript-normalizer pack show biomed-ptbr --search metf
```

**Quando sai uma versão nova.** A sua cópia lembra de onde veio (`based_on: financas-ptbr@0.3.7`) e quantas mudanças você salvou desde então (`local_edits`). Quando sai uma versão mais nova, junto com uma nova versão do programa ou no repositório de pacotes, o menu avisa na primeira tela, Installed packs marca `↑ merge available`, e o `pack update` menciona:

```
financas-ptbr 0.4.0 is available; your copy is based on 0.3.7 with 3 local edits.
Merge? [y/N]
```

Nada é mesclado sem você dizer sim. A mescla vai termo a termo: o que só o upstream mudou é aceito, o que só você mudou é mantido, e o que os dois mudaram é combinado quando dá. Quando não dá, ela pergunta, um conflito por vez, mostrando as duas versões e até três linhas das suas próprias runs em que a forma aparece (D-069):

```
Conflict 1: Echo: the class differs on both sides
  base      Echo  (farmaco)
  mine      Echo  (exame)
  theirs    Echo  (doenca)
  in your runs:
    R2Qgz8tFWVI  3:10 o Echo saiu da lista
Which one?
   m. Keep mine
   t. Take theirs
   l. Decide later
```

"Decide later" mantém a sua versão e anota o conflito em `packs/<nome>.merge-pending.yaml`. Antes de gravar, a mescla guarda a sua cópia como `<nome>.yaml.bak-<data e hora>`, e no fim imprime o que foi acrescentado, mantido, combinado e removido. A sua camada aprendida nunca é alterada; o resumo diz onde ela agora repete ou contradiz o pacote. `pack merge <nome> --dry-run` mostra tudo isso sem gravar nada; `--yes-theirs` e `--yes-mine` respondem todos os conflitos de um lado só.

**Um termo que você notou.** Depois de normalizar, e em "Show a run's outputs", o menu pergunta "Add a term you noticed?". Pede a forma errada que você viu, mostra até cinco linhas da run com ela, para você conferir que é essa, e depois o que ela deveria ser. Se esse termo está no pacote, pergunta se o reconhecedor ouviu errado (uma variante, corrigida dali em diante) ou se a pessoa falou assim mesmo (um alias, mantido como foi dito); se não está, pede uma classe e acrescenta o termo com a forma como variante. Depois oferece normalizar a run de novo com ele (D-066):

```
The wrong form you saw
> mississões
  in 1 line(s) of R2Qgz8tFWVI:
    3:22 gestão, tanto as mississões e tal. Então
Is 'mississões' the form you saw? [Y/n]
What it should be
> emissão
+ term     emissão (conceito)
  + variant  mississões -> emissão
Normalize R2Qgz8tFWVI again with it? [Y/n]
```

**Devolvendo.** O que você ensina à ferramenta numa revisão fica na sua camada aprendida. Para oferecê-lo a todo mundo que usa o pacote:

```
transcript-normalizer pack propose --pack financas-ptbr
```

```
What would be contributed to financas-ptbr 0.3.7 (3), from packs/financas-ptbr.learned.yaml:
  + variant   esse mig -> CEMIG
  + alias     Klabinha -> Klabin
  - rejected  saber se  (not Sabesp)
Only these lines are sent: the term, the form and your decision, never the transcript.
Contribute these? [y/N]
```

Com um sim, grava `contributions/financas-ptbr-<data>.yaml` e abre no navegador uma issue já preenchida no repositório de pacotes (ou imprime o link); você a envia por lá, e quem mantém o pacote decide o que entra (D-056). O menu oferece isso depois de uma revisão.

Um pacote inteiro, seu para uma área nova ou um que veio com o programa e você melhorou, é proposto com `pack propose --whole <nome>` (menu: Packs → Contribute a pack). Para uma cópia (um pacote com `based_on`), propõe só o que você mudou desde a base, com o título "financas-ptbr: 3 additions from <você>". Para um pacote seu, mostra a área do pacote, as classes, o número de termos e cinco deles, e pergunta; com um sim, grava `contributions/<nome>-<versão>.yaml` e abre uma issue com o título "New pack: <nome>", ou "Update: <nome>" quando o repositório já tem esse pacote, com o arquivo no corpo, recolhido (ou, para um pacote longo, um aviso para anexar o arquivo). Nada sai do seu computador até você mesmo enviar a issue (D-067). O `pack export <nome>` grava o mesmo arquivo em qualquer lugar, para compartilhar de outro jeito.

## 7. Outro idioma

O pacote declara o idioma (`language: pt-BR`), e um módulo de idioma fornece o que o núcleo não deve adivinhar: como dobrar o texto (caixa, acentos), como é um plural, os padrões de unidade, onde termina uma frase e o esqueleto fonético. Há dois: português do Brasil e inglês (plurais em -s, -es e -ies, `bn`/`B` e `mn`/`M` depois de um número como billion e million, ainda sem esqueleto fonético; D-068). Um pacote em outro idioma é comparado com um módulo genérico, sem inflexões e sem regras de unidade; o menu faz isso sozinho e avisa, e um comando precisa de `--allow-generic`. Acrescentar um idioma é um arquivo Python; a seção 1 de [CONTRIBUTING.md](../CONTRIBUTING.md) mostra o caminho.

## 8. Quão bom é

Quatro vídeos têm um gabarito conferido à mão (o arquivo **gold**) e são medidos de novo a cada mudança. Os números abaixo vêm de `uv run python scripts/measure.py`, que é a fonte: se discordarem, ele está certo. Com o pacote que vem junto (0.3.7):

| vídeo | linhas a acertar | acertos | faltas | mudanças erradas |
|---|---|---|---|---|
| R2Qgz8tFWVI | 167 | 142 | 25 | 15 |
| wxgFO_fyfXg | 222 | 211 | 11 | 9 |
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
- **faixa** (band): o grau de certeza de um casamento: alta (aplicada), média (aplicada e perguntada), ask (um nome pelo som: perguntado, nunca aplicado), baixa (só registrada).
- **run**: o diretório `runs/<id-do-vídeo>/`, com a transcrição de um vídeo e tudo o que saiu dela.
- **fixture**: um vídeo guardado no repositório com a transcrição, um pacote congelado e um gabarito, para medir.
- **gold** (gabarito): a resposta conferida à mão de uma fixture: cada lugar que deve mudar e cada lugar que não pode.
- **camada aprendida** (learned layer): as suas respostas da revisão (`--review` ou `--confirm`), em `packs/<pacote>.learned.yaml`; pessoal, nunca distribuída.
- **stand-off**: guardar as mudanças como registros à parte que apontam para o texto original, em vez de editá-lo.
