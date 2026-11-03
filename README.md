# MediaForge

Aplicativo desktop local para Windows que baixa mídia de links diretos autorizados e de vídeos individuais públicos do YouTube, converte arquivos de mídia e extrai áudio. O processamento de arquivos locais acontece no seu computador, sem contas, telemetria ou envio dos seus arquivos a servidores.

> **Uso responsável:** baixe e converta somente conteúdo que você criou, que esteja em domínio público, tenha licença compatível ou para o qual possua autorização expressa. Respeite direitos autorais, os termos das plataformas e a legislação aplicável.

Desenvolvido por Ernani Salasar  
Copyright (c) 2026 Ernani Salasar

## Recursos principais

- Download de links diretos de mídia e de um único vídeo público do YouTube por vez.
- Melhor qualidade disponível na fonte: usando **Original** e sem conversão, o download pode preservar 1080p, 1440p ou 2160p (4K) quando a fonte os oferecer.
- Download de áudio do YouTube com seleção do melhor fluxo de áudio (`bestaudio`).
- Saída de áudio em MP3, M4A, WAV, FLAC e Opus.
- Conversão de vídeos locais para MP4, WebM, MOV e MKV.
- Conversão opcional após um download, com preservação do intermediário se a conversão falhar ou for cancelada.
- Fila de tarefas, progresso, estimativa de tempo e cancelamento.
- Histórico local em SQLite e configurações locais em JSON.
- Proteções contra URLs internas, redirecionamentos inseguros, arquivos HTML disfarçados e sobrescrita acidental.

Não há capturas de tela versionadas neste repositório. Elas podem ser adicionadas em uma etapa futura, com imagens reais da aplicação.

## Requisitos do sistema

- Windows 10 ou Windows 11.
- Python 3.11 ou superior. O fluxo documentado abaixo usa Python 3.12.
- FFmpeg e FFprobe instalados e disponíveis no `PATH`, ou configurados na aplicação.
- Conexão com a internet somente para consultar metadados e baixar a mídia solicitada.

O código também pode ser usado para desenvolvimento em Linux e macOS, mas o fluxo principal de instalação e empacotamento é voltado ao Windows.

## Instalação no Windows

Abra o PowerShell na pasta do projeto e execute:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Se você não tiver o Python 3.12 instalado, instale uma versão compatível do Python e ajuste o primeiro comando para a versão disponível. Marque a opção para adicionar o Python ao `PATH` durante a instalação.

