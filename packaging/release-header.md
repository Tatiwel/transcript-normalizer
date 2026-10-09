## Which file do I download?

| file | who it is for | what it does |
|---|---|---|
| `transcript-normalizer-VERSION-<system>-lite` | anyone who just wants to use it | fetches the platform's captions and fixes domain terms; opens a menu when double-clicked |
| `transcript-normalizer-VERSION-<system>-full` (macOS, Linux) | anyone who also has videos without captions, or audio files | everything lite does, and also transcribes audio on your computer (the first time, it downloads a 1.5 GB speech model). On macOS, a `.zip`: unzip, then open `transcript-normalizer` inside the folder. On Windows, full is the two files below |
| `transcript-normalizer-VERSION-windows-full-setup.exe` | Windows, full: the installer | choose where it goes (for you only, no administrator needed, or for all users); Start menu shortcut; clean uninstall from "Add or remove programs", which keeps your files |
| `transcript-normalizer-VERSION-windows-full-portable.zip` | Windows, full: portable | unzip anywhere, e.g. a USB drive, and open `transcript-normalizer.exe` inside the folder; everything (your files, settings, the speech model) stays in its `data` folder; delete the folder to remove it |
| `transcript_normalizer-VERSION-py3-none-any.whl`, `.tar.gz` | Python developers | the package, for `pip install` |

`<system>` is `windows`, `macos` (Apple silicon) or `linux`; Linux executables run on glibc 2.35 or newer (Ubuntu 22.04 and later). The executables are not signed, so Windows and macOS will warn the first time; the SHA-256 of every file is at the end of this page.

## Qual arquivo baixar?

| arquivo | para quem | o que faz |
|---|---|---|
| `transcript-normalizer-VERSION-<sistema>-lite` | quem só quer usar | pega a legenda da plataforma e corrige os termos da área; abre um menu com dois cliques |
| `transcript-normalizer-VERSION-<sistema>-full` (macOS, Linux) | quem também tem vídeos sem legenda, ou arquivos de áudio | tudo o que o lite faz, e ainda transcreve o áudio no seu computador (na primeira vez, baixa um modelo de fala de 1,5 GB). No macOS, um `.zip`: descompacte e abra o `transcript-normalizer` dentro da pasta. No Windows, o full são os dois arquivos abaixo |
| `transcript-normalizer-VERSION-windows-full-setup.exe` | Windows, full: o instalador | você escolhe onde instalar (só para você, sem administrador, ou para todos os usuários); atalho no menu Iniciar; desinstalação limpa em "Adicionar ou remover programas", que mantém os seus arquivos |
| `transcript-normalizer-VERSION-windows-full-portable.zip` | Windows, full: portátil | descompacte em qualquer lugar, por exemplo num pendrive, e abra o `transcript-normalizer.exe` dentro da pasta; tudo (seus arquivos, configurações, o modelo de fala) fica na pasta `data` dele; apague a pasta para removê-lo |
| `transcript_normalizer-VERSION-py3-none-any.whl`, `.tar.gz` | quem programa em Python | o pacote, para `pip install` |

`<sistema>` é `windows`, `macos` (Apple Silicon) ou `linux`; os executáveis de Linux rodam com glibc 2.35 ou mais nova (Ubuntu 22.04 em diante). Os executáveis não são assinados, então o Windows e o macOS avisam na primeira vez; o SHA-256 de cada arquivo está no fim desta página.

---