Para instalar também as ferramentas de teste:

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
```

## Instalação do FFmpeg e FFprobe

O MediaForge não baixa executáveis automaticamente. Uma opção de instalação no Windows é:

```powershell
winget install Gyan.FFmpeg
```

Feche e abra novamente o PowerShell ou o VS Code. Em seguida, confirme a instalação:

```powershell
ffmpeg -version
ffprobe -version
```

Como alternativa, baixe uma build indicada em [ffmpeg.org/download.html](https://ffmpeg.org/download.html), extraia-a e adicione a pasta `bin` ao `PATH`. Também é possível informar essa pasta em **Configurações → Pasta do FFmpeg** ou usar a variável de ambiente `MEDIAFORGE_FFMPEG_DIR`.

Para verificar o ambiente sem abrir a interface:

```powershell
.venv\Scripts\python -m mediaforge --check
```

### Runtime JavaScript para downloads do YouTube

O yt-dlp utiliza scripts EJS e um runtime JavaScript para resolver desafios JavaScript do YouTube. O projeto declara explicitamente yt-dlp-ejs==0.8.0, compativel com yt-dlp==2026.10.26. Brotli, Certifi, PyCryptodome e WebSockets sao declarados separadamente. Mutagen foi excluido porque a aplicacao nao utiliza a incorporacao de miniaturas.

Instale também o Deno 2.3.0 ou superior, recomendado pelo projeto yt-dlp. Instruções oficiais:
https://docs.deno.com/runtime/getting_started/installation/

Confirme a instalação no PowerShell com o comando: deno --version

O Deno precisa estar disponível no PATH. Ele não é instalado pelo pip nem incluído no executável do MediaForge. Em outra máquina, deverá ser instalado separadamente para utilizar os downloads do YouTube. Links diretos de mídia e conversões locais não dependem dele.

## Como iniciar

No PowerShell:

```powershell
.venv\Scripts\python -m mediaforge
```

No Windows, você também pode executar `run.bat` por duplo clique depois de criar o ambiente virtual e instalar as dependências.

## Baixar um vídeo na melhor qualidade disponível

1. Cole a URL de um vídeo individual público do YouTube ou um link direto para um arquivo de mídia.
2. Clique em **Validar fonte** e aguarde a leitura dos metadados.
3. Selecione **Vídeo**.
4. Para preservar o arquivo disponibilizado pela fonte, selecione **Original** e deixe desmarcada a opção **Converter para o formato escolhido após baixar**.
5. Escolha a pasta de destino e clique em **Baixar**.

O aplicativo não apresenta seletores explícitos para 1440p ou 2160p. A opção **Original** preserva a melhor combinação de vídeo e áudio que a fonte disponibilizar; isso pode incluir 1080p, 1440p ou 4K, mas não é garantido para toda URL.

São aceitos somente vídeos individuais públicos do YouTube. Playlists, transmissões ao vivo, estreias e conteúdo que exija login, cookies ou credenciais não são suportados.

## Extrair áudio do YouTube

1. Valide uma URL de vídeo individual público do YouTube.
2. Selecione **Áudio**.
3. Escolha MP3, M4A, WAV, FLAC ou Opus e, quando aplicável, o bitrate desejado.
4. Escolha a pasta de destino e clique em **Baixar áudio**.

Nesse modo, o MediaForge solicita somente o melhor fluxo de áudio disponível. O FFmpeg realiza o pós-processamento local para o formato selecionado. Converter um áudio com perdas para WAV ou FLAC não recupera detalhes já perdidos na fonte.

## Converter arquivos locais

1. Clique em **Selecionar arquivos…** ou arraste vídeos e áudios para a janela.
2. Escolha **Vídeo** ou **Áudio**, o formato de saída, a resolução e a qualidade do áudio.
3. Informe a pasta de destino e clique em **Converter** ou **Extrair áudio**.

O original não é alterado. O resultado é gravado primeiro em um arquivo temporário e só substitui o destino após uma verificação com FFprobe. A aplicação pede confirmação antes de sobrescrever um arquivo existente.

## Download, conversão e tempo de processamento

Baixar e converter são operações distintas. Quando **Converter para o formato escolhido após baixar** está marcada, o aplicativo baixa primeiro o arquivo original e cria uma tarefa de conversão em seguida.

Conversões dependem da duração, resolução, codecs e desempenho do computador. Vídeos 4K podem exigir mais tempo. Se a sua intenção é apenas preservar o arquivo da fonte, deixe a conversão desmarcada.

Se a conversão posterior for cancelada ou falhar, o download original é preservado para uma nova tentativa. O intermediário só é removido após uma conversão bem-sucedida.

## Fila, cancelamento, configurações e histórico

- A fila mostra o estado de cada tarefa: aguardando, em andamento, concluído, cancelado ou falhou.
- Selecione uma tarefa para acompanhar o progresso no rodapé e use **Cancelar** para interrompê-la.
- Em **Configurações**, ajuste pasta de saída, localização do FFmpeg, limite por download, retenção de histórico e timeouts.
- O histórico é salvo apenas no computador em `%LOCALAPPDATA%\MediaForgeLocal\`. Ele guarda dados operacionais e o host de origem, não a URL completa, cookies ou tokens.

## Problemas frequentes

### FFmpeg ou FFprobe não encontrados

Instale-os, reinicie o terminal e confirme com:

```powershell
ffmpeg -version
ffprobe -version
```

Depois use **Configurações → Pasta do FFmpeg** se necessário.

### A fonte não pode ser validada

Verifique se a URL é pública, aponta diretamente para mídia ou para um vídeo individual do YouTube e não exige login. Endereços de rede local, privada, loopback ou metadados de nuvem são bloqueados de propósito.

### Um formato está indisponível

Os formatos oferecidos dependem dos codificadores presentes na instalação do FFmpeg. Instale uma build completa do FFmpeg e execute novamente `--check`.

### O download ou a conversão foi interrompido

Arquivos parciais de download podem ser mantidos para diagnóstico quando a conexão falha. Saídas parciais de conversão também podem ser mantidas quando o FFmpeg retorna um erro. Arquivos cancelados são limpos automaticamente.

## Privacidade e segurança

Não há telemetria, anúncios ou contas. A rede é usada somente para consultar a fonte pública informada e baixar sua mídia; nenhum arquivo local é enviado.

- Sem cookies de navegador, proxies, senhas ou tokens de autenticação.
- Validação de URL, DNS, redirecionamentos e conexão TCP contra SSRF e DNS rebinding.
- Sem `shell=True`: FFmpeg e FFprobe recebem listas de argumentos.
- Nomes e caminhos de saída são sanitizados para evitar path traversal.

Os detalhes técnicos estão em [docs/SEGURANCA.md](docs/SEGURANCA.md) e [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

## Direitos autorais e uso autorizado

Você é responsável por ter o direito de baixar ou converter o conteúdo usado. O MediaForge não tenta contornar autenticação, restrições de acesso ou proteções de plataformas.

## Empacotamento Windows

O script `build_exe.bat` prepara um executável Windows com PyInstaller e declara explicitamente o ícone SVG como dado da aplicação. O FFmpeg não é incluído: ele deve ser instalado separadamente pelo usuário.

A compilação em modo onedir foi validada no Windows 11 com Python 3.14.3 e PyInstaller 6.22.3. O executável gerado foi aberto e testado para download de vídeo, extração de áudio, conversão local e exibição da fila. O script instala o PyInstaller no ambiente virtual do projeto quando executado. FFmpeg, FFprobe e Deno não são incluídos e devem ser instalados separadamente, conforme as funções utilizadas.

## Dependências e tecnologias

- Python
- PySide6
- yt-dlp
- FFmpeg e FFprobe
- requests e urllib3
- Brotli, Certifi, PyCryptodome e WebSockets
- yt-dlp-ejs para suporte aos desafios JavaScript do YouTube
- pytest, para testes de desenvolvimento

O ícone `square-letter-m.svg` é do Lucide Icons e mantém seu aviso de copyright e licença ISC no arquivo de origem.

## Licença e conformidade

O código original do MediaForge está licenciado sob a licença MIT. O arquivo [LICENSE](./LICENSE) aplica a licença ao código original do projeto e preserva os direitos autorais de Ernani Salasar.

A licença MIT é aplicada exclusivamente ao código original do MediaForge. Ela não cobre bibliotecas de terceiros, runtimes Qt, bindings PySide6, plugins Qt, nem componentes externos baixados por dependências do projeto. O projeto mantém esses componentes sob seus termos próprios e não afirma que toda a distribuição seja MIT.

Os metadados instalados de PySide6-Essentials e Shiboken6 declaram: `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. Isso não comprova, por si só, a conformidade de uma distribuição. Consulte [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md), os textos em [LICENSES/](./LICENSES/) e a [documentação de licenciamento Qt](./docs/LICENCIAMENTO_QT.md), que registra também as fontes correspondentes e as verificações ainda necessárias.

A exigência mínima de `certifi>=2026.10.19` foi mantida alinhada com a dependência oficial declarada pelo yt-dlp 2026.10.26 (`certifi>=2026.10.19` no extra `default`), e a instalação atual resolve para `certifi 2026.10.23`.

## Créditos

**MediaForge**  
Desenvolvido por Ernani Salasar  
Copyright (c) 2026 Ernani Salasar
